"""D-076: a verse read verbatim from the approved translation is a verified retrieval, and a
quote found in several places is never resolved to one of them by order.

Before: «لا إله إلا الله» (37:35 and 47:19) took 37:35 with «اعتمدنا الموضع 37:35», and every
Quran segment in review scored 0.0, so a verse-only answer showed «متوسط الثقة 0%» next to an
approved translation, with the partial-quote flag reading «درجة الثقة … منخفضة».
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.llm.base import LLMResult
from app.pipeline import cache, orchestrator, quran
from app.pipeline.budget import DailyBreaker, RequestLimits
from app.pipeline.quran import resolve_quran
from app.pipeline.report import assemble, load_messages
from app.pipeline.segmenter import segment
from app.schemas import Segment, TranslateRequest

DATA = Path(__file__).resolve().parents[3] / "data"
AMBIGUOUS = "﴿لا إله إلا الله﴾"
WHOLE_VERSE = "﴿وما أرسلناك إلا رحمة للعالمين﴾"  # 21:107, one place
LABEL_FREE_OF = ("اعتمدنا الموضع",)


def _approved(lang: str, ref: str) -> str:
    data = json.loads((DATA / "quran" / "translations" / f"{lang}.json").read_text("utf-8"))
    return data["verses"][ref]


class FakeRouter:
    """Every LLM call succeeds with a fixed reply; counts the calls."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        self.calls += 1
        fields = {name: (0.6 if name == "score" else "x") for name in schema.model_fields}
        return LLMResult(data=schema(**fields), provider="fake", model="fake")


def _translate(text: str, lang: str = "en") -> tuple[Any, FakeRouter]:
    cache.clear()
    router = FakeRouter()
    req = TranslateRequest(text=text, target_lang=lang, mode="localize")
    limits = RequestLimits(daily=DailyBreaker(10_000))
    return asyncio.run(orchestrator.translate(req, router, limits)), router


# ── Unique verse ─────────────────────────────────────────────────────


def test_unique_whole_verse_is_a_verified_retrieval():
    response, router = _translate(f"قال الله تعالى: {WHOLE_VERSE}")
    seg = response.segments[0]
    assert router.calls == 0
    assert seg.verification == "verified_retrieval"
    assert seg.confidence == 1.0
    assert seg.output == f"﴿{_approved('en', '21:107')}﴾"
    assert [s.ref for s in seg.sources] == ["21:107"]
    assert response.review_queue == []


def test_verse_only_response_never_shows_zero_or_low_confidence():
    # A partial quote of one verse (49:10) is reviewed for coverage, but is not low confidence.
    for text in (WHOLE_VERSE, "﴿إنما المؤمنون إخوة﴾"):
        response, _router = _translate(text)
        seg = response.segments[0]
        assert seg.verification == "verified_retrieval"
        assert seg.confidence == 1.0
        assert response.summary.avg_confidence is None
        texts = [flag.text for flag in seg.flags]
        assert load_messages()["low_confidence"] not in texts


def test_two_verified_verses_leave_the_average_empty_not_zero():
    # «الحمد لله رب العالمين» is in several suras; «قل هو الله أحد» is only 112:1.
    response, _router = _translate(f"قال تعالى {WHOLE_VERSE} وقال ﴿قل هو الله أحد﴾")
    assert [s.verification for s in response.segments] == ["verified_retrieval"] * 2
    assert response.summary.avg_confidence is None


# ── Ambiguous verse (37:35 / 47:19) ──────────────────────────────────


def test_ambiguous_phrase_is_not_resolved_to_one_place():
    result = resolve_quran(AMBIGUOUS, "en")
    assert result["output"] is None
    assert result["sources"] == []
    assert result["review"] is True
    assert result["verification"] == "ambiguous_verse"
    assert [c.ref for c in result["candidates"]] == ["37:35", "47:19"]


def test_each_candidate_carries_its_text_and_approved_translations():
    for candidate in resolve_quran(AMBIGUOUS, "fr")["candidates"]:
        assert "لا اله الا الله" in " ".join(quran._match_words(candidate.ar))
        assert candidate.ar != " ".join(quran._match_words(candidate.ar))  # with tashkeel
        assert candidate.en == _approved("en", candidate.ref)
        assert candidate.fr == _approved("fr", candidate.ref)
        assert candidate.en_edition and candidate.fr_edition


