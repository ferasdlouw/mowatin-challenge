"""Shared fixtures for LLM-layer tests. All HTTP is mocked with respx; no network."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import respx
from pydantic import BaseModel, ConfigDict

from app.llm.gemini import BASE_URL as GEMINI_BASE
from app.llm.gemini import GeminiClient
from app.llm.openrouter import BASE_URL as OPENROUTER_BASE
from app.llm.openrouter import OpenRouterClient
from app.llm.router import LLMRouter

FAKE_KEY = "test-key-not-real"
GEMINI_MODEL = "gemini-2.0-flash"
OPENROUTER_MODEL = "mistralai/mistral-large"
GEMINI_URL = f"{GEMINI_BASE}/models/{GEMINI_MODEL}:generateContent"
OPENROUTER_URL = f"{OPENROUTER_BASE}/chat/completions"
TIMEOUT = 5.0


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    translation: str


def gemini_ok(text: str, prompt_tokens: int = 100, output_tokens: int = 20) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
            "usageMetadata": {
                "promptTokenCount": prompt_tokens,
                "candidatesTokenCount": output_tokens,
            },
        },
    )


def openrouter_ok(text: str, prompt_tokens: int = 90, output_tokens: int = 15) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": output_tokens},
        },
    )


def answer_json(translation: str = "Patience is light.") -> str:
    return json.dumps({"translation": translation})


@pytest.fixture()
def mock_api() -> Iterator[respx.MockRouter]:
    # assert_all_mocked: any request to an unmocked URL fails the test instead of hitting the network.
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        yield router


@pytest.fixture()
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture()
def gemini(http: httpx.AsyncClient) -> GeminiClient:
    return GeminiClient(http, FAKE_KEY, GEMINI_MODEL, TIMEOUT)


@pytest.fixture()
def openrouter(http: httpx.AsyncClient) -> OpenRouterClient:
    return OpenRouterClient(http, FAKE_KEY, OPENROUTER_MODEL, TIMEOUT)


@pytest.fixture()
def sleeps() -> list[float]:
    return []


@pytest.fixture()
def fake_sleep(sleeps: list[float]) -> Any:
    async def _sleep(seconds: float) -> None:
        sleeps.append(seconds)

    return _sleep


@pytest.fixture()
def router(gemini: GeminiClient, openrouter: OpenRouterClient, fake_sleep: Any) -> LLMRouter:
    return LLMRouter([gemini, openrouter], sleep=fake_sleep)
