"""Phase SEC Batch 3 (F2, F3): safety guards match canonical text (D-036).

Before the fix a damma, a tatweel or a zero-width joiner inside «ما حكم» skipped the fatwa
referral, and a verse in plain parentheses or a hadith without «» went to the LLM.
"""

from __future__ import annotations

import asyncio
import collections
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.llm.base import LLMResult
from app.pipeline import cache, orchestrator
from app.pipeline.budget import DailyBreaker, RequestLimits
from app.pipeline.classifier import classify
from app.pipeline.glossary import detect
from app.pipeline.normalize import canonicalize_for_matching, strip_format_chars
from app.pipeline.quran import resolve_quran
from app.pipeline.segmenter import segment
from app.schemas import TranslateRequest

DEV = Path(__file__).resolve().parents[3] / "data" / "testset" / "dev.jsonl"
VERSE = "﴿يَا أَيُّهَا الَّذِينَ آمَنُوا اسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ﴾"

ZWSP, ZWJ, RLO, LRI, TAG_A = "\u200b", "\u200d", "\u202e", "\u2066", "\U000e0041"


class CountingRouter:
    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        self.calls += 1
        fields = {name: (1.0 if name == "score" else "x") for name in schema.model_fields}
        return LLMResult(data=schema(**fields), provider="fake", model="fake")


def _translate(text: str) -> tuple[Any, CountingRouter]:
    cache.clear()
    router = CountingRouter()
    limits = RequestLimits(daily=DailyBreaker(10_000))
    req = TranslateRequest(text=text, mode="localize")
    return asyncio.run(orchestrator.translate(req, router, limits)), router


@pytest.mark.parametrize(
    "question",
    [
        "ما حُكم صلاتي؟",
        "ما حكـــم صلاتي؟",
        f"كم زك{ZWJ}اة مالي؟",
        f"هل يجو{ZWSP}ز لي الصلاة هنا؟",
        f"ما ح{RLO}كم صلاتي؟",
        f"ما ح{LRI}كم صلاتي؟",
        f"ما ح{TAG_A}كم صلاتي؟",
        "هَلْ يَجُوزُ لِي أَنْ أُصَلِّيَ هُنَا؟",
    ],
)
def test_marked_or_smuggled_fatwa_question_is_referred(question):
    assert classify(question) == {"category": "fatwa_like", "level": "D"}


def test_ruling_question_with_ha_is_not_taken_for_the_exclusion():
    # Ta marbuta is not unified: «ما حكمه» (its ruling) is not the exclusion «ما حكمة» (wisdom).
    assert classify("ما حكمه؟")["category"] == "fatwa_like"
    assert classify("ما حكمة الصيام؟")["category"] != "fatwa_like"


def test_quoted_verse_with_inna_is_not_a_personal_question():
    assert classify("ما معنى قوله تعالى ﴿إِنَّا أَعْطَيْنَاكَ الْكَوْثَرَ﴾؟")["category"] == "quran"


def test_vocalised_fatwa_sentence_stays_one_segment():
    text = "أنا أعيش في فرنسا، هَلْ يَجُوزُ لِي الجمع بين الصلاتين؟"
    assert segment(text) == [text]


@pytest.mark.parametrize(
    "text",
    [
        "قال الله تعالى: (أعطيناكم الخير كله في هذا اليوم المبارك)",
        "يَقُولُ اللَّهُ تَعَالَى: أعطيناكم الخير كله في هذا اليوم المبارك",
        f"قال الله{ZWSP} تعالى: (أعطيناكم الخير كله في هذا اليوم المبارك)",
        "قال تعالى: (إنا أعطيناك)",
        "قال الله تعالى الحمد لله رب العالمين وفيه فوائد كثيرة",
    ],
)
def test_unbracketed_verse_is_never_sent_to_the_llm(text):
    response, router = _translate(text)
    segment_ = response.segments[0]
    assert segment_.type == "quran"
    assert segment_.output is None
    assert router.calls == 0
    assert any(flag.severity == "warn" for flag in segment_.flags)
    assert response.review_queue == [1]


SAHEEH_21_107 = "﴿And We have not sent you, [O Muḥammad], except as a mercy to the worlds.﴾"


@pytest.mark.parametrize(
    "text",
    [
        "قال الله تعالى: (وما أرسلناك إلا رحمة للعالمين)",
        "يَقُولُ اللَّهُ تَعَالَى: وَمَا أَرْسَلْنَاكَ إِلَّا رَحْمَةً لِّلْعَالَمِينَ",
        f"قال الله{ZWSP} تعالى: (وما أرسلناك إلا رحمة للعالمين)",
        "قال الله تعالى في كتابه العزيز: «وما أرسلناك إلا رحمة للعالمين».",
        "وقال تعالى وما أرسلناك إلا رحمة للعالمين",
    ],
)
def test_unbracketed_verse_gets_the_approved_translation(text):
    # D-041: an attributed verse without ornate brackets is found in the Tanzil text and the
    # approved translation is inserted, exactly as for a bracketed quote. Still no LLM call.
    response, router = _translate(text)
    segment_ = response.segments[0]
    assert segment_.type == "quran"
    assert segment_.output == SAHEEH_21_107
    assert [(s.kind, s.ref) for s in segment_.sources] == [("quran", "21:107")]
    assert router.calls == 0
    assert response.review_queue == []


