"""Per-request and per-process limits on LLM work (Phase SEC, decision D-034).

One request may make at most ``call_budget`` routed LLM calls and may start new calls only
until ``deadline_s`` has passed; the whole process may make at most ``daily_calls`` routed
calls per UTC day. A refused call is never sent: the caller gets ``LLMResult(data=None)``
and fails safe to ``output: null`` + review, like any failed call (D-011).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

LIMIT_ERROR = "limit_reached"

DEFAULT_MAX_SEGMENTS = 6
DEFAULT_CALL_BUDGET = 28
DEFAULT_DEADLINE_S = 90.0
DEFAULT_DAILY_CALLS = 1000
_SECONDS_PER_DAY = 86_400


class DailyBreaker:
    """Process-wide routed-call counter that resets at 00:00 UTC (in memory, per instance)."""

    def __init__(
        self, limit: int = DEFAULT_DAILY_CALLS, clock: Callable[[], float] = time.time
    ) -> None:
        self.limit = limit
        self._clock = clock
        self._day = self._today()
        self._used = 0

    def _today(self) -> int:
        return int(self._clock() // _SECONDS_PER_DAY)

    def take(self) -> bool:
        """Count one call; ``False`` once today's limit is spent."""
        today = self._today()
        if today != self._day:
            self._day, self._used = today, 0
        if self._used >= self.limit:
            return False
        self._used += 1
        return True


@dataclass(frozen=True)
class RequestLimits:
    """The limits one request runs under; built once per app from ``Settings``."""

    max_segments: int = DEFAULT_MAX_SEGMENTS
    call_budget: int = DEFAULT_CALL_BUDGET
    deadline_s: float = DEFAULT_DEADLINE_S
    daily: DailyBreaker = field(default_factory=DailyBreaker)


class RequestBudget:
    """Counts one request's routed LLM calls against its limits."""

    def __init__(self, limits: RequestLimits, clock: Callable[[], float] = time.monotonic) -> None:
        self._limits = limits
        self._clock = clock
        self._ends_at = clock() + limits.deadline_s
        self.calls = 0
        self.denied = 0
        self.reason: str | None = None

    def allow(self) -> bool:
        """``True`` if one more call may start now; the first refusal reason is kept."""
        reason = self._refusal()
        if reason is None:
            self.calls += 1
            return True
        self.denied += 1
        self.reason = self.reason or reason
        return False

    def remaining(self) -> float:
        """Seconds left before the deadline (D-060: a running call may not outlive it)."""
        return max(self._ends_at - self._clock(), 0.0)

    def expire(self) -> None:
        """A call was cut at the deadline: counted as refused, like a call not started."""
        self.denied += 1
        self.reason = self.reason or "deadline"

    def _refusal(self) -> str | None:
        if self.calls >= self._limits.call_budget:
            return "call_budget"
        if self._clock() >= self._ends_at:
            return "deadline"
        if not self._limits.daily.take():
            return "daily_budget"
        return None
