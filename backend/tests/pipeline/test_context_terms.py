"""D-058 (code audit item 6): the avoid words of every detected term are checked.

The 7 ``context`` terms (islam, ihsan, jannah, hikmah, fitnah, ayah, dhikr) are not locked,
because another sense may be meant, so their avoid words («garden» for الجنة, «meditation»
for الذكر) were never checked and a wrong rendering passed the term check.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from app.llm.base import LLMResult
from app.pipeline import cache, orchestrator
from app.pipeline.budget import DailyBreaker, RequestLimits
from app.pipeline.glossary import get_index
from app.pipeline.report import load_messages
from app.pipeline.verifier import _term_check
from app.schemas import LockedTerm, TranslateRequest

CONTEXT_TERMS = sorted(
    term_id for term_id, entry in get_index().entries.items() if entry["strategy"] == "context"
)


class OutputRouter:
    """Localizer returns ``output``; back-translation and judge agree fully."""

    def __init__(self, output: str, source: str) -> None:
        self.output, self.source, self.prompts = output, source, []

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        self.prompts.append(prompt)
        name = schema.__name__
        if name == "TranslationOutput":
            return LLMResult(data=schema(output=self.output))
        if name == "BackTranslation":
            return LLMResult(data=schema(arabic_text=self.source))
        return LLMResult(data=schema(score=1.0))


def test_the_seven_context_terms():
    assert CONTEXT_TERMS == ["ayah", "dhikr", "fitnah", "hikmah", "ihsan", "islam", "jannah"]


@pytest.mark.parametrize("term_id", CONTEXT_TERMS)
@pytest.mark.parametrize("lang", ["en", "fr"])
def test_avoid_word_of_a_context_term_fails_the_term_check(term_id, lang):
    entry = get_index().entries[term_id]
    word = entry[lang]["avoid"][0]
    score, _marks, flags = _term_check(f"It is about {word} here.", lang, [], [term_id])
    assert score == 0.0
    assert [(f.key, f.detail) for f in flags] == [("avoid_word_found", f"{entry['ar']}|{word}")]


def test_context_term_in_another_sense_is_not_a_fault():
    # Not locked: «beneficence» (ihsan said of Allah) is not «ihsan», and is not avoided.
    assert _term_check("Allah's beneficence", "en", [], ["ihsan"]) == (1.0, [], [])


def test_avoid_word_asked_for_by_another_term_is_not_a_fault():
    # «charity» is avoided for ihsan, and is the gloss of sadaqah.
    sadaqah = LockedTerm(ar="الصدقة", out="sadaqah", glossary_id="sadaqah")
    result = _term_check("Ihsan and sadaqah (charity).", "en", [sadaqah], ["ihsan", "sadaqah"])
    assert result == (1.0, ["sadaqah"], [])


def test_wrong_rendering_through_the_pipeline_is_reviewed():
    source = "يرجو المؤمن الجنة"
    cache.clear()
    router = OutputRouter("The believer hopes for the garden.", source)
    req = TranslateRequest(text=source, target_lang="en", mode="localize")
    response = asyncio.run(
        orchestrator.translate(req, router, RequestLimits(daily=DailyBreaker(1000)))
    )
    segment = response.segments[0]
    assert segment.type == "term_heavy"
    assert segment.confidence < 0.75
    assert response.review_queue == [1]
    avoid_text = load_messages()["avoid_word_found"].replace("{term}", "الجنة")
    assert any(f.text == avoid_text.replace("{word}", "garden") for f in segment.flags)
    # The model was told the approved rendering of the usual sense.
    assert "the approved rendering of its usual sense is 'paradise" in router.prompts[0]
