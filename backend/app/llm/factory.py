"""Builds the provider chain from settings (``LLM_*`` then ``FALLBACK_*``)."""

from __future__ import annotations

import httpx

from app.config import Settings
from app.llm.base import ProviderClient
from app.llm.gemini import GeminiClient
from app.llm.openai_compat import OpenAICompatClient, base_url_problem, is_local
from app.llm.openrouter import OpenRouterClient
from app.llm.router import LLMRouter

PROVIDERS: dict[str, type[GeminiClient] | type[OpenRouterClient]] = {
    "gemini": GeminiClient,
    "openrouter": OpenRouterClient,
}
# Built separately: it is the only provider that needs ``<SLOT>_BASE_URL`` (D-026).
OPENAI_COMPAT = "openai_compat"


class LLMConfigError(ValueError):
    """Invalid provider configuration. Messages name env vars, never their values."""


def build_provider(
    prefix: str, settings: Settings, http: httpx.AsyncClient
) -> ProviderClient | None:
    """Client for the ``{prefix}_*`` slot; ``None`` when its provider is unset.

    Raises ``LLMConfigError`` on an unknown provider or a partial slot.
    """
    field = prefix.lower()
    name: str = getattr(settings, f"{field}_provider")
    api_key: str = getattr(settings, f"{field}_api_key")
    model: str = getattr(settings, f"{field}_model")
    if not name:
        return None
    name = name.strip().lower()
    if name == OPENAI_COMPAT:
        return _tag_billing(_build_openai_compat(prefix, settings, http), settings)
    provider_cls = PROVIDERS.get(name)
    if provider_cls is None:
        names = ", ".join(sorted([*PROVIDERS, OPENAI_COMPAT]))
        raise LLMConfigError(f"{prefix}_PROVIDER must be one of: {names}")
    if not api_key or not model:
        raise LLMConfigError(f"{prefix}_API_KEY and {prefix}_MODEL are required")
    return _tag_billing(provider_cls(http, api_key, model, settings.llm_timeout_s), settings)


def _tag_billing(provider: ProviderClient, settings: Settings) -> ProviderClient:
    """The router reads ``free_tier`` to log actual cost 0 next to the list cost (D-031)."""
    provider.free_tier = settings.llm_billing == "free"  # type: ignore[attr-defined]
    return provider


def _build_openai_compat(
    prefix: str, settings: Settings, http: httpx.AsyncClient
) -> OpenAICompatClient:
    """Base URL required and checked; an empty key is accepted only for a local server."""
    field = prefix.lower()
    api_key: str = getattr(settings, f"{field}_api_key")
    model: str = getattr(settings, f"{field}_model")
    base_url: str = getattr(settings, f"{field}_base_url")
    if not model or not base_url:
        raise LLMConfigError(f"{prefix}_MODEL and {prefix}_BASE_URL are required")
    problem = base_url_problem(base_url)
    if problem:
        raise LLMConfigError(f"{prefix}_BASE_URL {problem}")
    if not api_key and not is_local(base_url):
        raise LLMConfigError(f"{prefix}_API_KEY is required unless {prefix}_BASE_URL is local")
    return OpenAICompatClient(http, api_key, model, settings.llm_timeout_s, base_url)


def configured_providers(settings: Settings, http: httpx.AsyncClient) -> list[ProviderClient]:
    """Primary first, then fallback; unset slots are skipped."""
    candidates = [build_provider(prefix, settings, http) for prefix in ("LLM", "FALLBACK")]
    return [provider for provider in candidates if provider is not None]


def build_router(settings: Settings, http: httpx.AsyncClient) -> LLMRouter:
    """Router over the configured chain; an empty chain fails safe on every call."""
    return LLMRouter(configured_providers(settings, http))
