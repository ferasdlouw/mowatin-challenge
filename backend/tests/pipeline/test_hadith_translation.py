"""Sourced hadith = meaning translation with source + grade; unsourced/fabricated = null + review."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

import app.pipeline.hadith as hadith_module
from app.llm.base import LLMResult, Usage
from app.pipeline import cache, orchestrator
from app.pipeline.hadith import load_items
from app.pipeline.report import load_messages
from app.schemas import TranslateRequest

# Holds the locked renderings of «الرسول» and «النية» from the glossary.
MEANING = "The messenger of God said: deeds are judged by intention."
SOURCED_TEXT = "قال رسول الله ﷺ: «إنما الأعمال بالنيات»."
UNSOURCED_TEXT = "قال النبي ﷺ: «اطلبوا العلم من المهد إلى اللحد»."
FABRICATED_TEXT = "قال النبي ﷺ: «اطلبوا العلم ولو في الصين»."
MIXED_TEXT = "قال النبي ﷺ: «إنما الأعمال بالنيات» و«اطلبوا العلم من المهد إلى اللحد»."

# Shapes from data/CONTENT_SLOTS.md §2; fixtures only, never shipped as content.
SOURCED = {
    "status": "verified",
    "items": [
        {
            "id": "h_niyyat",
            "text_ar": "إنما الأعمال بالنيات",
            "collection": "bukhari",
            "number": "1",
            "grade": "صحيح",
        }
    ],
}
FABRICATED = {
    "status": "verified",
    "items": [{"id": "f_china", "text_ar": "اطلبوا العلم ولو في الصين", "ruling": "موضوع"}],
}


class FakeRouter:
    """Answers by schema name and records each schema asked for; ``None`` = failed call."""

    def __init__(self, translation: str | None = MEANING) -> None:
        self.translation = translation
        self.calls: list[str] = []

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult:
        self.calls.append(schema.__name__)
        answers = {
            "TranslationOutput": {"output": self.translation} if self.translation else None,
            "BackTranslation": {"arabic_text": "إنما الأعمال بالنيات"},
            "JudgeOutput": {"score": 1},
        }
        answer = answers.get(schema.__name__)
        data = schema.model_validate(answer) if answer else None
        return LLMResult(data=data, provider="fake", model="fake", usage=Usage())


@pytest.fixture(autouse=True)
def slots(monkeypatch, tmp_path):
    (tmp_path / "hadith.json").write_text(json.dumps(SOURCED), encoding="utf-8")
    (tmp_path / "fabricated.json").write_text(json.dumps(FABRICATED), encoding="utf-8")
    monkeypatch.setattr(hadith_module, "HADITH_DIR", tmp_path)
    load_items.cache_clear()
    cache.clear()
    yield
    load_items.cache_clear()
    cache.clear()


async def _translate(text: str, router: FakeRouter):
    req = TranslateRequest(text=text, target_lang="en", mode="localize")
    return await orchestrator.translate(req, router)


def _texts(seg) -> list[str]:
    return [f.text for f in seg.flags]


async def test_sourced_hadith_gets_meaning_translation_with_source_and_grade():
    router = FakeRouter()
    resp = await _translate(SOURCED_TEXT, router)
    seg = resp.segments[0]
    assert seg.type == "hadith"
    assert seg.output == MEANING
    hadith_sources = [s for s in seg.sources if s.kind == "hadith"]
    assert [(s.ref, s.grade) for s in hadith_sources] == [("bukhari 1", "صحيح")]
    assert load_messages()["hadith_sourced"] in _texts(seg)
    assert all(f.severity == "info" for f in seg.flags)
    assert {t.glossary_id for t in seg.locked_terms} == {"rasul", "niyyah"}  # term lock applies
    # Localizer, then the verifier's back-translation (judge unset here).
    assert router.calls[:2] == ["TranslationOutput", "BackTranslation"]
    assert 0 < seg.confidence < 0.75  # no judge: verified but still sent to review (D-021)


async def test_sourced_hadith_without_llm_data_stays_null():
    seg = (await _translate(SOURCED_TEXT, FakeRouter(translation=None))).segments[0]
    assert seg.output is None
    assert seg.confidence == 0.0
    assert seg.sources[0].grade == "صحيح"


@pytest.mark.parametrize(
    ("text", "severity"),
    [(UNSOURCED_TEXT, "warn"), (FABRICATED_TEXT, "block"), (MIXED_TEXT, "warn")],
    ids=["unsourced", "fabricated", "mixed-sourced-and-unsourced"],
)
async def test_unsourced_or_fabricated_hadith_stays_null_and_in_review(text, severity):
    router = FakeRouter()
    resp = await _translate(text, router)
    seg = resp.segments[0]
    assert seg.type == "hadith"
    assert seg.output is None
    assert any(f.severity == severity for f in seg.flags)
    assert seg.id in resp.review_queue
    assert router.calls == []  # never sent to the LLM
