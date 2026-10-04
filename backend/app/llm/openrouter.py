"""OpenRouter client (OpenAI-compatible) — fallback provider, decision D-002."""

from __future__ import annotations

from typing import Any

import httpx

from app.llm.base import SEED, TEMPERATURE, Completion, Usage
from app.llm.errors import ErrorKind, ProviderError
from app.llm.http import as_int, post_json

BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterClient:
    """Calls ``/chat/completions`` with ``response_format: json_object``."""

    name = "openrouter"

    def __init__(self, http: httpx.AsyncClient, api_key: str, model: str, timeout: float) -> None:
        self._http = http
        self._api_key = api_key
        self.model = model
        self._timeout = timeout

    async def generate(self, prompt: str) -> Completion:
        payload = await post_json(
            self._http,
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            body=self._body(prompt),
            timeout=self._timeout,
        )
        return Completion(text=extract_chat_text(payload), usage=extract_chat_usage(payload))

    def _body(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": TEMPERATURE,
            "seed": SEED,
            "response_format": {"type": "json_object"},
        }


def extract_chat_text(payload: dict[str, Any]) -> str:
    """Text of an OpenAI-style ``/chat/completions`` reply (shared with ``openai_compat``)."""
    # OpenRouter can relay an upstream failure as HTTP 200 with an "error" object.
    if "error" in payload:
        raise ProviderError(ErrorKind.SERVER)
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ProviderError(ErrorKind.INVALID_RESPONSE) from None
    if not isinstance(text, str) or not text.strip():
        raise ProviderError(ErrorKind.INVALID_RESPONSE)
    return text


def extract_chat_usage(payload: dict[str, Any]) -> Usage:
    """Token counts of an OpenAI-style reply; missing or odd values count as zero."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return Usage()
    return Usage(
        prompt_tokens=as_int(usage.get("prompt_tokens")),
        output_tokens=as_int(usage.get("completion_tokens")),
    )
