"""Phase 3c: compare baseline (``wrong``/``why``) and the per-request cost log."""

from __future__ import annotations

import json
import logging

import pytest
from pydantic import BaseModel

import app.pipeline.quran as quran_module
import app.pipeline.verifier as verifier_module
from app.llm.base import LLMResult, Usage
from app.pipeline import cache, orchestrator
from app.pipeline.report import load_messages
from app.schemas import TranslateRequest

TERM_TEXT = "التوحيد أساس الإسلام."
HADITH_TEXT = "قال رسول الله ﷺ: «إنما الأعمال بالنيات»."
VERSE_TEXT = "﴿يَا أَيُّهَا الَّذِينَ آمَنُوا اسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ﴾"
USAGE = Usage(prompt_tokens=100, output_tokens=20)
COST = 0.001
LIST_COST = 0.003


class FakeRouter:
    """Answers by schema name; every call reports the same usage and cost."""

    def __init__(self, answers: dict[str, dict]) -> None:
        self.answers = answers

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult:
        data = schema.model_validate(self.answers[schema.__name__])
        return LLMResult(
            data=data,
            provider="fake",
            model="fake",
            usage=USAGE,
            cost_usd=COST,
            list_cost_usd=LIST_COST,
        )


def _router(raw: str, localized: str = "Tawhid is the basis of Islam.") -> FakeRouter:
    answers = {"BackTranslation": {"arabic_text": TERM_TEXT}, "JudgeOutput": {"score": 1}}
    return _LocalizeOrRawRouter(localized, raw, answers)


class _LocalizeOrRawRouter(FakeRouter):
    """Localize and raw share ``TranslationOutput``; raw_v1.txt asks for a plain translation."""

    def __init__(self, localized: str, raw: str, answers: dict[str, dict]) -> None:
        super().__init__(answers)
        self.localized, self.raw = localized, raw

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult:
        if schema.__name__ == "TranslationOutput":
            output = self.raw if "plain translation" in prompt else self.localized
            self.answers["TranslationOutput"] = {"output": output}
        return await super().complete_json(prompt, schema)


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture()
def approved_verse(monkeypatch, tmp_path):
    """A tmp approved EN translation holding 2:153 only."""
    (tmp_path / "en.json").write_text(
        json.dumps({"status": "verified", "edition": "Fixture", "verses": {"2:153": "V."}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(quran_module, "TRANSLATIONS_DIR", tmp_path)
    quran_module.get_index.cache_clear()
    yield
    quran_module.get_index.cache_clear()


async def _compare(text: str, router: FakeRouter):
    req = TranslateRequest(text=text, target_lang="en", mode="compare")
    return (await orchestrator.translate(req, router)).segments[0]


async def test_compare_term_wrong_holds_exact_raw_substring():
    seg = await _compare(TERM_TEXT, _router("Unity is the basis of Islam."))
    expected_why = load_messages()["compare_why_term"]
    expected_why = expected_why.replace("{term}", "التوحيد").replace("{word}", "Unity")
    assert seg.baseline.output == "Unity is the basis of Islam."
    assert seg.baseline.wrong == ["Unity"]
    assert seg.baseline.why == expected_why


async def test_compare_term_avoid_word_inside_another_word_is_not_wrong():
    seg = await _compare(TERM_TEXT, _router("Communityism is the basis of Islam."))
    assert (seg.baseline.wrong, seg.baseline.why) == ([], "")


async def test_compare_quran_machine_translated_verse_is_wrong(approved_verse):
    raw = "O you who have believed, seek help through patience and prayer."
    seg = await _compare(VERSE_TEXT, _router(raw))
    assert seg.type == "quran"
    assert seg.baseline.wrong == [raw]
    assert seg.baseline.why == load_messages()["compare_why_quran"]


async def test_compare_quran_raw_with_approved_text_is_not_wrong(approved_verse):
    seg = await _compare(VERSE_TEXT, _router("V."))
    assert (seg.baseline.wrong, seg.baseline.why) == ([], "")


async def test_compare_hadith_unsourced_attribution_is_wrong():
    raw = 'The Messenger of God said: "Actions are by intentions."'
    seg = await _compare(HADITH_TEXT, _router(raw))
    assert seg.type == "hadith"
    assert seg.baseline.wrong == [raw]
    assert seg.baseline.why == load_messages()["compare_why_hadith"]


def _cost_records(caplog) -> list[dict]:
    return [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == "app.pipeline.orchestrator" and "request_cost" in r.getMessage()
    ]


async def test_request_cost_is_aggregated_and_logged_without_text(caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    judge = FakeRouter({"JudgeOutput": {"score": 1}})
    monkeypatch.setattr(verifier_module, "_judge_router", lambda _router: judge)
    raw = "Unity is the basis of Islam."
    await _compare(TERM_TEXT, _router(raw))

    (record,) = _cost_records(caplog)
    # localize + back-translation + judge + raw baseline
    assert record["llm_completions"] == 4
    assert record["llm_failed"] == 0
    assert (record["prompt_tokens"], record["output_tokens"]) == (400, 80)
    assert record["cost_usd"] == pytest.approx(4 * COST)
    assert record["list_cost_usd"] == pytest.approx(4 * LIST_COST)
    assert record["cache_hit"] is False
    assert (record["mode"], record["segments"], record["chars"]) == ("compare", 1, len(TERM_TEXT))
    for r in caplog.records:
        message = r.getMessage()
        for secret in (TERM_TEXT, "التوحيد", raw, "Tawhid is the basis"):
            assert secret not in message


async def test_cache_hit_logs_zero_cost(caplog):
    caplog.set_level(logging.INFO)
    req = TranslateRequest(text=TERM_TEXT, target_lang="en", mode="localize")
    await orchestrator.translate(req, _router("unused"))
    await orchestrator.translate(req, _router("unused"))
    first, second = _cost_records(caplog)
    assert first["cache_hit"] is False and first["llm_completions"] == 2
    assert second["cache_hit"] is True and second["llm_completions"] == 0
    assert second["cost_usd"] == 0
    assert second["list_cost_usd"] == 0
