"""openai_compat provider (D-026): any OpenAI-compatible endpoint, local or hosted."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from app.config import Settings
from app.llm.base import SEED, TEMPERATURE, Usage
from app.llm.errors import ErrorKind, ProviderError
from app.llm.factory import LLMConfigError, build_provider, configured_providers
from app.llm.gemini import GeminiClient
from app.llm.openai_compat import OpenAICompatClient, base_url_problem
from app.llm.openrouter import OpenRouterClient
from app.llm.router import LLMRouter
from tests.llm.conftest import FAKE_KEY, Answer, answer_json, openrouter_ok

HOSTED = "https://llm.example.test/v1"
LOCAL = "http://localhost:11434/v1"
MODEL = "llama3.1:8b"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "llm_provider": "openai_compat",
        "llm_api_key": FAKE_KEY,
        "llm_model": MODEL,
        "llm_base_url": HOSTED,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def _client(http: httpx.AsyncClient, base_url: str = HOSTED, key: str = FAKE_KEY) -> Any:
    return OpenAICompatClient(http, key, MODEL, 5.0, base_url)


async def test_success_parses_text_usage_and_sends_json_mode(
    mock_api: respx.MockRouter, http: httpx.AsyncClient
) -> None:
    route = mock_api.post(f"{HOSTED}/chat/completions").mock(
        return_value=openrouter_ok('{"a": 1}', 40, 8)
    )

    completion = await _client(http, HOSTED + "/").generate("the prompt")

    assert completion.text == '{"a": 1}'
    assert completion.usage == Usage(prompt_tokens=40, output_tokens=8)
    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["model"] == MODEL
    assert body["messages"] == [{"role": "user", "content": "the prompt"}]
    assert (body["temperature"], body["seed"]) == (TEMPERATURE, SEED)
    assert body["response_format"] == {"type": "json_object"}
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"


async def test_local_server_without_key_sends_no_auth_header(
    mock_api: respx.MockRouter, http: httpx.AsyncClient
) -> None:
    route = mock_api.post(f"{LOCAL}/chat/completions").mock(return_value=openrouter_ok("{}"))

    await _client(http, LOCAL, key="").generate("p")

    assert "authorization" not in route.calls.last.request.headers


@pytest.mark.parametrize(
    ("response", "kind"),
    [
        (httpx.Response(429, headers={"retry-after": "2"}), ErrorKind.RATE_LIMITED),
        (httpx.Response(503), ErrorKind.SERVER),
        (httpx.Response(200, text="not json"), ErrorKind.INVALID_RESPONSE),
        (httpx.Response(200, json={"choices": []}), ErrorKind.INVALID_RESPONSE),
    ],
)
async def test_errors_are_classified(
    mock_api: respx.MockRouter, http: httpx.AsyncClient, response: httpx.Response, kind: ErrorKind
) -> None:
    mock_api.post(f"{HOSTED}/chat/completions").mock(return_value=response)

    with pytest.raises(ProviderError) as info:
        await _client(http).generate("p")

    assert info.value.kind == kind


async def test_router_logs_unknown_price_as_zero(
    mock_api: respx.MockRouter, http: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="app.llm")
    mock_api.post(f"{LOCAL}/chat/completions").mock(return_value=openrouter_ok(answer_json()))

    result = await LLMRouter([_client(http, LOCAL, key="")]).complete_json("p", Answer)

    assert result.ok and result.cost_usd == 0.0
    record = json.loads(caplog.records[-1].getMessage())
    assert record["provider"] == "openai_compat"
    assert record["price_unknown"] is True


@pytest.mark.parametrize(
    "url",
    [
        "http://llm.example.test/v1",
        "http://192.168.1.10:11434/v1",
        "http://localhost.example.test/v1",
        "ftp://localhost/v1",
        "localhost:11434/v1",
        "https:///v1",
        "https://user:secret@llm.example.test/v1",
        "https://llm.example.test/v1?key=abc",
    ],
)
def test_bad_base_urls_are_rejected(url: str) -> None:
    assert base_url_problem(url) is not None


@pytest.mark.parametrize(
    "url", [HOSTED, LOCAL, "http://127.0.0.1:1234/v1", "https://localhost:8443/v1"]
)
def test_good_base_urls_are_accepted(url: str) -> None:
    assert base_url_problem(url) is None


async def test_factory_builds_openai_compat_for_any_slot(http: httpx.AsyncClient) -> None:
    settings = _settings(judge_provider="OpenAI_Compat", judge_model=MODEL, judge_base_url=LOCAL)

    primary = build_provider("LLM", settings, http)
    judge = build_provider("JUDGE", settings, http)

    assert isinstance(primary, OpenAICompatClient) and isinstance(judge, OpenAICompatClient)
    assert primary._base_url == HOSTED and judge._base_url == LOCAL


async def test_factory_rejects_http_to_a_remote_host_without_echoing_it(
    http: httpx.AsyncClient,
) -> None:
    with pytest.raises(LLMConfigError) as info:
        build_provider("LLM", _settings(llm_base_url="http://llm.example.test/v1"), http)

    assert "LLM_BASE_URL" in str(info.value)
    assert "example.test" not in str(info.value)


async def test_factory_requires_base_url_for_openai_compat_only(http: httpx.AsyncClient) -> None:
    with pytest.raises(LLMConfigError, match="LLM_BASE_URL"):
        build_provider("LLM", _settings(llm_base_url=""), http)
    gemini = _settings(llm_provider="gemini", llm_model="gemini-2.0-flash", llm_base_url="")
    assert isinstance(build_provider("LLM", gemini, http), GeminiClient)


async def test_empty_key_is_allowed_only_for_localhost(http: httpx.AsyncClient) -> None:
    local = build_provider("LLM", _settings(llm_api_key="", llm_base_url=LOCAL), http)
    assert isinstance(local, OpenAICompatClient)
    with pytest.raises(LLMConfigError, match="LLM_API_KEY is required"):
        build_provider("LLM", _settings(llm_api_key=""), http)


async def test_default_providers_are_unchanged(http: httpx.AsyncClient) -> None:
    assert Settings(_env_file=None).llm_provider == ""  # type: ignore[call-arg]
    settings = _settings(
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
        fallback_provider="openrouter",
        fallback_api_key=FAKE_KEY,
        fallback_model="mistralai/mistral-large",
    )
    providers = configured_providers(settings, http)
    assert [type(p) for p in providers] == [GeminiClient, OpenRouterClient]
