"""request_cost carries per-request speed totals for docs/MODELS.md, and never the text."""

from __future__ import annotations

import json
import logging

import pytest
from pydantic import BaseModel

from app.llm.base import LLMResult, Usage
from app.pipeline import cache, orchestrator
from app.schemas import TranslateRequest

TEXT = "التوحيد أساس الإسلام."
OUTPUT = "CANARY-OUTPUT Tawhid is the basis of Islam."


class _TimedRouter:
    """Every call reports 20 output tokens in 250 ms."""

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult:
        answers = {
            "TranslationOutput": {"output": OUTPUT},
            "BackTranslation": {"arabic_text": TEXT},
            "JudgeOutput": {"score": 1},
        }
        return LLMResult(
            data=schema.model_validate(answers[schema.__name__]),
            usage=Usage(prompt_tokens=100, output_tokens=20),
            latency_ms=250,
        )


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


def _cost_record(caplog: pytest.LogCaptureFixture) -> dict:
    (record,) = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == "app.pipeline.orchestrator" and "request_cost" in r.getMessage()
    ]
    return record


async def test_request_cost_has_latency_total_and_tokens_per_second(caplog) -> None:
    caplog.set_level(logging.INFO)
    req = TranslateRequest(text=TEXT, target_lang="en", mode="localize")

    await orchestrator.translate(req, _TimedRouter())

    record = _cost_record(caplog)
    calls = record["llm_completions"]
    assert calls >= 1
    assert record["llm_latency_ms"] == 250 * calls
    assert record["output_tokens_per_s"] == pytest.approx(80.0)
    for r in caplog.records:
        message = r.getMessage()
        assert TEXT not in message and "التوحيد" not in message and "CANARY" not in message


async def test_request_without_llm_calls_has_no_speed(caplog) -> None:
    caplog.set_level(logging.INFO)
    req = TranslateRequest(text=TEXT, target_lang="en", mode="localize")

    await orchestrator.translate(req, _TimedRouter())
    await orchestrator.translate(req, _TimedRouter())

    records = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == "app.pipeline.orchestrator" and "request_cost" in r.getMessage()
    ]
    cached = records[-1]
    assert cached["cache_hit"] is True
    assert (cached["llm_latency_ms"], cached["output_tokens_per_s"]) == (0, None)
