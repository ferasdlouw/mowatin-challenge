"""Tests for scripts/split_testset.py: validate, and a split that never overwrites a frozen set."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import pytest

from .conftest import FIXTURES, REPO

TOOL = REPO / "scripts" / "split_testset.py"


def _tool(*args: str) -> subprocess.CompletedProcess[str]:
    # The tool prints Arabic: UTF-8 on both ends, or a cp1252 console (Windows) garbles it.
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_validate_accepts_the_fixture_and_rejects_a_bad_row(tmp_path):
    assert _tool("validate", str(FIXTURES / "testset" / "dev.jsonl")).returncode == 0
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"id": "X1", "category": "nope"}) + "\n", encoding="utf-8")
    proc = _tool("validate", str(bad))
    assert proc.returncode == 1
    assert "X1" in proc.stdout  # each problem line names its case id


@pytest.mark.parametrize(
    ("change", "why"),
    [
        (lambda r: r["source"].update(source_type="blog"), "source_type from the fixed list"),
        (lambda r: r["expect"].update(quran_refs=["2:287"]), "Al-Baqarah has 286 verses"),
        (lambda r: r["expect"].update(quran_refs=["2153"]), "a ref is sura:aya"),
        (lambda r: r["expect"].update(hadith_refs=["blog:12"]), "a known hadith collection"),
        (lambda r: r.update(level="E"), "level is A-D"),
        (lambda r: r.update(text_ar="  "), "text_ar is not empty"),
    ],
)
def test_validate_rejects_each_schema_rule(tmp_path, change, why):
    row = _rows(FIXTURES / "testset" / "dev.jsonl")[0]
    change(row)
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    proc = _tool("validate", str(bad))
    assert proc.returncode == 1, why
    assert row["id"] in proc.stdout


def test_validate_accepts_a_row_without_source_type(tmp_path):
    # Optional: the older seed cases carry no source_type; it is checked only when present.
    row = _rows(FIXTURES / "testset" / "dev.jsonl")[0]
    row["source"].pop("source_type")
    ok = tmp_path / "ok.jsonl"
    ok.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    assert _tool("validate", str(ok)).returncode == 0


def test_split_merges_inputs_and_writes_consistent_files(tmp_path):
    rows = _rows(FIXTURES / "testset" / "dev.jsonl")
    first, extra = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    first.write_text("".join(json.dumps(r) + "\n" for r in rows[:3]), encoding="utf-8")
    extra.write_text("".join(json.dumps(r) + "\n" for r in rows[3:]), encoding="utf-8")
    out = tmp_path / "out"
    proc = _tool("split", "--input", str(first), "--input", str(extra), "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    dev, test, everything = (_rows(out / f) for f in ("dev.jsonl", "test.jsonl", "testset.jsonl"))
    assert sorted(r["id"] for r in dev + test) == sorted(r["id"] for r in everything)
    assert {r["id"] for r in everything} == {r["id"] for r in rows}
    digest = hashlib.sha256((out / "test.jsonl").read_bytes()).hexdigest()
    assert (out / "test.sha256").read_text(encoding="utf-8").split()[0] == digest


def test_split_refuses_to_overwrite_test_without_force(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "test.jsonl").write_text("frozen\n", encoding="utf-8")
    proc = _tool("split", "--input", str(FIXTURES / "testset" / "dev.jsonl"), "--out", str(out))
    assert proc.returncode != 0
    assert (out / "test.jsonl").read_text(encoding="utf-8") == "frozen\n"


def test_split_refuses_invalid_rows(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"id": "X1", "category": "nope"}) + "\n", encoding="utf-8")
    proc = _tool("split", "--input", str(bad), "--out", str(tmp_path / "out"))
    assert proc.returncode != 0
    assert not (tmp_path / "out" / "test.jsonl").exists()


def _frozen_set(tmp_path):
    """A small frozen split (2 dev / 3 test) laid out like data/testset."""
    rows = _rows(FIXTURES / "testset" / "dev.jsonl")
    out = tmp_path / "set"
    out.mkdir()
    lines = [json.dumps(r, ensure_ascii=False) + "\n" for r in rows]
    (out / "testset.jsonl").write_text("".join(lines), encoding="utf-8")
    (out / "dev.jsonl").write_text("".join(lines[:2]), encoding="utf-8")
    (out / "test.jsonl").write_text("".join(lines[2:]), encoding="utf-8")
    digest = hashlib.sha256((out / "test.jsonl").read_bytes()).hexdigest()
    (out / "test.sha256").write_text(digest + "\n", encoding="utf-8")
    new = [dict(r, id=f"N{i}") for i, r in enumerate(rows)]
    new_file = tmp_path / "new.jsonl"
    new_file.write_text("".join(json.dumps(r) + "\n" for r in new), encoding="utf-8")
    return out, rows, new_file


def test_add_keeps_the_existing_split_and_appends_new_cases(tmp_path):
    out, rows, new_file = _frozen_set(tmp_path)
    old = {n: (out / n).read_text(encoding="utf-8") for n in ("dev.jsonl", "test.jsonl")}
    proc = _tool("add", str(new_file), "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    for name, text in old.items():
        assert (out / name).read_text(encoding="utf-8").startswith(text)  # old bytes untouched
    dev_ids = {r["id"] for r in _rows(out / "dev.jsonl")}
    test_ids = {r["id"] for r in _rows(out / "test.jsonl")}
    assert {r["id"] for r in rows[:2]} <= dev_ids
    assert {r["id"] for r in rows[2:]} <= test_ids
    assert dev_ids | test_ids == {r["id"] for r in _rows(out / "testset.jsonl")}
    assert len(dev_ids | test_ids) == 2 * len(rows)
    digest = hashlib.sha256((out / "test.jsonl").read_bytes()).hexdigest()
    assert (out / "test.sha256").read_text(encoding="utf-8").split()[0] == digest
    split = json.loads((out / "split.json").read_text(encoding="utf-8"))["split"]
    assert set(split) == dev_ids | test_ids


def test_add_refuses_a_changed_test_file(tmp_path):
    out, _rows_, new_file = _frozen_set(tmp_path)
    (out / "test.jsonl").write_text("tampered\n", encoding="utf-8")
    proc = _tool("add", str(new_file), "--out", str(out))
    assert proc.returncode != 0
    assert "N0" not in (out / "testset.jsonl").read_text(encoding="utf-8")
