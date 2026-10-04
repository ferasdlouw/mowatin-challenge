"""User-facing flags the LLM layer can raise, with text from ``flags.ar.json``."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas import Flag

FLAGS_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "messages" / "flags.ar.json"
)
FALLBACK_KEY = "provider_fallback"


@lru_cache(maxsize=1)
def _messages() -> dict[str, str]:
    try:
        data = json.loads(FLAGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    messages = data.get("messages") if isinstance(data, dict) else None
    return messages if isinstance(messages, dict) else {}


def fallback_flag() -> Flag:
    """Info flag recorded whenever the fallback provider produced the answer."""
    return Flag(type="info", key=FALLBACK_KEY, msg=_messages().get(FALLBACK_KEY, ""))
