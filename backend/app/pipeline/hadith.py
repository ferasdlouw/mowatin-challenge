"""Hadith handler: match a quoted saying against the approved and fabricated lists.

Never presents an unsourced saying as authentic: only a match in ``data/hadith/hadith.json``
yields a source; anything else is flagged and sent to review (ARCHITECTURE.md §3).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.pipeline.normalize import normalize_text
from app.schemas import Flag, SourceRef

HADITH_DIR = Path(__file__).resolve().parents[3] / "data" / "hadith"

_QUOTE_RE = re.compile(r"«([^»]*)»")
_NON_WORD_RE = re.compile(r"[^\w\s]")


def match_key(text: str) -> str:
    """Normalized, punctuation-free, single-spaced form used for matching."""
    return " ".join(_NON_WORD_RE.sub(" ", normalize_text(text)).split())


@lru_cache(maxsize=2)
def load_items(name: str) -> tuple[dict[str, Any], ...]:
    """Items of ``data/hadith/<name>.json``; an absent or placeholder slot is empty."""
    path = HADITH_DIR / f"{name}.json"
    if not path.exists():
        return ()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") == "placeholder":
        return ()
    return tuple(data.get("items", []))


def _matches(quote_key: str, item: dict[str, Any]) -> bool:
    """The whole quote equals the item's text or one of its variants.

    Exact only: a quote that merely contains an approved text may carry an added clause,
    which must not inherit the hadith's grade.
    """
    forms = [item.get("text_ar", ""), *item.get("variants_ar", [])]
    return any(quote_key == match_key(form) for form in forms if form)


def _find(quote_key: str, name: str) -> dict[str, Any] | None:
    return next((item for item in load_items(name) if _matches(quote_key, item)), None)


def _resolve_quote(quote_key: str) -> tuple[SourceRef | None, Flag]:
    """Fabricated is checked first so a forged saying can never pass as sourced."""
    fabricated = _find(quote_key, "fabricated")
    if fabricated:
        return None, Flag(
            type="block", key="hadith_fabricated", detail=fabricated.get("ruling", "")
        )
    sourced = _find(quote_key, "hadith")
    if sourced:
        ref = f"{sourced.get('collection', '')} {sourced.get('number', '')}".strip()
        source = SourceRef(kind="hadith", ref=ref, grade=sourced.get("grade"))
        return source, Flag(type="info", key="hadith_sourced")
    return None, Flag(type="warn", key="hadith_unsourced")


def resolve_hadith(text: str) -> tuple[list[SourceRef], list[Flag]]:
    """Sources and flags for a segment classified as hadith; every «…» quote is checked."""
    keys = [key for key in map(match_key, _QUOTE_RE.findall(text)) if key]
    if not keys:
        return [], [Flag(type="warn", key="hadith_unsourced")]
    sources: list[SourceRef] = []
    flags: list[Flag] = []
    for key in keys:
        source, flag = _resolve_quote(key)
        if source:
            sources.append(source)
        if flag not in flags:
            flags.append(flag)
    return sources, flags
