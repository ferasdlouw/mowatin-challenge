"""Tests for scripts/run_eval.py: frozen-split guard, systems, run files, blind_eval compatibility."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

import httpx
import pytest
import respx
import run_eval as r

from .conftest import API_REQUEST, FIXTURES, REPO

# ── frozen test split ────────────────────────────────────────────────


def _frozen_copy(tmp_path):
    """A fixture test split with its checksum, laid out like data/testset."""
    testset = tmp_path / "testset"
    testset.mkdir()
    shutil.copy(FIXTURES / "testset" / "dev.jsonl", testset / "test.jsonl")
    digest = hashlib.sha256((testset / "test.jsonl").read_bytes()).hexdigest()
    (testset / "test.sha256").write_text(digest + "\n", encoding="utf-8")
    return testset


def test_dev_is_the_default_split():
    assert r.parse_args([]).split == "dev"


def test_test_split_refused_without_confirmation(tmp_path, monkeypatch):
    testset = _frozen_copy(tmp_path)
    opened = []
    monkeypatch.setattr(r.Path, "read_bytes", lambda self: opened.append(self) or b"")
    with pytest.raises(r.FrozenSplitError, match="--i-confirm-frozen"):
        r.resolve_split("test", confirmed=False, testset_dir=testset)
    assert opened == []


def test_cli_refuses_test_split_before_touching_data(tmp_path, capsys):
    missing = tmp_path / "no_data_here"
    with pytest.raises(SystemExit) as exc:
        r.main(["--split", "test", "--data-dir", str(missing), "--out", str(tmp_path / "o")])
    assert "--i-confirm-frozen" in str(exc.value)
    assert not (tmp_path / "o").exists()


def test_test_split_loads_with_confirmation_and_matching_checksum(tmp_path):
    testset = _frozen_copy(tmp_path)
    path = r.resolve_split("test", confirmed=True, testset_dir=testset)
    assert len(r.load_cases(path)) == 5


def test_test_split_refused_when_checksum_differs(tmp_path):
    testset = _frozen_copy(tmp_path)
    (testset / "test.sha256").write_text("0" * 64 + "\n", encoding="utf-8")
    with pytest.raises(r.FrozenSplitError, match="does not match"):
        r.resolve_split("test", confirmed=True, testset_dir=testset)


def test_runs_must_be_positive():
    with pytest.raises(SystemExit):
        r.parse_args(["--runs", "0"])


# ── systems and id mapping ───────────────────────────────────────────


def test_gt_only_with_key():
    assert r.available_systems("") == ["raw", "localize"]
    assert r.available_systems("k") == ["gt", "raw", "localize"]


def test_id_mapping_matches_both_tools():
    assert {s.file_id: s.summary_id for s in r.SYSTEMS.values()} == {
        "gt": "mt",
        "raw": "llm",
        "mowatten": "mowatin",
    }
    summary = json.loads((REPO / "eval/results/summary.json").read_text(encoding="utf-8"))
    assert {s["id"] for s in summary["systems"]} == {s.summary_id for s in r.SYSTEMS.values()}
    blind_tool = (REPO / "scripts/blind_eval.py").read_text(encoding="utf-8")
    assert 'SYSTEMS = ["mt", "llm", "mowatin"]' in blind_tool


def test_api_translator_sends_contract_request(fake_post):
    translate = r.api_translator(fake_post, "localize", "general_non_muslim")
    output, segments = translate("نص تجريبي عن التوحيد", "fr")
    assert fake_post.seen == [
        {
            "text": "نص تجريبي عن التوحيد",
            "target_lang": "fr",
            "audience": "general_non_muslim",
            "mode": "localize",
        }
    ]
    assert output == "Tawhîd is the basis."
    assert segments[0]["type"] == "term_heavy"


def test_api_translator_joins_outputs_and_skips_null():
    def post(_body):
        segments = [{"output": "A."}, {"output": None}, {"output": "B."}]
        return httpx.Response(200, json={"segments": segments}, request=API_REQUEST)

    assert r.api_translator(post, "localize", "youth")("x", "en")[0] == "A. B."


@respx.mock
def test_gt_translator_keeps_key_out_of_url():
    route = respx.post(r.GT_URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"translations": [{"translatedText": "Hello"}]}}
        )
    )
    with httpx.Client() as client:
        output, segments = r.gt_translator(client, "secret-test-key")("مرحبا", "en")
    assert (output, segments) == ("Hello", [])
    sent = route.calls.last.request
    assert "secret-test-key" not in str(sent.url)
    assert sent.headers["X-Goog-Api-Key"] == "secret-test-key"
    assert json.loads(sent.content) == {
        "q": "مرحبا",
        "source": "ar",
        "target": "en",
        "format": "text",
    }


def test_failed_call_becomes_empty_answer(cases):
    def broken(_text, _target):
        raise httpx.ConnectError("down")

    rows, failures = r.run_system(cases[:1], broken)
    assert failures == 2
    assert rows == [
        {"id": "F001", "target": t, "output": "", "segments": []} for t in ("en", "fr")
    ]


# ── end to end on fixtures ───────────────────────────────────────────


def _run(cases, fake_post, out, runs=2):
    translators = {
        name: r.api_translator(fake_post, r.SYSTEMS[name].api_mode, "general_non_muslim")
        for name in ("raw", "localize")
    }
    return r.evaluate(cases, translators, runs, out, FIXTURES)


def test_evaluate_writes_run_files_and_scores(cases, fake_post, tmp_path):
    scores = _run(cases, fake_post, tmp_path)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [
        "mowatten_run1.jsonl",
        "mowatten_run2.jsonl",
        "raw_run1.jsonl",
        "raw_run2.jsonl",
    ]
    rows = [
        json.loads(line) for line in (tmp_path / "raw_run1.jsonl").read_text("utf-8").splitlines()
    ]
    assert len(rows) == 10
    assert all(set(row) == {"id", "target", "output", "segments"} for row in rows)
    assert set(scores) == {"llm", "mowatin"}
    assert len(scores["mowatin"]) == 2
    assert scores["mowatin"][0]["term_accuracy"] == 100.0
    assert scores["mowatin"][0]["scripture_integrity"] == 100.0
    assert scores["llm"][0]["term_accuracy"] == 0.0


def test_format_table_prints_every_metric(cases, fake_post, tmp_path):
    table = r.format_table(_run(cases, fake_post, tmp_path, runs=1))
    for label in (
        "term_accuracy",
        "scripture_integrity",
        "referral_recall",
        "referral_precision",
        "over_referral",
        "errors/100 quran",
        "errors/100 referral",
    ):
        assert label in table
    assert "n/a" in table  # raw never refers, so its precision has no denominator


def test_run_files_are_readable_by_blind_eval(cases, fake_post, tmp_path):
    """run_eval files feed scripts/blind_eval.py: one sheet per language, no cross-language mixups."""
    runs_dir, rating_dir = tmp_path / "runs", tmp_path / "rating"
    _run(cases, fake_post, runs_dir, runs=1)
    raw, mowatten = runs_dir / "raw_run1.jsonl", runs_dir / "mowatten_run1.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "blind_eval.py"),
            "--mt",
            str(raw),  # no GT key in tests: the raw run stands in for the MT file
            "--llm",
            str(raw),
            "--mowatin",
            str(mowatten),
            "--test",
            str(FIXTURES / "testset" / "dev.jsonl"),
            "--lang",
            "en",
            "--outdir",
            str(rating_dir),
        ],
        capture_output=True,
        # The tool prints Arabic: UTF-8 on both ends, or a cp1252 console (Windows) garbles it.
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    key = json.loads((rating_dir / "KEY.json").read_text(encoding="utf-8"))
    assert key["lang"] == "en"
    assert {s for perm in key["key"].values() for s in perm.values()} == {"mt", "llm", "mowatin"}
    sheets = "".join(
        (rating_dir / name).read_text(encoding="utf-8-sig")
        for name in ("shared_sample.csv", "rest.csv")
    )
    assert "Tawhid is the basis." in sheets  # the EN answer of F001
    assert "Tawhîd" not in sheets  # never the FR row of the same case
    assert "(لا يوجد ناتج" in sheets  # a withheld answer (F004, level D) is shown, not an error


def test_cli_dev_run_in_process_against_real_app(tmp_path, monkeypatch, capsys):
    """The real CLI path: in-process FastAPI app (stub pipeline), fixture data, no network."""
    monkeypatch.setenv("GT_API_KEY", "")
    out = tmp_path / "runs"
    r.main(["--data-dir", str(FIXTURES), "--out", str(out), "--runs", "1"])
    printed = capsys.readouterr().out
    assert "failed_calls=0" in printed
    for label in ("term_accuracy", "scripture_integrity", "referral_recall", "over_referral"):
        assert label in printed
    assert sorted(p.name for p in out.iterdir()) == [
        "metrics.json",
        "mowatten_run1.jsonl",
        "raw_run1.jsonl",
    ]
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["split"] == "dev"
    assert set(metrics["systems"]) == {"llm", "mowatin"}


def test_server_error_scores_as_failed_unit(cases):
    def post(_body):
        return httpx.Response(500, json={"error": True}, request=API_REQUEST)

    translate = r.api_translator(post, "localize", "general_non_muslim")
    rows, failures = r.run_system(cases[:1], translate)
    assert failures == 2
    assert all(row["output"] == "" for row in rows)


def test_in_process_run_is_not_rate_limited(monkeypatch):
    """A .env copied from .env.example (30/min) must not turn eval units into 429s."""
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "2")
    post, close = r._in_process_post()
    try:
        codes = [post({"text": "التوحيد", "target_lang": "en"}).status_code for _ in range(5)]
    finally:
        close()
    assert codes == [200] * 5


# ── throttle (--delay) ───────────────────────────────────────────────


def test_delay_defaults_to_zero_and_rejects_negative():
    assert r.parse_args([]).delay == 0.0
    assert r.parse_args(["--delay", "12"]).delay == 12.0
    with pytest.raises(SystemExit):
        r.parse_args(["--delay", "-1"])


def test_throttled_waits_between_requests_not_before_the_first():
    sent, waits = [], []
    post = r.throttled(lambda body: sent.append(body) or httpx.Response(200), 12.0, waits.append)

    for n in range(3):
        post({"n": n})

    assert [b["n"] for b in sent] == [0, 1, 2]
    assert waits == [12.0, 12.0]


def test_zero_delay_returns_the_same_post():
    def post(body):
        return httpx.Response(200)

    assert r.throttled(post, 0.0) is post
