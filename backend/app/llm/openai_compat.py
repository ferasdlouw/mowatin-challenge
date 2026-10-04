"""Any OpenAI-compatible ``/chat/completions`` endpoint (decision D-026).

This is the open-source / local option: Ollama or LM Studio on the same machine, or any
hosted OpenAI-compatible endpoint. The default providers (D-001..D-003) are unchanged; this
client is used only when a slot sets ``<SLOT>_PROVIDER=openai_compat`` and ``<SLOT>_BASE_URL``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx

from app.llm.base import SEED, TEMPERATURE, Completion
from app.llm.http import post_json
from app.llm.openrouter import extract_chat_text, extract_chat_usage

# Plain http is allowed only to this machine, so a key or user text never crosses a network
# unencrypted. Other loopback spellings are refused on purpose: the rule stays easy to audit.
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})


def base_url_problem(url: str) -> str | None:
    """Why ``url`` is not an allowed base URL, or ``None`` when it is.

    The reason never repeats the URL, so it is safe to put in an error message.
    """
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
    except ValueError:
        return "is not a valid URL"
    if parts.username or parts.password or parts.query or parts.fragment:
        return "must not contain credentials, a query or a fragment"
    if not host:
        return "must include a host"
    if parts.scheme == "https" or (parts.scheme == "http" and host in LOCAL_HOSTS):
        return None
    return "must use https (http is allowed only for localhost or 127.0.0.1)"


def is_local(url: str) -> bool:
    """True when ``url`` points at this machine (an empty API key is allowed only then)."""
    return urlsplit(url.strip()).hostname in LOCAL_HOSTS


class OpenAICompatClient:
    """Calls ``{base_url}/chat/completions`` with ``response_format: json_object``."""

    name = "openai_compat"

    def __init__(
        self, http: httpx.AsyncClient, api_key: str, model: str, timeout: float, base_url: str
    ) -> None:
        self._http = http
        self._api_key = api_key
        self.model = model
        self._timeout = timeout
        self._base_url = base_url.strip().rstrip("/")

    async def generate(self, prompt: str) -> Completion:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = await post_json(
            self._http,
            f"{self._base_url}/chat/completions",
            headers=headers,
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
