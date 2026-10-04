"""Router policy: retry once with backoff, fail over, validate JSON, fail safe."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from app.llm.base import Usage
from app.llm.gemini import GeminiClient
from app.llm.notices import FALLBACK_KEY, FLAGS_PATH
from app.llm.router import BACKOFF_S, MAX_RETRY_AFTER_S, NOT_CONFIGURED, LLMRouter
from tests.llm.conftest import (
    GEMINI_URL,
    OPENROUTER_URL,
    Answer,
    answer_json,
    gemini_ok,
    openrouter_ok,
)


async def test_success_on_primary(
    mock_api: respx.MockRouter, router: LLMRouter, sleeps: list[float]
) -> None:
    mock_api.post(GEMINI_URL).mock(return_value=gemini_ok(answer_json("ok"), 100, 20))
    fallback = mock_api.post(OPENROUTER_URL)

    result = await router.complete_json("p", Answer)

    assert result.ok
    assert result.data == Answer(translation="ok")
    assert (result.provider, result.model) == ("gemini", "gemini-2.0-flash")
    assert result.usage == Usage(100, 20)
    assert result.cost_usd == pytest.approx((100 * 0.10 + 20 * 0.40) / 1_000_000)
    assert result.flags == []
    assert result.error is None
    assert sleeps == []
    assert not fallback.called


async def test_5xx_retried_once_then_succeeds(
    mock_api: respx.MockRouter, router: LLMRouter, sleeps: list[float]
) -> None:
    primary = mock_api.post(GEMINI_URL).mock(
        side_effect=[httpx.Response(500), gemini_ok(answer_json())]
    )
    fallback = mock_api.post(OPENROUTER_URL)

    result = await router.complete_json("p", Answer)

    assert result.ok and result.provider == "gemini"
    assert primary.call_count == 2
    assert sleeps == [BACKOFF_S]
    assert not fallback.called


@pytest.mark.parametrize(
    ("retry_after", "expected_sleep"),
    [("1", 1.0), ("30", MAX_RETRY_AFTER_S), (None, BACKOFF_S)],
)
async def test_429_retry_honours_capped_retry_after(
    mock_api: respx.MockRouter,
    router: LLMRouter,
    sleeps: list[float],
    retry_after: str | None,
    expected_sleep: float,
) -> None:
    headers = {"Retry-After": retry_after} if retry_after else {}
    mock_api.post(GEMINI_URL).mock(
        side_effect=[httpx.Response(429, headers=headers), gemini_ok(answer_json())]
    )

    result = await router.complete_json("p", Answer)

    assert result.ok and result.provider == "gemini"
    assert sleeps == [expected_sleep]


async def test_timeout_twice_fails_over_with_info_flag(
    mock_api: respx.MockRouter, router: LLMRouter, sleeps: list[float]
) -> None:
    primary = mock_api.post(GEMINI_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    mock_api.post(OPENROUTER_URL).mock(return_value=openrouter_ok(answer_json("fb"), 90, 15))

    result = await router.complete_json("p", Answer)

    assert result.data == Answer(translation="fb")
    assert (result.provider, result.model) == ("openrouter", "mistralai/mistral-large")
    assert primary.call_count == 2
    assert sleeps == [BACKOFF_S]
    assert [(f.type, f.key) for f in result.flags] == [("info", FALLBACK_KEY)]


def test_fallback_flag_text_comes_from_messages_file() -> None:
    from app.llm.notices import fallback_flag

    messages = json.loads(Path(FLAGS_PATH).read_text(encoding="utf-8"))["messages"]

    assert fallback_flag().msg == messages[FALLBACK_KEY]
    assert fallback_flag().msg


async def test_invalid_json_retried_once_then_succeeds(
    mock_api: respx.MockRouter, router: LLMRouter, sleeps: list[float]
) -> None:
    mock_api.post(GEMINI_URL).mock(
        side_effect=[gemini_ok("{not json", 100, 5), gemini_ok(answer_json(), 100, 20)]
    )

    result = await router.complete_json("p", Answer)

    assert result.ok and result.provider == "gemini"
    assert sleeps == [BACKOFF_S]
    # Tokens of the wasted attempt are still billed and must be counted.
    assert result.usage == Usage(200, 25)
    assert result.cost_usd == pytest.approx((200 * 0.10 + 25 * 0.40) / 1_000_000)


@pytest.mark.parametrize(
    "bad_text",
    [
        "{not json",
        '{"wrong_field": "x"}',
        '{"translation": "x", "extra": 1}',
        '{"translation": 42}',
        "[]",
    ],
)
async def test_invalid_output_twice_fails_over(
    mock_api: respx.MockRouter, router: LLMRouter, bad_text: str
) -> None:
    primary = mock_api.post(GEMINI_URL).mock(return_value=gemini_ok(bad_text))
    mock_api.post(OPENROUTER_URL).mock(return_value=openrouter_ok(answer_json("fb")))

    result = await router.complete_json("p", Answer)

    assert primary.call_count == 2
    assert result.provider == "openrouter"
    assert result.data == Answer(translation="fb")


async def test_code_fenced_json_is_accepted(mock_api: respx.MockRouter, router: LLMRouter) -> None:
    fenced = f"```json\n{answer_json('fenced')}\n```"
    mock_api.post(GEMINI_URL).mock(return_value=gemini_ok(fenced))

    result = await router.complete_json("p", Answer)

    assert result.data == Answer(translation="fenced")


@pytest.mark.parametrize("status", [400, 401, 403])
async def test_client_error_fails_over_without_retry(
    mock_api: respx.MockRouter, router: LLMRouter, sleeps: list[float], status: int
) -> None:
    primary = mock_api.post(GEMINI_URL).mock(return_value=httpx.Response(status))
    mock_api.post(OPENROUTER_URL).mock(return_value=openrouter_ok(answer_json()))

    result = await router.complete_json("p", Answer)

    assert primary.call_count == 1
    assert sleeps == []
    assert result.provider == "openrouter"


async def test_all_providers_down_fails_safe_without_raising(
    mock_api: respx.MockRouter, router: LLMRouter, sleeps: list[float]
) -> None:
    primary = mock_api.post(GEMINI_URL).mock(return_value=httpx.Response(503))
    fallback = mock_api.post(OPENROUTER_URL).mock(return_value=httpx.Response(500))

    result = await router.complete_json("p", Answer)

    assert result.data is None
    assert not result.ok
    assert result.error == "server"
    assert result.flags == []
    assert primary.call_count == 2
    assert fallback.call_count == 2
    assert sleeps == [BACKOFF_S, BACKOFF_S]


async def test_fallback_error_is_the_reported_error(
    mock_api: respx.MockRouter, router: LLMRouter
) -> None:
    mock_api.post(GEMINI_URL).mock(return_value=httpx.Response(500))
    mock_api.post(OPENROUTER_URL).mock(side_effect=httpx.ReadTimeout("slow"))

    result = await router.complete_json("p", Answer)

    assert result.error == "timeout"


async def test_no_fallback_configured_primary_down_fails_safe(
    mock_api: respx.MockRouter, gemini: GeminiClient, fake_sleep: object
) -> None:
    mock_api.post(GEMINI_URL).mock(return_value=httpx.Response(429))
    router = LLMRouter([gemini], sleep=fake_sleep)  # type: ignore[arg-type]

    result = await router.complete_json("p", Answer)

    assert result.data is None
    assert result.error == "rate_limited"


async def test_no_provider_configured_fails_safe() -> None:
    result = await LLMRouter([]).complete_json("p", Answer)

    assert result.data is None
    assert result.error == NOT_CONFIGURED
    assert result.usage == Usage()
