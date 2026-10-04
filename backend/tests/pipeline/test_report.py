"""report.py: the review rule shared with the client, flag rendering, disclosure."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import app.pipeline.report as report_module
from app.pipeline.report import (
    DISCLOSURE,
    MessageKeyError,
    assemble,
    load_messages,
    needs_review,
    render_flag,
)
from app.schemas import Flag, Segment, SegmentFlag

REPO = Path(__file__).resolve().parents[3]
API_JS = REPO / "frontend" / "src" / "lib" / "api.js"

# Every key a Phase 2c/2d stage can emit, with a sample detail for its placeholders.
EMITTED = {
    "quran_from_approved": "",
    "quran_mismatch": "2:153|نص الآية",
    "quran_not_found": "",
    "quran_ambiguous": "55:13, 55:16",
    "quran_translation_pending": "",
    "quran_diacritized": "49:10|إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ",
    "hadith_sourced": "",
    "hadith_unsourced": "",
    "hadith_fabricated": "موضوع",
    "fatwa_referral": "",
}


def _seg(confidence: float, *severities: str) -> Segment:
    flags = [SegmentFlag(severity=s, text="x") for s in severities]  # type: ignore[arg-type]
    return Segment(id=1, confidence=confidence, flags=flags)


def test_review_rule_matches_api_js():
    """review_queue rule: confidence below 0.75 OR any warn/block flag, exactly as needsReview()
    in frontend/src/lib/api.js. If the client rule changes, this test must change with it."""
    js = API_JS.read_text(encoding="utf-8")
    expected = (
        "export const needsReview = (s) => (s.confidence != null && s.confidence < 0.75)"
        " || s.flags.some((f) => f.severity !== 'info')"
    )
    assert expected in js


@pytest.mark.parametrize(
    ("confidence", "severities", "review"),
    [
        (0.75, (), False),
        (0.7499, (), True),
        (0.0, (), True),
        (1.0, ("info",), False),
        (1.0, ("info", "info"), False),
        (1.0, ("warn",), True),
        (1.0, ("block",), True),
        (0.9, ("info", "warn"), True),
    ],
)
def test_needs_review_truth_table(confidence, severities, review):
    assert needs_review(_seg(confidence, *severities)) is review


def test_assemble_queue_summary_and_disclosure():
    segments = [
        Segment(id=1, confidence=0.95),
        Segment(id=2, confidence=0.5),
        Segment(id=3, confidence=0.9, flags=[SegmentFlag(severity="warn", text="x")]),
    ]
    body = assemble(segments)
    assert body.review_queue == [2, 3]
    assert body.summary.segments == 3
    assert body.summary.flagged == 2
    assert body.summary.avg_confidence == 0.78
    assert body.disclosure == DISCLOSURE


def test_assemble_empty():
    body = assemble([])
    assert body.review_queue == []
    assert body.summary.avg_confidence == 0.0


def test_disclosure_is_the_contract_string():
    """The fixed §4 string, identical to the one the frontend falls back to."""
    assert DISCLOSURE in (REPO / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert f"'{DISCLOSURE}'" in API_JS.read_text(encoding="utf-8")


@pytest.mark.parametrize(("key", "detail"), EMITTED.items())
def test_every_emitted_key_has_a_message_and_fills_placeholders(key, detail):
    flag = render_flag(Flag(type="warn", key=key, detail=detail))
    assert flag.text
    assert not re.search(r"\{[a-z_]+\}", flag.text)
    assert flag.severity == "warn"


def test_text_comes_from_flags_ar_json():
    assert render_flag(Flag(key="hadith_unsourced")).text == load_messages()["hadith_unsourced"]


def test_placeholders_filled_with_detail():
    mismatch = render_flag(Flag(type="block", key="quran_mismatch", detail="2:153|نص الآية"))
    assert "2:153" in mismatch.text
    assert "نص الآية" in mismatch.text
    ambiguous = render_flag(Flag(key="quran_ambiguous", detail="55:13, 55:16"))
    assert "55:13, 55:16" in ambiguous.text
    assert render_flag(Flag(key="hadith_fabricated", detail="موضوع")).text.count("موضوع") == 1


def test_slot_text_in_msg_is_used_verbatim():
    assert render_flag(Flag(type="info", key="any", msg="نص من ملف")).text == "نص من ملف"


def test_unknown_key_raises():
    with pytest.raises(MessageKeyError):
        render_flag(Flag(key="no_such_key"))


def test_unfilled_placeholder_raises(monkeypatch):
    monkeypatch.setattr(report_module, "load_messages", lambda: {"needs_ref": "انظر {ref}"})
    with pytest.raises(MessageKeyError):
        render_flag(Flag(key="needs_ref"))


@pytest.mark.parametrize("key", ["limit_reached", "injection_suspected", "raw_unprotected"])
def test_phase_sec_flags_show_their_own_text(key):
    """The three Phase SEC keys now have their own message, not the fallback one."""
    text = render_flag(Flag(type="warn", key=key)).text
    assert text == load_messages()[key]
    assert text
