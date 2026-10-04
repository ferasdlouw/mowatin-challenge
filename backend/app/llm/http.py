"""The single HTTP edge shared by all providers."""

from __future__ import annotations

from typing import Any

import httpx

from app.llm.errors import ErrorKind, ProviderError, error_from_exception, error_from_status


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """POST a JSON body and return the decoded JSON object, or raise ``ProviderError``."""
    try:
        response = await client.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        raise error_from_exception(exc) from None
    if response.is_error:
        raise error_from_status(response)
    try:
        payload = response.json()
    except ValueError:
        raise ProviderError(ErrorKind.INVALID_RESPONSE, response.status_code) from None
    if not isinstance(payload, dict):
        raise ProviderError(ErrorKind.INVALID_RESPONSE, response.status_code)
    return payload


def as_int(value: object) -> int:
    """Token counts arrive as loosely typed JSON; anything odd counts as zero."""
    return value if isinstance(value, int) and value >= 0 else 0
