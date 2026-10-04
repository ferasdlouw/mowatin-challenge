"""In-memory per-IP sliding-window rate limit for ``/v1/*``.

Per process only: right for the single free-plan Render instance (see docs/dev/DEPLOY.md).
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from app.errors import rate_limited_response
from app.security.client_ip import client_ip, rate_limit_key, subnet_key

LIMITED_PREFIX = "/v1/"
MAX_TRACKED_CLIENTS = 10_000
# An IPv6 /48 (one site) may make this many times the per-client limit (NEW-4).
SUBNET_LIMIT_FACTOR = 4


class SlidingWindowLimiter:
    """Allows ``limit`` hits per ``window_s`` seconds per key."""

    def __init__(
        self,
        limit: int,
        window_s: float,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = MAX_TRACKED_CLIENTS,
    ) -> None:
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}
        self._last_sweep = clock()

    def hit(self, key: str) -> int | None:
        """Record a hit. Return ``None`` if allowed, else whole seconds until a slot frees."""
        now = self._clock()
        hits = self._hits.get(key)
        if hits is None:
            if not self._has_room(now):
                # Never evict an active key: that would let a client reset its own count
                # by cycling addresses. A full table means a flood, so new keys wait.
                return math.ceil(self.window_s)
            hits = self._hits[key] = deque()
        while hits and hits[0] <= now - self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(1, math.ceil(hits[0] + self.window_s - now))
        hits.append(now)
        return None

    def _has_room(self, now: float) -> bool:
        """Bound memory; idle keys are swept at most once per window, not on every insert."""
        if len(self._hits) < self._max_keys:
            return True
        if now - self._last_sweep >= self.window_s:
            self._last_sweep = now
            cutoff = now - self.window_s
            for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= cutoff]:
                del self._hits[key]
        return len(self._hits) < self._max_keys


class RateLimitMiddleware:
    """Return 429 + ``Retry-After`` once a client exceeds the limit on ``/v1/*``.

    ``/health`` is never limited (the keep-alive cron calls it), nor are CORS preflights.
    An IPv6 client is also counted against its /48 in ``subnet_limiter``, checked first so a
    site over its limit adds no new per-client keys.
    """

    def __init__(
        self,
        app: ASGIApp,
        limiter: SlidingWindowLimiter,
        trusted_proxy_hops: int,
        subnet_limiter: SlidingWindowLimiter | None = None,
    ) -> None:
        self.app = app
        self.limiter = limiter
        self.trusted_proxy_hops = trusted_proxy_hops
        self.subnet_limiter = subnet_limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] != "OPTIONS"
            and scope["path"].startswith(LIMITED_PREFIX)
        ):
            address = client_ip(scope, self.trusted_proxy_hops)
            retry_after = self._hit(address)
            if retry_after is not None:
                await rate_limited_response(retry_after)(scope, receive, send)
                return
        await self.app(scope, receive, send)

    def _hit(self, address: str) -> int | None:
        site = subnet_key(address)
        if site is not None and self.subnet_limiter is not None:
            retry_after = self.subnet_limiter.hit(site)
            if retry_after is not None:
                return retry_after
        return self.limiter.hit(rate_limit_key(address))
