"""Phase SEC Batch 5 (F5, F6, NEW-2): raw mode is never certain; degraded answers are not cached.

Before the fix ``mode=raw`` returned the unprotected LLM translation with confidence 1.0 and no
flag, and a response whose LLM calls had all failed was cached for an hour.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from app.llm.base import LLMResult
from app.pipeline import cache, orchestrator
from app.pipeline.budget import DailyBreaker, RequestLimits
from app.pipeline.cache import LRUCache
from app.schemas import TranslateRequest

VERSE = "﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾"


class FakeRouter:
    """Answers every schema (``ok``) or fails every call (``data=None``)."""

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls = 0

    async def complete_json(self, prompt: str, schema: type[BaseModel]) -> LLMResult[Any]:
        self.calls += 1
        if not self.ok:
            return LLMResult(data=None, error="rate_limited")
        fields = {name: (1.0 if name == "score" else "x") for name in schema.model_fields}
        return LLMResult(data=schema(**fields), provider="fake", model="fake")


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


def _run(text: str, router: FakeRouter, mode: str = "localize", **limits: Any):
    req = TranslateRequest(text=text, mode=mode)
    request_limits = RequestLimits(daily=DailyBreaker(10_000), **limits)
    return asyncio.run(orchestrator.translate(req, router, request_limits))


def test_raw_mode_is_never_certain_and_always_reviewed():
    response = _run(VERSE, FakeRouter(), mode="raw")
    segment = response.segments[0]
    assert segment.output == "x"
    assert segment.confidence == 0.0
    assert [flag.severity for flag in segment.flags] == ["warn"]
    assert response.review_queue == [1]


def test_raw_calls_count_against_the_budget():
    router = FakeRouter()
    _run("أ، " * 50, router, mode="raw", max_segments=6, call_budget=3)
    assert router.calls == 3


def test_failed_llm_response_is_not_cached():
    failing = FakeRouter(ok=False)
    _run("الصبر مفتاح الفرج.", failing)
    healthy = FakeRouter()
    response = _run("الصبر مفتاح الفرج.", healthy)
    assert healthy.calls > 0
    assert response.segments[0].output == "x"


def test_limited_response_is_not_cached():
    first = FakeRouter()
    _run("الصبر مفتاح الفرج. والعلم نور.", first, call_budget=1)
    second = FakeRouter()
    _run("الصبر مفتاح الفرج. والعلم نور.", second)
    assert second.calls > 0


def test_cut_text_response_is_not_cached():
    _run("أ، " * 10, FakeRouter(), max_segments=2)
    again = FakeRouter()
    _run("أ، " * 10, again, max_segments=2)
    assert again.calls > 0


def test_healthy_response_is_cached():
    _run("الصبر مفتاح الفرج.", FakeRouter())
    second = FakeRouter()
    _run("الصبر مفتاح الفرج.", second)
    assert second.calls == 0


def test_cache_is_bounded_by_bytes():
    lru = LRUCache(capacity=100, max_bytes=100)
    lru.set("a", 1, size=60)
    lru.set("b", 2, size=60)
    assert lru.get("a") is None
    assert lru.get("b") == 2
    assert lru.total_bytes == 60
    lru.set("huge", 3, size=101)
    assert lru.get("huge") is None
    lru.clear()
    assert lru.total_bytes == 0


def test_expired_entry_releases_its_bytes():
    now = [0.0]
    lru = LRUCache(ttl_s=1, max_bytes=100, clock=lambda: now[0])
    lru.set("a", 1, size=40)
    now[0] = 2.0
    assert lru.get("a") is None
    assert lru.total_bytes == 0
