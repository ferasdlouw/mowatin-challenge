"""Level-D guard: a personal-ruling question is never answered, only referred.

Detection is the classifier's (`fatwa_like`); this module decides what the segment carries.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas import Flag, Level, TargetLang

REFERRAL_PATH = Path(__file__).resolve().parents[3] / "data" / "policy" / "referral.json"

LEVEL: Level = "D"


def _read_slot() -> dict:
    """referral.json, or {} while the slot is absent or a placeholder."""
    if not REFERRAL_PATH.exists():
        return {}
    data = json.loads(REFERRAL_PATH.read_text(encoding="utf-8"))
    return {} if data.get("status") == "placeholder" else data


@lru_cache(maxsize=1)
def referral_message_ar() -> str:
    """``message.ar`` from referral.json, or "" while the slot is absent or a placeholder."""
    return _read_slot().get("message", {}).get("ar", "").strip()


@lru_cache(maxsize=2)
def referral_text(lang: TargetLang) -> str:
    """``message.<lang>`` followed by one line per ``bodies.<lang>`` entry, or "" without a message.

    Shown to the target-language reader after the translated question, so it is never Arabic.
    """
    data = _read_slot()
    message = data.get("message", {}).get(lang, "").strip()
    if not message:
        return ""
    bodies = [
        f"- {body['name']} ({body['country']}): {body['url']}"
        for body in data.get("bodies", {}).get(lang, [])
        if body.get("name") and body.get("url")
    ]
    return "\n".join([message, *bodies])


def referral_flags() -> list[Flag]:
    """A warn flag that sends the segment to review, plus the referral advice when available.

    Two flags instead of one joined string, so each slot's text is shown exactly as written
    (D-017).
    """
    flags = [Flag(type="warn", key="fatwa_referral")]
    message = referral_message_ar()
    if message:
        flags.append(Flag(type="info", key="referral_message", msg=message))
    return flags
