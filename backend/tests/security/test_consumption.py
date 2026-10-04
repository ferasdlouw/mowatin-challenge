"""Phase SEC Batch 2 (F1, NEW-1, NEW-2): LLM fan-out, deadline, daily breaker, Quran near-match CPU.

Before the fix one 4,000-char request ("أ،" repeated 2000 times) made 2,000 segments and 4,000-8,000 routed
LLM calls, and a 20-letter junk "verse" held the event loop for 29 s.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import pytest
from pydantic import BaseModel

import app.pipeline.verifier as verifier_module
from app.llm.base import LLMResult
from app.pipeline import cache, orchestrator
from app.pipeline.budget import DailyBreaker, RequestBudget, RequestLimits
from app.pipeline.quran import resolve_quran
from app.pipeline.segmenter import segment_capped
from app.schemas import TranslateRequest

FLOOD = "أ،" * 2000
MARKER = "سرّي-لا-يُسجَّل"


class CountingRouter:
    """Fake LLM that answers any schema and counts every call it receives."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        self.calls += 1
        fields = {name: (1.0 if name == "score" else "x") for name in schema.model_fields}
        return LLMResult(data=schema(**fields), provider="fake", model="fake")


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture()
def judge(monkeypatch) -> CountingRouter:
    """A configured judge, counted separately from the localizer's router."""
    fake = CountingRouter()
    monkeypatch.setattr(verifier_module, "_judge_router", lambda _router: fake)
    return fake


def _run(text: str, router: CountingRouter, limits: RequestLimits, mode: str = "compare"):
    req = TranslateRequest(text=text, mode=mode)
    return asyncio.run(orchestrator.translate(req, router, limits))


def _flag_texts(segment) -> list[str]:
    return [flag.severity for flag in segment.flags]


@pytest.mark.parametrize("mode", ["localize", "compare", "raw"])
def test_flood_input_makes_at_most_the_call_budget(mode, judge):
    router = CountingRouter()
    limits = RequestLimits(max_segments=6, call_budget=28, daily=DailyBreaker(10_000))
    response = _run(FLOOD, router, limits, mode)
    assert router.calls + judge.calls <= limits.call_budget
    # 6 translated segments + the rest as one untranslated segment in review.
    assert len(response.segments) == 7
    rest = response.segments[-1]
    assert rest.output is None
    assert "warn" in _flag_texts(rest)
    assert rest.id in response.review_queue


def test_judge_calls_count_against_the_request_budget(judge):
    router = CountingRouter()
    limits = RequestLimits(max_segments=6, call_budget=4, daily=DailyBreaker(10_000))
    response = _run("التوحيد أساس الإسلام. الصبر مفتاح الفرج.", router, limits, "localize")
    assert judge.calls >= 1
    assert router.calls + judge.calls <= 4
    # Segment 2 needed calls the budget refused: it is flagged and in review.
    assert response.segments[1].id in response.review_queue


def test_refused_call_fails_safe_to_null_and_review():
    router = CountingRouter()
    limits = RequestLimits(max_segments=6, call_budget=1, daily=DailyBreaker(10_000))
    response = _run("الصبر مفتاح الفرج. والعلم نور.", router, limits, "localize")
    assert router.calls == 1
    second = response.segments[1]
    assert second.output is None
    assert second.confidence == 0.0
    assert "warn" in _flag_texts(second)
    assert second.id in response.review_queue


def test_deadline_stops_new_llm_calls():
    router = CountingRouter()
    limits = RequestLimits(deadline_s=0.0, daily=DailyBreaker(10_000))
    response = _run("الصبر مفتاح الفرج.", router, limits, "localize")
    assert router.calls == 0
    assert response.segments[0].output is None
    assert response.review_queue == [1]


def test_daily_breaker_is_shared_across_requests():
    daily = DailyBreaker(limit=3)
    limits = RequestLimits(daily=daily)
    first, second = CountingRouter(), CountingRouter()
    _run("الصبر مفتاح الفرج.", first, limits, "raw")
    _run("والعلم نور.", second, limits, "raw")
    _run("والحلم زينة.", second, limits, "raw")
    _run("والصدق منجاة.", second, limits, "raw")
    assert first.calls + second.calls == 3


def test_daily_breaker_resets_at_utc_midnight():
    now = [86_400.0 * 100 + 10]
    daily = DailyBreaker(limit=1, clock=lambda: now[0])
    assert daily.take() is True
    assert daily.take() is False
    now[0] += 86_400
    assert daily.take() is True


def test_request_budget_keeps_the_first_refusal_reason():
    budget = RequestBudget(RequestLimits(call_budget=1, daily=DailyBreaker(10)))
    assert budget.allow() is True
    assert budget.allow() is False
    assert budget.reason == "call_budget"
    assert budget.denied == 1


def test_limit_hit_is_logged_without_text(caplog):
    caplog.set_level(logging.INFO, logger="app.pipeline.orchestrator")
    limits = RequestLimits(max_segments=2, daily=DailyBreaker(10_000))
    _run(f"{MARKER}، " * 10, CountingRouter(), limits, "localize")
    lines = [json.loads(r.getMessage()) for r in caplog.records if "limit_hit" in r.getMessage()]
    assert len(lines) == 1
    assert lines[0]["reason"] == "max_segments"
    assert set(lines[0]) == {
        "event",
        "reason",
        "segments",
        "llm_calls",
        "llm_denied",
        "chars",
        "sha256",
    }
    assert all(MARKER not in r.getMessage() for r in caplog.records)


def test_large_response_stays_small_for_the_cache():
    limits = RequestLimits(max_segments=6, daily=DailyBreaker(10_000))
    response = _run(FLOOD, CountingRouter(), limits)
    assert len(response.model_dump_json()) < 20_000


def test_segment_capped_returns_the_untouched_rest():
    text = "أولًا، ثانيًا، ثالثًا. رابعًا؟ خامسًا"
    kept, rest = segment_capped(text, 2)
    assert kept == ["أولًا،", "ثانيًا،"]
    assert rest == "ثالثًا. رابعًا؟ خامسًا"
    assert segment_capped(text, 50)[1] == ""


@pytest.mark.parametrize(
    "junk",
    ["ب" * 20, "ب" * 300, "الله " * 600, "من " * 12, "في " * 30, "الذين امنوا " * 3],
)
def test_quran_near_match_is_cpu_bounded(junk):
    resolve_quran("﴿من من﴾", "en")  # build the index outside the timed call
    started = time.perf_counter()
    result = resolve_quran(f"﴿{junk}﴾", "en")
    assert time.perf_counter() - started < 1.0
    assert result["output"] is None
    assert result["review"] is True


def test_app_builds_limits_from_settings(make_client):
    client = make_client(max_segments=2, llm_call_budget=5, llm_daily_call_budget=7)
    limits = client.app.state.limits
    assert (limits.max_segments, limits.call_budget, limits.daily.limit) == (2, 5, 7)
    body = client.post("/v1/translate", json={"text": "أ، " * 10, "mode": "localize"}).json()
    assert len(body["segments"]) == 3
    assert body["segments"][-1]["output"] is None
