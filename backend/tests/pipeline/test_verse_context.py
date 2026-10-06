"""D-051: text next to a quoted verse is never dropped behind the verse's translation.

The Quran handler outputs the approved translation of the verse only. Before the fix,
commentary in the same clause as a bracketed verse («… وهذا يعني») vanished from the output while the segment
passed as certain (confidence 1.0, not in review).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.llm.base import LLMResult
from app.pipeline import cache, orchestrator
from app.pipeline.budget import DailyBreaker, RequestLimits
from app.pipeline.classifier import classify
from app.pipeline.quran import has_extra_text, lead_in_start, resolve_quran
from app.pipeline.report import load_messages
from app.pipeline.segmenter import segment
from app.schemas import TranslateRequest

DATA = Path(__file__).resolve().parents[3] / "data"
VERSE = "﴿وما أرسلناك إلا رحمة للعالمين﴾"
SAHEEH_21_107 = "﴿And We have not sent you, [O Muḥammad], except as a mercy to the worlds.﴾"
COMMENTARY = "وهذا يدل على رحمة الإسلام"


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
    ("text", "expected"),
    [
        (
            f"قال الله تعالى: {VERSE} {COMMENTARY}.",
            [f"قال الله تعالى: {VERSE}", f"{COMMENTARY}."],
        ),
        (
            f"الصبر خلق عظيم كما قال تعالى: {VERSE} [الأنبياء: 107] فاصبر",
            ["الصبر خلق عظيم", f"كما قال تعالى: {VERSE} [الأنبياء: 107]", "فاصبر"],
        ),
        (
            f"قال تعالى {VERSE} وقال ﴿الحمد لله رب العالمين﴾",
            [f"قال تعالى {VERSE}", "وقال ﴿الحمد لله رب العالمين﴾"],
        ),
        # Ends in «الله» with no word of speech: the sentence keeps every word.
        (f"توكل على الله {VERSE}", ["توكل على الله", VERSE]),
        (f"ما معنى قوله تعالى {VERSE}؟", ["ما معنى", f"قوله تعالى {VERSE}؟"]),
    ],
)
def test_verse_is_its_own_segment_with_its_lead_in(text, expected):
    assert segment(text) == expected


def test_punctuation_never_becomes_a_segment():
    assert segment(f": {VERSE} .") == [f": {VERSE} ."]


def test_lead_in_needs_a_word_of_speech():
    assert lead_in_start("نتأمل قوله تعالى: ") == len("نتأمل ")
    assert lead_in_start("توكل على الله ") == len("توكل على الله ")
    assert lead_in_start(" و") == 1


def test_commentary_after_a_verse_is_translated_and_the_verse_stays_certain():
    response, router = _translate(f"قال الله تعالى: {VERSE} {COMMENTARY}.")
    verse, commentary = response.segments
    assert (verse.type, verse.output, verse.confidence) == ("quran", SAHEEH_21_107, 1.0)
    # «الإسلام» is a glossary term; either way the localizer translates it.
    assert commentary.type in ("general", "term_heavy")
    assert commentary.output == "x"
    assert router.calls > 0
    assert 1 not in response.review_queue


@pytest.mark.parametrize(
    "text",
    [
        f"قال الله تعالى: (وما أرسلناك إلا رحمة للعالمين) {COMMENTARY}",
        f"{COMMENTARY} قال الله تعالى وما أرسلناك إلا رحمة للعالمين",
    ],
)
def test_verse_with_words_around_it_keeps_its_translation_and_is_reviewed(text):
    # Plain parentheses or no brackets: the segmenter cannot split, so the segment is reviewed.
    response, _router = _translate(text)
    segment_ = response.segments[0]
    assert segment_.output == SAHEEH_21_107
    assert segment_.confidence == 0.0
    assert response.review_queue == [1]
    texts = [(flag.severity, flag.text) for flag in segment_.flags]
    assert ("warn", load_messages()["low_confidence"]) in texts


def test_two_verses_in_one_quran_segment_are_reviewed():
    result = resolve_quran(f"{VERSE} ﴿الحمد لله رب العالمين﴾", "en")
    assert result["review"] is True
    assert "quran_extra_text" in [flag.key for flag in result["flags"]]


def test_lead_in_and_sura_reference_are_not_extra_text():
    assert not has_extra_text("قال الله تعالى:  [الأنبياء: 107].")
    assert not has_extra_text("وقال عز وجل في كتابه العزيز  (سورة الأنبياء: ١٠٧)")
    assert has_extra_text(f" {COMMENTARY}")


def _texts() -> list[str]:
    dev = (DATA / "testset" / "dev.jsonl").read_text(encoding="utf-8").splitlines()
    demo = json.loads((DATA / "demo" / "examples.json").read_text(encoding="utf-8"))["items"]
    return [json.loads(line)["text_ar"] for line in dev if line.strip()] + [
        item["text_ar"] for item in demo
    ]


def test_no_dev_or_demo_verse_is_flagged_for_extra_text():
    for text in _texts():
        for part in segment(text):
            if classify(part)["category"] == "quran":
                for lang in ("en", "fr"):
                    keys = [flag.key for flag in resolve_quran(part, lang)["flags"]]
                    assert "quran_extra_text" not in keys, part
