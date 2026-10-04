"""Google Gemini (AI Studio) client — primary provider, decision D-001."""

from __future__ import annotations

from typing import Any

import httpx

from app.llm.base import SEED, TEMPERATURE, Completion, Usage
from app.llm.errors import ErrorKind, ProviderError
from app.llm.http import as_int, post_json

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiClient:
    """Calls ``models/{model}:generateContent`` in JSON mode.

    The key goes in the ``x-goog-api-key`` header, never in the URL, so it
    cannot leak through logged URLs or exception messages.
    """

    name = "gemini"

    def __init__(self, http: httpx.AsyncClient, api_key: str, model: str, timeout: float) -> None:
        self._http = http
        self._api_key = api_key
        self.model = model
        self._timeout = timeout

    async def generate(self, prompt: str) -> Completion:
        payload = await post_json(
            self._http,
            f"{BASE_URL}/models/{self.model}:generateContent",
            headers={"x-goog-api-key": self._api_key},
            body=self._body(prompt),
            timeout=self._timeout,
        )
        return Completion(text=_extract_text(payload), usage=_extract_usage(payload))

    @staticmethod
    def _body(prompt: str) -> dict[str, Any]:
        return {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": TEMPERATURE,
                "seed": SEED,
                "responseMimeType": "application/json",
            },
        }


def _extract_text(payload: dict[str, Any]) -> str:
    # A safety block returns 200 with no candidates; treat it like any bad answer.
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        # Thinking models (Gemma 4) return their reasoning as parts marked
        # ``thought``; only the remaining parts are the JSON answer.
        text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError(ErrorKind.INVALID_RESPONSE) from None
    if not text.strip():
        raise ProviderError(ErrorKind.INVALID_RESPONSE)
    return text


def _extract_usage(payload: dict[str, Any]) -> Usage:
    meta = payload.get("usageMetadata")
    if not isinstance(meta, dict):
        return Usage()
    return Usage(
        prompt_tokens=as_int(meta.get("promptTokenCount")),
        output_tokens=as_int(meta.get("candidatesTokenCount")),
    )
