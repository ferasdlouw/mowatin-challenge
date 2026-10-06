"""Routes JSON completions through primary → fallback with retry and fail-safe.

Policy (decision D-011): each provider gets one retry with backoff on
retryable errors; then the next provider is tried; if all fail the caller
gets ``LLMResult(data=None)`` and must emit ``output: null`` + review.
Provider failures never raise out of ``complete_json``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import unicodedata
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from app.llm.base import LLMResult, ProviderClient, T, Usage
from app.llm.errors import ErrorKind, ProviderError
from app.llm.notices import fallback_flag
from app.llm.pricing import actual_cost, estimate_cost
from app.security.privacy import keyed_digest

logger = logging.getLogger("app.llm")

MAX_ATTEMPTS = 2
BACKOFF_S = 0.5
MAX_RETRY_AFTER_S = 4.0
NOT_CONFIGURED = "not_configured"

Sleep = Callable[[float], Awaitable[None]]


@dataclass
class _Tally:
    """Tokens, cost and latency summed over every attempt of one request (tokens are billed even on bad JSON)."""

    prompt_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    list_cost_usd: float = 0.0
    latency_ms: int = 0

    def add(self, usage: Usage, cost: float | None, list_cost: float | None) -> None:
        self.prompt_tokens += usage.prompt_tokens
        self.output_tokens += usage.output_tokens
        self.cost_usd += cost or 0.0
        self.list_cost_usd += list_cost or 0.0

    def usage(self) -> Usage:
        return Usage(self.prompt_tokens, self.output_tokens)


class LLMRouter:
    """Implements ``JsonCompleter`` over an ordered list of providers."""

    def __init__(
        self,
        providers: Sequence[ProviderClient],
        sleep: Sleep = asyncio.sleep,
        clock: Callable[[], float] = time.perf_counter,
        judge: LLMRouter | None = None,
    ) -> None:
        self._providers = list(providers)
        self._sleep = sleep
        self._clock = clock
        # The verifier's JUDGE_* router, built once with the app's settings (D-061).
        self.judge = judge

    async def complete_json(self, prompt: str, schema: type[T]) -> LLMResult[T]:
        tally = _Tally()
        error = NOT_CONFIGURED
        for index, provider in enumerate(self._providers):
            try:
                data = await self._with_retry(provider, prompt, schema, tally)
            except ProviderError as exc:
                error = exc.kind.value
                self._log_failover(index, exc)
                continue
            return LLMResult(
                data=data,
                provider=provider.name,
                model=provider.model,
                usage=tally.usage(),
                cost_usd=tally.cost_usd,
                list_cost_usd=tally.list_cost_usd,
                latency_ms=tally.latency_ms,
                flags=[fallback_flag()] if index > 0 else [],
            )
        _log({"event": "llm_failed", "error": error, **_fingerprint(prompt)})
        return LLMResult(
            data=None,
            usage=tally.usage(),
            cost_usd=tally.cost_usd,
            list_cost_usd=tally.list_cost_usd,
            latency_ms=tally.latency_ms,
            error=error,
        )

    async def _with_retry(
        self, provider: ProviderClient, prompt: str, schema: type[T], tally: _Tally
    ) -> T:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            # Every HTTP attempt, retries included, counts against the provider's own daily
            # cap (D-066); once it is spent the provider is skipped and the next one is tried.
            daily = getattr(provider, "daily", None)
            if daily is not None and not daily.take():
                raise ProviderError(ErrorKind.DAILY_QUOTA)
            try:
                return await self._attempt(provider, prompt, schema, attempt, tally)
            except ProviderError as exc:
                if attempt == MAX_ATTEMPTS or not exc.retryable:
                    raise
                await self._sleep(_backoff(exc, attempt))
        raise AssertionError("unreachable")  # pragma: no cover

    async def _attempt(
        self, provider: ProviderClient, prompt: str, schema: type[T], attempt: int, tally: _Tally
    ) -> T:
        started = self._clock()
        usage, cost, list_cost, outcome = Usage(), None, None, "ok"
        try:
            completion = await provider.generate(prompt)
            usage = completion.usage
            list_cost = estimate_cost(provider.model, usage)
            # Set by factory.build_provider from LLM_BILLING; test fakes default to paid.
            free_tier = bool(getattr(provider, "free_tier", False))
            cost = actual_cost(provider.model, usage, free_tier)
            tally.add(usage, cost, list_cost)
            return _parse(completion.text, schema)
        except ProviderError as exc:
            outcome = exc.kind.value
            raise
        finally:
            latency_ms = round((self._clock() - started) * 1000)
            tally.latency_ms += latency_ms
            _log(
                {
                    "event": "llm_call",
                    "provider": provider.name,
                    "model": provider.model,
                    "attempt": attempt,
                    "outcome": outcome,
                    "latency_ms": latency_ms,
                    "prompt_tokens": usage.prompt_tokens,
                    "output_tokens": usage.output_tokens,
                    "output_tokens_per_s": tokens_per_second(usage.output_tokens, latency_ms),
                    # Actual (billed today) and at paid list price (cost at scale), D-031.
                    "cost_usd": cost,
                    "list_cost_usd": list_cost,
                    "cost_known": list_cost is not None,
                    # Unknown models are never priced by guess: they count $0 and say so.
                    "price_unknown": list_cost is None,
                    **_fingerprint(prompt),
                }
            )

    def _log_failover(self, index: int, exc: ProviderError) -> None:
        if index + 1 >= len(self._providers):
            return
        _log(
            {
                "event": "llm_failover",
                "from": self._providers[index].name,
                "to": self._providers[index + 1].name,
                "reason": exc.kind.value,
            }
        )


def _parse(text: str, schema: type[T]) -> T:
    try:
        parsed = schema.model_validate_json(_strip_code_fence(text))
        return schema.model_validate(_unescape(parsed.model_dump()))
    except ValidationError:
        raise ProviderError(ErrorKind.INVALID_RESPONSE) from None


# Some models escape twice, so «\u00ab» survives JSON decoding as six literal characters.
_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")


def _decode_escape(found: re.Match[str]) -> str:
    char = chr(int(found.group(1), 16))
    # Control, format and surrogate code points stay escaped: never smuggle them into output.
    return found.group(0) if unicodedata.category(char).startswith("C") else char


def _unescape(value: object) -> object:
    if isinstance(value, str):
        return _ESCAPE_RE.sub(_decode_escape, value)
    if isinstance(value, list):
        return [_unescape(item) for item in value]
    if isinstance(value, dict):
        return {key: _unescape(item) for key, item in value.items()}
    return value


def _strip_code_fence(text: str) -> str:
    # Some models wrap JSON in ```json fences even in JSON mode.
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped[3:-3]
        stripped = stripped.removeprefix("json")
    return stripped.strip()


def _backoff(exc: ProviderError, attempt: int) -> float:
    if exc.retry_after is not None:
        return min(exc.retry_after, MAX_RETRY_AFTER_S)
    return BACKOFF_S * 2 ** (attempt - 1)


def tokens_per_second(output_tokens: int, latency_ms: int) -> float | None:
    """Output speed for the model-choice table (docs/MODELS.md); ``None`` when not measurable."""
    if output_tokens <= 0 or latency_ms <= 0:
        return None
    return round(output_tokens / (latency_ms / 1000), 1)


def _fingerprint(prompt: str) -> dict[str, object]:
    """Privacy rule: identify a prompt by length and keyed hash prefix, never its text."""
    return {"prompt_len": len(prompt), "prompt_sha256": keyed_digest(prompt)}


def _log(record: dict[str, object]) -> None:
    logger.info(json.dumps(record, ensure_ascii=False, sort_keys=True))
