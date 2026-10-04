"""Shared types and interfaces for the LLM provider layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

from app.schemas import Flag

T = TypeVar("T", bound=BaseModel)

# Low temperature and a fixed seed keep repeated runs (3 eval runs) comparable.
TEMPERATURE = 0.2
SEED = 7


@dataclass(frozen=True)
class Usage:
    """Token counts reported by a provider for one call."""

    prompt_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class Completion:
    """Raw text returned by a provider, before JSON validation."""

    text: str
    usage: Usage


@dataclass
class LLMResult(Generic[T]):
    """Outcome of a routed JSON completion.

    ``data`` is ``None`` when every attempt failed; callers must then emit
    ``output: null`` and send the segment to review instead of crashing.
    """

    data: T | None
    provider: str = ""
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    # Billed today (0 on a free tier); list_cost_usd = the same tokens at paid list price.
    cost_usd: float = 0.0
    list_cost_usd: float = 0.0
    # Summed over every attempt, including retries and failover (docs/MODELS.md).
    latency_ms: int = 0
    error: str | None = None
    flags: list[Flag] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.data is not None


class ProviderClient(Protocol):
    """One HTTP-backed model. Raises ``ProviderError`` on any failure."""

    name: str
    model: str

    async def generate(self, prompt: str) -> Completion: ...


class JsonCompleter(Protocol):
    """What the pipeline depends on; tests can fake this directly."""

    async def complete_json(self, prompt: str, schema: type[T]) -> LLMResult[T]: ...