def test_ambiguous_segment_is_reviewed_with_its_own_message():
    response, router = _translate(f"قال تعالى: {AMBIGUOUS}")
    seg = response.segments[0]
    assert router.calls == 0
    assert seg.verification == "ambiguous_verse"
    assert seg.output is None
    assert seg.confidence == 0.0
    assert response.review_queue == [seg.id]
    text = next(flag.text for flag in seg.flags if flag.severity == "warn")
    assert text.startswith("هذا النص موجود في أكثر من موضع")
    assert "37:35, 47:19" in text
    assert "المراجع الشرعي" in text
    assert not any(phrase in text for phrase in LABEL_FREE_OF)


# ── Context that leaves one place ────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "ref"),
    [
        (f"قال تعالى: {AMBIGUOUS} (47:19)", "47:19"),
        (f"قال تعالى: {AMBIGUOUS} (٣٧:٣٥)", "37:35"),
        # A word next to the quote that only one place has next to it.
        ("«لا إله إلا الله» واستغفر لذنبك", "47:19"),
        ("إذا قيل لهم «لا إله إلا الله»", "37:35"),
    ],
)
def test_context_in_the_segment_leaves_exactly_one_place(text, ref):
    result = resolve_quran(text, "en")
    assert [s.ref for s in result["sources"]] == [ref]
    assert result["output"] == f"﴿{_approved('en', ref)}﴾"
    assert result["verification"] == "verified_retrieval"
    resolved = next(f for f in result["flags"] if f.key == "quran_context_resolved")
    assert resolved.detail == ref
    # Part of a long verse: inserted, but still reviewed (D-055).
    assert result["review"] is True


@pytest.mark.parametrize(
    "text",
    [
        f"قال تعالى: {AMBIGUOUS} (2:255)",  # a reference that is neither place
        "قال الله: «لا إله إلا الله»",  # words that only introduce a verse
        f"قال تعالى: {AMBIGUOUS} [محمد: 19]",  # sura names are not read (no name list)
    ],
)
def test_context_that_does_not_single_out_a_place_stays_ambiguous(text):
    result = resolve_quran(text, "en")
    assert result["verification"] == "ambiguous_verse"
    assert result["output"] is None


def test_numeric_reference_stays_in_the_verse_segment():
    assert segment(f"قال تعالى: {AMBIGUOUS} (47:19). وهذا أصل التوحيد.") == [
        f"قال تعالى: {AMBIGUOUS} (47:19).",
        "وهذا أصل التوحيد.",
    ]


# ── Misquoted and unmatched verses ───────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "قال الله تعالى: ﴿الْحَمْدُ لِلَّهِ رَبِّ الْمُسْلِمِينَ﴾",  # misquote of 1:2
        "قال الله تعالى: ﴿هذا نص لا يوجد في القرآن الكريم أبدا﴾",  # not found
        "﴿الله مع﴾",  # too short to be a verse
    ],
)
def test_misquoted_or_unmatched_verse_is_never_verified(text):
    response, _router = _translate(text)
    seg = response.segments[0]
    assert seg.verification is None
    assert seg.confidence == 0.0
    assert response.review_queue == [seg.id]
    assert response.summary.avg_confidence == 0.0


# ── Response-level average ───────────────────────────────────────────


def test_mixed_input_average_leaves_out_the_verified_verse_only():
    text = (
        f"قال الله تعالى: {WHOLE_VERSE}. الصبر خلق عظيم. "
        "قال رسول الله ﷺ: «من صام يوم الجمعة دخل الجنة بلا حساب»"
    )
    response, _router = _translate(text)
    by_type = {s.type: s for s in response.segments}
    # «الصبر» is a glossary term, so the plain sentence is term_heavy (LLM + verifier).
    assert set(by_type) == {"quran", "term_heavy", "hadith"}
    assert by_type["quran"].verification == "verified_retrieval"
    # Plain text and hadith keep their own scores; the verse is not counted at 1.0 or 0.0.
    others = [s.confidence for s in response.segments if s.type != "quran"]
    assert response.summary.avg_confidence == round(sum(others) / len(others), 2)
    every = [s.confidence for s in response.segments]
    assert response.summary.avg_confidence != round(sum(every) / len(every), 2)


def test_assemble_average_without_verified_segments_is_unchanged():
    segments = [
        Segment(id=1, confidence=1.0, verification="verified_retrieval"),
        Segment(id=2, confidence=0.9),
        Segment(id=3, confidence=0.8),
        Segment(id=4, confidence=0.0, verification="ambiguous_verse"),
    ]
    body = assemble(segments)
    # The ambiguous verse still counts at 0.0, as any unresolved segment does.
    assert body.summary.avg_confidence == 0.57
    assert body.review_queue == [4]
