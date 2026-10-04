"""In-memory LRU response cache with a TTL, keyed by hash(text, lang, audience, mode)."""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("app.pipeline.cache")

DEFAULT_CAPACITY = 1000
# One hour: a demo session reuses answers, while glossary or slot updates show up the same day.
DEFAULT_TTL_S = 3600.0
# Memory bound (D-039): a free Render instance has 512 MB; entries are counted by JSON size.
DEFAULT_MAX_BYTES = 64 * 1024 * 1024


class LRUCache:
    """Least-recently-used eviction plus expiry; an entry older than ``ttl_s`` is a miss.

    Bounded by ``capacity`` entries and by ``max_bytes`` of the sizes given to ``set``.
    """

    def __init__(
        self,
        capacity: int = DEFAULT_CAPACITY,
        ttl_s: float = DEFAULT_TTL_S,
        clock: Callable[[], float] = time.monotonic,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self.cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self.capacity = capacity
        self.ttl_s = ttl_s
        self._clock = clock
        self.max_bytes = max_bytes
        self._sizes: dict[str, int] = {}
        self.total_bytes = 0

    def get(self, key: str) -> Any | None:
        item = self.cache.get(key)
        if item is None:
            return None
        expires_at, value = item
        if self._clock() >= expires_at:
            self._drop(key)
            return None
        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, size: int = 0) -> None:
        if size > self.max_bytes:
            return
        if key in self.cache:
            self._drop(key)
        self.cache[key] = (self._clock() + self.ttl_s, value)
        self._sizes[key] = size
        self.total_bytes += size
        while len(self.cache) > self.capacity or self.total_bytes > self.max_bytes:
            self._drop(next(iter(self.cache)))

    def _drop(self, key: str) -> None:
        del self.cache[key]
        self.total_bytes -= self._sizes.pop(key, 0)

    def clear(self) -> None:
        self.cache.clear()
        self._sizes.clear()
        self.total_bytes = 0


_cache = LRUCache()


def get_cache_key(text: str, target_lang: str, audience: str, mode: str) -> str:
    key_dict = {
        "text": text,
        "target_lang": target_lang,
        "audience": audience,
        "mode": mode,
    }
    key_str = json.dumps(key_dict, sort_keys=True)
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


def get(key: str) -> Any:
    return _cache.get(key)


def set(key: str, value: Any) -> None:
    """Store a response; its JSON length is what counts against the byte bound."""
    dump = getattr(value, "model_dump_json", None)
    _cache.set(key, value, size=len(dump()) if dump else 0)


def clear() -> None:
    _cache.clear()
