"""D-060 (code audit item 8): no request outlives its deadline, and the browser waits for it.

Before, the deadline only stopped new calls: a call already running could go on with retries
and failover for ~80 s, so a request took up to ~170 s while the browser gave up at 60 s and
the server kept spending the free quota.
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.config import Settings
from app.llm.base import LLMResult
from app.pipeline import cache, orchestrator
from app.pipeline.budget import DailyBreaker, RequestBudget, RequestLimits
from app.pipeline.report import load_messages
from app.schemas import TranslateRequest

API_JS = Path(__file__).resolve().parents[3] / "frontend" / "src" / "lib" / "api.js"
COLD_START_S = 60


class SlowAfter:
    """The first ``fast`` calls answer at once; every later call hangs for ``hang_s``."""

    def __init__(self, fast: int, hang_s: float) -> None:
        self.fast, self.hang_s, self.calls = fast, hang_s, 0

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        self.calls += 1
        if self.calls > self.fast:
            await asyncio.sleep(self.hang_s)
        fields = {name: (1.0 if name == "score" else "x") for name in schema.model_fields}
        return LLMResult(data=schema(**fields), provider="fake", model="fake")


def _translate(text: str, router: SlowAfter, deadline_s: float):
    cache.clear()
    limits = RequestLimits(deadline_s=deadline_s, daily=DailyBreaker(10_000))
    req = TranslateRequest(text=text, mode="localize")
    started = time.monotonic()
    response = asyncio.run(orchestrator.translate(req, router, limits))
    return response, time.monotonic() - started


def test_a_hanging_call_is_cut_at_the_deadline():
    response, elapsed = _translate("التوحيد أساس الدين.", SlowAfter(fast=0, hang_s=30), 0.3)
    assert elapsed < 2
    segment = response.segments[0]
    assert segment.output is None
    assert response.review_queue == [1]
    assert load_messages()["limit_reached"] in [flag.text for flag in segment.flags]


def test_segments_done_before_the_deadline_are_kept():
    # Segment 1 needs 2 calls (localize + back-translation; no judge configured).
    text = "التوحيد أساس الدين. والصلاة عماد الدين."
    response, elapsed = _translate(text, SlowAfter(fast=2, hang_s=30), 0.5)
    assert elapsed < 2
    first, second = response.segments
    assert first.output == "x"
    assert second.output is None
    assert 2 in response.review_queue


def test_a_cut_response_is_not_cached():
    text = "التوحيد أساس الدين."
    _translate(text, SlowAfter(fast=0, hang_s=30), 0.2)
    key = cache.get_cache_key(text, "en", "general_non_muslim", "localize")
    assert cache.get(key) is None


def test_budget_remaining_and_expire():
    now = [100.0]
    budget = RequestBudget(RequestLimits(deadline_s=5.0), clock=lambda: now[0])
    assert budget.remaining() == 5.0
    now[0] = 107.0
    assert budget.remaining() == 0.0
    budget.expire()
    assert (budget.denied, budget.reason) == (1, "deadline")


def test_the_browser_waits_longer_than_the_server_deadline():
    match = re.search(r"const TIMEOUT_MS = (\d+)", API_JS.read_text(encoding="utf-8"))
    assert match, "TIMEOUT_MS not found in frontend/src/lib/api.js"
    deadline = Settings(_env_file=None).request_deadline_s  # type: ignore[call-arg]
    assert int(match.group(1)) / 1000 >= deadline + COLD_START_S
