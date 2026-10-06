"""Provider failure types, classified so the router can decide retry vs failover."""

from __future__ import annotations

from enum import StrEnum

import httpx


class ErrorKind(StrEnum):
    TIMEOUT = "timeout"
    TRANSPORT = "transport"
    RATE_LIMITED = "rate_limited"
    SERVER = "server"
    CLIENT = "client"
    INVALID_RESPONSE = "invalid_response"
    # This provider's own daily request cap is spent (D-066): skip it, never retry today.
    DAILY_QUOTA = "daily_quota"


# 4xx other than 429 means bad config or a bad request: retrying the same
# provider cannot help, so the router fails over immediately.
_RETRYABLE = frozenset(
    {
        ErrorKind.TIMEOUT,
        ErrorKind.TRANSPORT,
        ErrorKind.RATE_LIMITED,
        ErrorKind.SERVER,
        ErrorKind.INVALID_RESPONSE,
    }
)


class ProviderError(Exception):
    """A failed provider call. The message never contains keys or user text."""

    def __init__(
        self,
        kind: ErrorKind,
        status: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(f"{kind.value}" + (f" (HTTP {status})" if status else ""))
        self.kind = kind
        self.status = status
        self.retry_after = retry_after

    @property
    def retryable(self) -> bool:
        return self.kind in _RETRYABLE


def error_from_status(response: httpx.Response) -> ProviderError:
    """Map a non-2xx response to a ``ProviderError``."""
    status = response.status_code
    if status == httpx.codes.TOO_MANY_REQUESTS:
        return ProviderError(ErrorKind.RATE_LIMITED, status, _parse_retry_after(response))
    if status >= httpx.codes.INTERNAL_SERVER_ERROR:
        return ProviderError(ErrorKind.SERVER, status)
    return ProviderError(ErrorKind.CLIENT, status)


def error_from_exception(exc: httpx.HTTPError) -> ProviderError:
    """Map an httpx transport-level exception to a ``ProviderError``."""
    if isinstance(exc, httpx.TimeoutException):
        return ProviderError(ErrorKind.TIMEOUT)
    return ProviderError(ErrorKind.TRANSPORT)


def _parse_retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None
