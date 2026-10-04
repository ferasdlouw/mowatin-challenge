"""fatwa_guard.py: level D, warn referral flag, optional referral advice from referral.json."""

from __future__ import annotations

import json

import pytest

import app.pipeline.fatwa_guard as guard_module
from app.pipeline.fatwa_guard import (
    LEVEL,
    REFERRAL_PATH,
    referral_flags,
    referral_message_ar,
    referral_text,
)
from app.pipeline.report import needs_review, render_flag
from app.schemas import Segment


@pytest.fixture()
def referral(monkeypatch, tmp_path):
    """Point the guard at a tmp referral.json; returns a writer."""
    path = tmp_path / "referral.json"

    def write(data: dict) -> None:
        path.write_text(json.dumps(data), encoding="utf-8")
        referral_message_ar.cache_clear()
        referral_text.cache_clear()

    monkeypatch.setattr(guard_module, "REFERRAL_PATH", path)
    yield write
    referral_message_ar.cache_clear()
    referral_text.cache_clear()


def test_level_is_d():
    assert LEVEL == "D"


def test_placeholder_slot_gives_one_warn_flag(referral):
    referral({"status": "placeholder", "message": {"ar": "", "en": "", "fr": ""}})
    assert [(f.type, f.key) for f in referral_flags()] == [("warn", "fatwa_referral")]


def test_missing_slot_gives_one_warn_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(guard_module, "REFERRAL_PATH", tmp_path / "absent.json")
    referral_message_ar.cache_clear()
    try:
        assert len(referral_flags()) == 1
    finally:
        referral_message_ar.cache_clear()


def test_filled_slot_adds_info_flag_verbatim(referral):
    referral({"status": "draft", "message": {"ar": " نص الإحالة من الملف ", "en": "x", "fr": "x"}})
    flags = [render_flag(f) for f in referral_flags()]
    assert [f.severity for f in flags] == ["warn", "info"]
    assert flags[1].text == "نص الإحالة من الملف"


def test_referral_flags_always_put_segment_in_review(referral):
    referral({"status": "draft", "message": {"ar": "نص", "en": "", "fr": ""}})
    flags = [render_flag(f) for f in referral_flags()]
    assert needs_review(Segment(id=1, confidence=1.0, flags=flags))


_BODIES = {
    "en": [{"name": "Body EN", "country": "UK", "url": "https://en.example"}],
    "fr": [
        {"name": "Instance FR", "country": "France", "url": "https://fr.example"},
        {"name": "", "country": "France", "url": "https://skipped.example"},
    ],
}


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("en", "Ask a scholar.\n- Body EN (UK): https://en.example"),
        ("fr", "Demandez à un savant.\n- Instance FR (France): https://fr.example"),
    ],
)
def test_referral_text_is_target_message_then_bodies(referral, lang, expected):
    referral(
        {
            "status": "draft",
            "message": {"ar": "نص", "en": " Ask a scholar. ", "fr": "Demandez à un savant."},
            "bodies": _BODIES,
        }
    )
    assert referral_text(lang) == expected


def test_referral_text_is_empty_without_target_message(referral):
    referral({"status": "draft", "message": {"ar": "نص", "en": "", "fr": ""}, "bodies": _BODIES})
    assert referral_text("en") == ""


def test_referral_text_is_empty_for_placeholder_slot(referral):
    referral({"status": "placeholder", "message": {"ar": "", "en": "x", "fr": "x"}})
    assert referral_text("fr") == ""


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_slot_on_main_gives_message_and_every_body(lang):
    """Rudaina's referral.json loads for both targets with her message and all her bodies."""
    data = json.loads(REFERRAL_PATH.read_text(encoding="utf-8"))
    if data.get("status") == "placeholder":
        pytest.skip("referral slot is a placeholder")
    referral_text.cache_clear()
    text = referral_text(lang)
    assert text.splitlines()[0] == data["message"][lang].strip()
    assert data["bodies"][lang]
    for body in data["bodies"][lang]:
        assert body["url"].startswith("https://")
        assert f"- {body['name']} ({body['country']}): {body['url']}" in text.splitlines()
