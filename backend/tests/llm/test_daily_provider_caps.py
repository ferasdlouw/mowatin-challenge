"""D-066 (code audit item 14): each provider has its own daily cap, in real HTTP requests.

Before, the only daily limit counted routed calls for the whole app (1000), while one routed
call can be up to 4 HTTP requests (2 attempts on the primary, 2 on the fallback): nothing kept
OpenRouter's free tier (50 requests a day) from being spent.
"""

from __future__ import annotations

import httpx
import respx

from app.config import Settings
from app.llm.factory import build_router
from app.llm.notices import FALLBACK_KEY
from app.llm.router import LLMRouter
from app.pipeline.budget import DailyBreaker
from tests.llm.conftest import (
    GEMINI_URL,
    OPENROUTER_URL,
    Answer,
    answer_json,
    gemini_ok,
    openrouter_ok,
)


async def test_every_attempt_counts_and_a_spent_primary_is_skipped(
    mock_api: respx.MockRouter, router: LLMRouter
) -> None:
    primary, fallback = router._providers
    primary.daily = DailyBreaker(limit=2)
    gemini = mock_api.post(GEMINI_URL).mock(side_effect=[httpx.Response(500), httpx.Response(500)])
    openrouter = mock_api.post(OPENROUTER_URL).mock(return_value=openrouter_ok(answer_json()))

    first = await router.complete_json("p", Answer)  # primary: 2 attempts (retry), then fallback
    second = await router.complete_json("p", Answer)  # primary cap spent: straight to fallback

    assert gemini.call_count == 2
    assert openrouter.call_count == 2
    assert first.ok and second.ok
    assert second.provider == fallback.name
    assert [flag.key for flag in second.flags] == [FALLBACK_KEY]


async def test_both_caps_spent_fails_safe_without_a_request(
    mock_api: respx.MockRouter, router: LLMRouter
) -> None:
    for provider in router._providers:
        provider.daily = DailyBreaker(limit=0)
    gemini = mock_api.post(GEMINI_URL).mock(return_value=gemini_ok(answer_json()))
    openrouter = mock_api.post(OPENROUTER_URL).mock(return_value=openrouter_ok(answer_json()))

    result = await router.complete_json("p", Answer)

    assert result.data is None
    assert result.error == "daily_quota"
    assert not gemini.called and not openrouter.called


def _keys() -> dict[str, str]:
    return {
        "llm_provider": "gemini",
        "llm_api_key": "k",
        "llm_model": "m",
        "fallback_provider": "openrouter",
        "fallback_api_key": "k",
        "fallback_model": "m:free",
    }


def test_fallback_is_capped_at_45_by_default_and_the_primary_is_not():
    settings = Settings(_env_file=None, env="test", **_keys())  # type: ignore[arg-type]
    primary, fallback = build_router(settings, httpx.AsyncClient())._providers
    assert primary.daily is None
    assert fallback.daily is not None and fallback.daily.limit == 45


def test_caps_are_settings_and_zero_means_none(monkeypatch):
    monkeypatch.setenv("LLM_DAILY_LIMIT", "300")
    monkeypatch.setenv("FALLBACK_DAILY_LIMIT", "0")
    settings = Settings(_env_file=None, env="test", **_keys())  # type: ignore[arg-type]
    primary, fallback = build_router(settings, httpx.AsyncClient())._providers
    assert primary.daily.limit == 300
    assert fallback.daily is None


def test_a_blank_setting_keeps_the_default(monkeypatch):
    monkeypatch.setenv("FALLBACK_DAILY_LIMIT", "")
    assert Settings(_env_file=None).fallback_daily_limit == 45  # type: ignore[call-arg]