def test_unbracketed_match_respects_word_boundaries():
    # «سلناك إلا رحمة للعالمين» is inside 21:107 as letters, not as whole words.
    result = resolve_quran("قال الله تعالى: (سلناك إلا رحمة للعالمين)", "en")
    assert result["output"] is None
    assert result["review"] is True


@pytest.mark.parametrize(
    "text",
    [
        "قال رسول الله صلى الله عليه وسلم: النظافة من الإيمان",
        "قال النبي ﷺ: النظافة من الإيمان",
        f"قال رسول{ZWJ} الله: النظافة من الإيمان",
    ],
)
def test_unbracketed_hadith_is_never_presented_as_authentic(text):
    response, router = _translate(text)
    segment_ = response.segments[0]
    assert segment_.type == "hadith"
    assert segment_.output is None
    assert segment_.sources == []
    assert router.calls == 0
    assert any(flag.severity == "warn" for flag in segment_.flags)
    assert response.review_queue == [1]


def test_quoted_hadith_with_smuggled_attribution_is_still_checked():
    assert classify(f"قال رسول{ZWSP} الله: «إنما الأعمال بالنيات»")["category"] == "hadith"


def test_narrative_mention_of_the_prophet_is_not_blocked():
    assert classify("كان النبي ﷺ رحيمًا بالناس.")["category"] in ("term_heavy", "general")


def test_glossary_detection_ignores_format_characters():
    plain = [match["id"] for match in detect("الزكاة ركن")]
    assert plain
    assert [match["id"] for match in detect(f"الزك{ZWJ}اة ركن")] == plain


def test_verse_with_format_characters_still_matches_the_approved_text():
    clean = resolve_quran(VERSE, "en")
    smuggled = resolve_quran(VERSE.replace(" ", f" {ZWSP}").replace("ا", f"ا{LRI}", 1), "en")
    assert clean["sources"]
    assert [s.ref for s in smuggled["sources"]] == [s.ref for s in clean["sources"]]
    assert smuggled["output"] == clean["output"]


def test_canonical_form():
    assert canonicalize_for_matching("ما حُكْمُ") == canonicalize_for_matching("ما حكـم")
    assert canonicalize_for_matching(f"أ{ZWJ}إآٱ") == "اااا"
    assert canonicalize_for_matching("فتوى") == "فتوي"
    assert canonicalize_for_matching("الرَّحْمَٰن") == "الرحمن"
    assert canonicalize_for_matching("صلاة") == "صلاة"
    assert strip_format_chars(f"a{ZWSP}{RLO}{LRI}{TAG_A}b") == "ab"


def test_dev_categories_unchanged():
    counts: collections.Counter[str] = collections.Counter()
    official: collections.Counter[str] = collections.Counter()
    for line in DEV.read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            # O* = official scenarios added to dev on 2026-10-03 (D-040), counted apart.
            target = official if case["id"].startswith("O") else counts
            for part in segment(case["text_ar"]):
                target[classify(part)["category"]] += 1
    # Measured before Phase SEC on the same 44 dev cases (docs/security/AUDIT.md).
    assert dict(counts) == {
        "term_heavy": 30,
        "general": 8,
        "quran": 9,
        "hadith": 7,
        "fatwa_like": 2,
    }
    # O04, O08, O09: none is scripture or a personal ruling question.
    assert dict(official) == {"general": 2, "term_heavy": 2}


def test_bare_verse_gets_the_approved_translation():
    # Issue 7: no attribution formula and no brackets, the whole segment is a verse.
    response, router = _translate("وما أرسلناك إلا رحمة للعالمين")
    segment_ = response.segments[0]
    assert segment_.type == "quran"
    assert segment_.output == SAHEEH_21_107
    assert router.calls == 0


def test_bare_verse_inside_a_sentence_goes_to_review_not_the_llm():
    response, router = _translate(
        "ونتذكر دائما يا أيها الذين آمنوا استعينوا بالصبر والصلاة في كل حين"
    )
    segment_ = response.segments[0]
    assert segment_.type == "quran"
    assert segment_.output is None
    assert router.calls == 0
    assert response.review_queue == [1]


def test_ordinary_sentence_is_not_taken_for_a_verse():
    assert classify("الصبر مفتاح الفرج في كل الأحوال")["category"] != "quran"


@pytest.mark.parametrize("text", ["انما المؤمنون اخوة", "إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ"])
def test_three_word_bare_verse_found_in_one_place_is_the_verse(text):
    # D-047: typed bare, with or without hamza and marks, it is 49:10.
    assert classify(text)["category"] == "quran"


@pytest.mark.parametrize("text", ["إن شاء الله", "ما شاء الله", "في سبيل الله"])
def test_three_word_phrase_found_in_several_verses_stays_speech(text):
    assert classify(text)["category"] != "quran"
