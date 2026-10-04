"""Provider clients: request shape, response parsing and error classification."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.llm.base import SEED, TEMPERATURE, Usage
from app.llm.errors import ErrorKind, ProviderError
from app.llm.gemini import GeminiClient
from app.llm.openrouter import OpenRouterClient
from tests.llm.conftest import (
    FAKE_KEY,
    GEMINI_URL,
    OPENROUTER_MODEL,
    OPENROUTER_URL,
    gemini_ok,
    openrouter_ok,
)

# ── Gemini ───────────────────────────────────────────────────────────


async def test_gemini_success_parses_text_and_usage(
    mock_api: respx.MockRouter, gemini: GeminiClient
) -> None:
    mock_api.post(GEMINI_URL).mock(return_value=gemini_ok('{"a": 1}', 120, 30))

    completion = await gemini.generate("prompt")

    assert completion.text == '{"a": 1}'
    assert completion.usage == Usage(prompt_tokens=120, output_tokens=30)


async def test_gemini_request_is_json_mode_low_temp_seeded_and_key_in_header(
    mock_api: respx.MockRouter, gemini: GeminiClient
) -> None:
    route = mock_api.post(GEMINI_URL).mock(return_value=gemini_ok("{}"))

    await gemini.generate("the prompt")

    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["contents"][0]["parts"][0]["text"] == "the prompt"
    config = body["generationConfig"]
    assert config == {
        "temperature": TEMPERATURE,
        "seed": SEED,
        "responseMimeType": "application/json",
    }
    assert request.headers["x-goog-api-key"] == FAKE_KEY
    assert FAKE_KEY not in str(request.url)


async def test_gemini_missing_usage_counts_zero(
    mock_api: respx.MockRouter, gemini: GeminiClient
) -> None:
    payload = {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
    mock_api.post(GEMINI_URL).mock(return_value=httpx.Response(200, json=payload))

    assert (await gemini.generate("p")).usage == Usage()


async def test_gemini_skips_thought_parts(
    mock_api: respx.MockRouter, gemini: GeminiClient
) -> None:
    parts = [
        {"text": "* Input: return JSON ...", "thought": True},
        {"text": "`", "thought": True},
        {"text": '{"ok": true}'},
    ]
    payload = {"candidates": [{"content": {"parts": parts}}]}
    mock_api.post(GEMINI_URL).mock(return_value=httpx.Response(200, json=payload))

    assert (await gemini.generate("p")).text == '{"ok": true}'


async def test_gemini_only_thought_parts_is_invalid(
    mock_api: respx.MockRouter, gemini: GeminiClient
) -> None:
    payload = {"candidates": [{"content": {"parts": [{"text": "thinking", "thought": True}]}}]}
    mock_api.post(GEMINI_URL).mock(return_value=httpx.Response(200, json=payload))

    with pytest.raises(ProviderError) as err:
        await gemini.generate("p")
    assert err.value.kind is ErrorKind.INVALID_RESPONSE


@pytest.mark.parametrize(
    ("response", "kind", "retryable"),
    [
        (httpx.Response(429, headers={"Retry-After": "3"}), ErrorKind.RATE_LIMITED, True),
        (httpx.Response(500), ErrorKind.SERVER, True),
        (httpx.Response(503), ErrorKind.SERVER, True),
        (httpx.Response(401), ErrorKind.CLIENT, False),
        (httpx.Response(400), ErrorKind.CLIENT, False),
        (httpx.Response(200, text="<html>gateway</html>"), ErrorKind.INVALID_RESPONSE, True),
        (httpx.Response(200, json=[1, 2]), ErrorKind.INVALID_RESPONSE, True),
        # Safety block: 200 with no candidates.
        (
            httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),
            ErrorKind.INVALID_RESPONSE,
            True,
        ),
        (
            httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": " "}]}}]}),
            ErrorKind.INVALID_RESPONSE,
            True,
        ),
    ],
)
async def test_gemini_error_classification(
    mock_api: respx.MockRouter,
    gemini: GeminiClient,
    response: httpx.Response,
    kind: ErrorKind,
    retryable: bool,
) -> None:
    mock_api.post(GEMINI_URL).mock(return_value=response)

    with pytest.raises(ProviderError) as info:
        await gemini.generate("p")

    assert info.value.kind is kind
    assert info.value.retryable is retryable


async def test_gemini_429_reads_retry_after(
    mock_api: respx.MockRouter, gemini: GeminiClient
) -> None:
    mock_api.post(GEMINI_URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "3"}))

    with pytest.raises(ProviderError) as info:
        await gemini.generate("p")

    assert info.value.retry_after == 3.0


async def test_gemini_429_with_unparseable_retry_after(
    mock_api: respx.MockRouter, gemini: GeminiClient
) -> None:
    response = httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
    mock_api.post(GEMINI_URL).mock(return_value=response)

    with pytest.raises(ProviderError) as info:
        await gemini.generate("p")

    assert info.value.retry_after is None


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (httpx.ReadTimeout("slow"), ErrorKind.TIMEOUT),
        (httpx.ConnectTimeout("slow"), ErrorKind.TIMEOUT),
        (httpx.ConnectError("refused"), ErrorKind.TRANSPORT),
    ],
)
async def test_gemini_transport_failures(
    mock_api: respx.MockRouter, gemini: GeminiClient, exc: Exception, kind: ErrorKind
) -> None:
    mock_api.post(GEMINI_URL).mock(side_effect=exc)

    with pytest.raises(ProviderError) as info:
        await gemini.generate("p")

    assert info.value.kind is kind
    assert info.value.retryable


# ── OpenRouter ───────────────────────────────────────────────────────


async def test_openrouter_success_parses_text_and_usage(
    mock_api: respx.MockRouter, openrouter: OpenRouterClient
) -> None:
    mock_api.post(OPENROUTER_URL).mock(return_value=openrouter_ok('{"b": 2}', 70, 11))

    completion = await openrouter.generate("prompt")

    assert completion.text == '{"b": 2}'
    assert completion.usage == Usage(prompt_tokens=70, output_tokens=11)


async def test_openrouter_request_shape(
    mock_api: respx.MockRouter, openrouter: OpenRouterClient
) -> None:
    route = mock_api.post(OPENROUTER_URL).mock(return_value=openrouter_ok("{}"))

    await openrouter.generate("the prompt")

    request = route.calls.last.request
    body = json.loads(request.content)
    assert body == {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": "the prompt"}],
        "temperature": TEMPERATURE,
        "seed": SEED,
        "response_format": {"type": "json_object"},
    }
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"


@pytest.mark.parametrize(
    ("response", "kind"),
    [
        (httpx.Response(429), ErrorKind.RATE_LIMITED),
        (httpx.Response(502), ErrorKind.SERVER),
        (httpx.Response(403), ErrorKind.CLIENT),
        # Upstream failure relayed as 200 + error object.
        (httpx.Response(200, json={"error": {"code": 502}}), ErrorKind.SERVER),
        (httpx.Response(200, json={"choices": []}), ErrorKind.INVALID_RESPONSE),
        (
            httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
            ErrorKind.INVALID_RESPONSE,
        ),
    ],
)
async def test_openrouter_error_classification(
    mock_api: respx.MockRouter,
    openrouter: OpenRouterClient,
    response: httpx.Response,
    kind: ErrorKind,
) -> None:
    mock_api.post(OPENROUTER_URL).mock(return_value=response)

    with pytest.raises(ProviderError) as info:
        await openrouter.generate("p")

    assert info.value.kind is kind


async def test_openrouter_timeout(
    mock_api: respx.MockRouter, openrouter: OpenRouterClient
) -> None:
    mock_api.post(OPENROUTER_URL).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(ProviderError) as info:
        await openrouter.generate("p")

    assert info.value.kind is ErrorKind.TIMEOUT


async def test_openrouter_bad_usage_values_count_zero(
    mock_api: respx.MockRouter, openrouter: OpenRouterClient
) -> None:
    payload = {
        "choices": [{"message": {"content": "{}"}}],
        "usage": {"prompt_tokens": "many", "completion_tokens": -1},
    }
    mock_api.post(OPENROUTER_URL).mock(return_value=httpx.Response(200, json=payload))

    assert (await openrouter.generate("p")).usage == Usage()


def test_provider_error_message_has_no_secret() -> None:
    error = ProviderError(ErrorKind.CLIENT, 401)

    assert str(error) == "client (HTTP 401)"
