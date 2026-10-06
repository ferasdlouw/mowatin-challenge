"""D-068: a hadith written without «…» is still checked against the lists.

Before, a saying after an attribution phrase but outside «…» was never looked up (an approved
hadith lost its source, a fabricated one its block), «أن النبي ﷺ قال» was not an attribution
at all, and a fabricated saying with no attribution went to the LLM as plain text.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from app.llm.base import LLMResult
from app.pipeline import cache, orchestrator
from app.pipeline.budget import DailyBreaker, RequestLimits
from app.pipeline.classifier import classify
from app.pipeline.hadith import resolve_hadith, unsourced_quotes
from app.pipeline.segmenter import segment
from app.schemas import TranslateRequest


def _flags(text: str) -> list[tuple[str, str]]:
    return [(flag.type, flag.key) for flag in resolve_hadith(text)[1]]


@pytest.mark.parametrize(
    "text",
    [
        "قال رسول الله ﷺ: الدين النصيحة",
        "قال عليه الصلاة والسلام: الدين النصيحة",
        "عن تميم الداري أن النبي ﷺ قال: الدين النصيحة",
        "الدين النصيحة",
    ],
)
def test_approved_hadith_without_guillemets_keeps_its_source(text):
    assert classify(text)["category"] == "hadith"
    sources, _ = resolve_hadith(text)
    assert [s.ref for s in sources] == ["muslim 55"]
    assert _flags(text) == [("info", "hadith_sourced")]


@pytest.mark.parametrize(
    "text",
    [
        "قال النبي ﷺ: اطلبوا العلم ولو في الصين",
        "اطلبوا العلم ولو في الصين",
        "كما يقولون: اطلبوا العلم ولو في الصين، فالعلم مهم",
    ],
)
def test_fabricated_saying_is_blocked_with_or_without_attribution(text):
    first = segment(text)[0]
    assert classify(first)["category"] == "hadith"
    assert ("block", "hadith_fabricated") in _flags(first)


def test_unknown_saying_after_a_formula_is_the_quote_dorar_is_asked_about():
    text = "عن عمر رضي الله عنه أن النبي ﷺ قال: إنما الأعمال بالنيات"
    assert classify(text)["category"] == "hadith"
    assert _flags(text) == [("warn", "hadith_unsourced")]
    assert unsourced_quotes(text) == ["انما الاعمال بالنيات"]


@pytest.mark.parametrize(
    "text",
    [
        "تحدثنا عن النبي ﷺ وسيرته العطرة",
        "النبي ﷺ قدوة للمسلمين",
        "قال الشيخ إن العلم نور",
        "اطلبوا العلم في كل مكان",
    ],
)
def test_ordinary_speech_about_the_prophet_is_not_a_hadith(text):
    assert classify(text)["category"] != "hadith"


class CountingRouter:
    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        self.calls += 1
        fields = {name: (1.0 if name == "score" else "x") for name in schema.model_fields}
        return LLMResult(data=schema(**fields), provider="fake", model="fake")


def test_bare_fabricated_saying_never_reaches_the_llm():
    cache.clear()
    router = CountingRouter()
    req = TranslateRequest(text="اطلبوا العلم ولو في الصين", mode="localize")
    response = asyncio.run(
        orchestrator.translate(req, router, RequestLimits(daily=DailyBreaker(100)))
    )
    segment = response.segments[0]
    assert (segment.type, segment.output) == ("hadith", None)
    assert router.calls == 0
    assert response.review_queue == [1]
