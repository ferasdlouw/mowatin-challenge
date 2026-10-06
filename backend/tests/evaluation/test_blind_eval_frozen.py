"""Audit item 17: blind_eval reads the sealed test set only with consent and a matching checksum.

A stand-in frozen set in a temp folder is used; the real data/testset/test.jsonl is never read.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import blind_eval
import pytest
from run_eval import FrozenSplitError

from .conftest import FIXTURES, REPO
from .test_run_eval import _run

SEALED = (REPO / "data" / "testset" / "test.jsonl").resolve()


@pytest.fixture(autouse=True)
def never_the_real_test_set(monkeypatch):
    real_read_text, real_read_bytes = Path.read_text, Path.read_bytes

    def guard(read):
        def checked(self, *args, **kwargs):
            assert self.resolve() != SEALED, "the sealed test set was read"
            return read(self, *args, **kwargs)

        return checked

    monkeypatch.setattr(Path, "read_text", guard(real_read_text))
    monkeypatch.setattr(Path, "read_bytes", guard(real_read_bytes))


@pytest.fixture()
def frozen(tmp_path, monkeypatch):
    """A frozen-set folder like data/testset: test.jsonl (fixture cases) + its test.sha256."""
    testset = tmp_path / "testset"
    testset.mkdir()
    shutil.copy(FIXTURES / "testset" / "dev.jsonl", testset / "test.jsonl")
    digest = hashlib.sha256((testset / "test.jsonl").read_bytes()).hexdigest()
    (testset / "test.sha256").write_text(f"{digest}  test.jsonl\n", encoding="utf-8")
    monkeypatch.setattr(blind_eval, "TESTSET_DIR", testset)
    return testset


def _argv(runs: Path, out: Path, *extra: str) -> list[str]:
    raw, mowatten = runs / "raw_run1.jsonl", runs / "mowatten_run1.jsonl"
    base = ["--mt", str(raw), "--llm", str(raw), "--mowatin", str(mowatten)]
    return [*base, "--lang", "en", "--outdir", str(out), *extra]


def test_the_real_default_is_refused_without_consent():
    with pytest.raises(FrozenSplitError, match="--i-confirm-frozen"):
        blind_eval.source_path(str(SEALED), confirmed=False)


def test_frozen_set_needs_consent(frozen, cases, fake_post, tmp_path):
    _run(cases, fake_post, tmp_path / "runs", runs=1)
    with pytest.raises(FrozenSplitError, match="--i-confirm-frozen"):
        blind_eval.main(_argv(tmp_path / "runs", tmp_path / "out"))
    assert not (tmp_path / "out").exists()


def test_frozen_set_with_consent_and_matching_checksum_is_rated(
    frozen, cases, fake_post, tmp_path
):
    _run(cases, fake_post, tmp_path / "runs", runs=1)
    blind_eval.main(_argv(tmp_path / "runs", tmp_path / "out", "--i-confirm-frozen"))
    assert (tmp_path / "out" / "KEY.json").exists()


def test_changed_frozen_set_is_refused_even_with_consent(frozen, cases, fake_post, tmp_path):
    _run(cases, fake_post, tmp_path / "runs", runs=1)
    with (frozen / "test.jsonl").open("a", encoding="utf-8") as f:
        f.write("\n")
    with pytest.raises(FrozenSplitError, match=r"test\.sha256"):
        blind_eval.main(_argv(tmp_path / "runs", tmp_path / "out", "--i-confirm-frozen"))
    assert not (tmp_path / "out").exists()


def test_another_file_needs_no_consent(cases, fake_post, tmp_path):
    _run(cases, fake_post, tmp_path / "runs", runs=1)
    test_arg = str(FIXTURES / "testset" / "dev.jsonl")
    blind_eval.main(_argv(tmp_path / "runs", tmp_path / "out", "--test", test_arg))
    assert (tmp_path / "out" / "KEY.json").exists()
