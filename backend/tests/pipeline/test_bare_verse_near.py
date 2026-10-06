"""D-053: a verse without brackets or formula never reaches the LLM.

Before the fix, «والعصر ان الانسان لفي خسر» (103:1-2) was plain text because the bare-verse
check looked inside one verse at a time, and the misquote «… لفي صر» went to the LLM, which
translated the verse from memory and silently corrected it.
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
from app.pipeline.quran import contains_bare_verse
from app.schemas import TranslateRequest

DATA = Path(__file__).resolve().parents[3] / "data"


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
    ("text", "ref"),
    [
        ("والعصر إن الإنسان لفي خسر", "103:1-2"),
        ("قل هو الله أحد الله الصمد", "112:1-2"),
    ],
)
def test_bare_quote_across_verses_gets_the_approved_translation(text, ref):
    response, router = _translate(text)
    segment = response.segments[0]
    assert segment.type == "quran"
    assert [(s.kind, s.ref) for s in segment.sources] == [("quran", ref)]
    assert segment.output and segment.output.startswith("﴿")
    assert router.calls == 0
    assert response.review_queue == []


def test_bare_misquote_is_not_sent_to_the_llm():
    # D-054: no LLM; the correct verse's approved translation, a misquote block, review.
    response, router = _translate("والعصر ان الانسان لفي صر")
    segment = response.segments[0]
    assert segment.type == "quran"
    assert segment.output == "﴿By time, Indeed, mankind is in loss,﴾"
    assert any(flag.severity == "block" for flag in segment.flags)
    assert router.calls == 0
    assert response.review_queue == [1]


@pytest.mark.parametrize(
    "text",
    [
        "بسم الله الرحمن الرحيم نبدأ الدرس",
        "إن الله مع الصابرين في كل حال",
        "العقيدة تتعلق بما يعتقده المسلم في الله وملائكته وكتبه ورسله واليوم الآخر",
    ],
)
def test_speech_with_a_quranic_phrase_stays_speech(text):
    assert classify(text)["category"] in ("general", "term_heavy")


def test_no_hadith_or_fabricated_saying_is_taken_for_a_verse():
    for name in ("hadith", "fabricated"):
        items = json.loads((DATA / "hadith" / f"{name}.json").read_text(encoding="utf-8"))
        for item in items["items"]:
            for text in (item["text_ar"], *item.get("variants_ar", [])):
                assert not contains_bare_verse(text), text
