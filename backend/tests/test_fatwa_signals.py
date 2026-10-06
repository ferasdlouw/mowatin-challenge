"""Audit item 20 (D-075): fatwa phrases come from data/policy/fatwa_signals.json; a missing or
empty file stops the app instead of letting ruling questions reach the LLM as plain text."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.pipeline import classifier
from app.pipeline.classifier import FatwaSignalsError, classify, is_fatwa_like


@pytest.fixture()
def signals_at(monkeypatch):
    """Point the classifier at another signals file; the real one is restored afterwards."""

    def point(path):
        monkeypatch.setattr(classifier, "FATWA_SIGNALS_PATH", path)
        classifier.load_fatwa_signals.cache_clear()

    yield point
    classifier.load_fatwa_signals.cache_clear()


@pytest.mark.parametrize(
    "text",
    [
        "هل يجوز لي أن أؤخر الصلاة؟",
        "ما حكم صلاة الجماعة؟",
        "هل علي قضاء هذه الأيام؟",
        "في حالتي هذه ماذا أفعل؟",
    ],
)
def test_former_code_phrases_are_found_through_the_data_file(text):
    assert is_fatwa_like(text)
    assert classify(text)["category"] == "fatwa_like"


def test_pending_phrase_still_refers_until_the_owner_decides():
    assert is_fatwa_like("هل يحل للمرأة أن تفعل ذلك؟")


def test_missing_file_is_an_error_not_an_empty_list(signals_at, tmp_path):
    signals_at(tmp_path / "absent.json")
    with pytest.raises(FatwaSignalsError, match="missing"):
        classifier.load_fatwa_signals()


@pytest.mark.parametrize(
    "payload",
    [{"phrases": []}, {"phrases": [{"text_ar": "  "}]}, {"status": "placeholder"}],
)
def test_file_without_a_phrase_is_an_error(signals_at, tmp_path, payload):
    path = tmp_path / "fatwa_signals.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    signals_at(path)
    with pytest.raises(FatwaSignalsError, match="no phrase"):
        classifier.load_fatwa_signals()


def test_app_does_not_start_without_signals(signals_at, tmp_path):
    signals_at(tmp_path / "absent.json")
    app = create_app(Settings(_env_file=None, env="test"))  # type: ignore[call-arg]
    with pytest.raises(FatwaSignalsError), TestClient(app):
        pass
