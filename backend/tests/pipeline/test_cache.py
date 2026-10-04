"""Response cache: LRU of 1,000 entries with a TTL (default one hour)."""

from __future__ import annotations

from app.pipeline import cache
from app.pipeline.cache import DEFAULT_CAPACITY, DEFAULT_TTL_S, LRUCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_defaults_are_one_hour_and_1000_entries():
    assert DEFAULT_TTL_S == 3600
    assert DEFAULT_CAPACITY == 1000
    assert (cache._cache.ttl_s, cache._cache.capacity) == (3600, 1000)


def test_entry_expires_after_ttl():
    clock = FakeClock()
    lru = LRUCache(capacity=10, clock=clock)
    lru.set("k", "v")
    clock.now += DEFAULT_TTL_S - 1
    assert lru.get("k") == "v"
    clock.now += 1
    assert lru.get("k") is None
    assert "k" not in lru.cache


def test_custom_ttl_and_reset_on_set():
    clock = FakeClock()
    lru = LRUCache(capacity=10, ttl_s=5, clock=clock)
    lru.set("k", "v1")
    clock.now += 4
    lru.set("k", "v2")
    clock.now += 4
    assert lru.get("k") == "v2"
    clock.now += 1
    assert lru.get("k") is None


def test_lru_eviction_still_applies():
    clock = FakeClock()
    lru = LRUCache(capacity=2, clock=clock)
    lru.set("a", 1)
    lru.set("b", 2)
    assert lru.get("a") == 1
    lru.set("c", 3)
    assert lru.get("b") is None
    assert (lru.get("a"), lru.get("c")) == (1, 3)
