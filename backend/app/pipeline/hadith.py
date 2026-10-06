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

from app.pipeline.normalize import canonicalize_for_matching, normalize_text
from app.schemas import Flag, SourceRef

HADITH_DIR = Path(__file__).resolve().parents[3] / "data" / "hadith"

_QUOTE_RE = re.compile(r"«([^»]*)»")
_NON_WORD_RE = re.compile(r"[^\w\s]")


def match_key(text: str) -> str:
    """Canonical, punctuation-free, single-spaced form used for matching (D-036, D-057).

    ``canonicalize_for_matching`` first: an alef wasla, a madda or hamza mark or a zero-width
    character must not turn a fabricated saying into an unknown one (block → warn), nor a
    sourced one into unsourced. ``normalize_text`` then unifies ta marbuta with ha, as before.
    """
    canonical = normalize_text(canonicalize_for_matching(text))
    return " ".join(_NON_WORD_RE.sub(" ", canonical).split())


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


def _canon(phrase: str) -> str:
    return re.escape(canonicalize_for_matching(phrase))


_PROPHET = f"(?:{_canon('رسول الله')}|{_canon('النبي')})"
_BLESSING = f"(?:ﷺ|{_canon('صلى الله عليه وسلم')})"
_SAID = f"(?:{_canon('قال')}|{_canon('يقول')})"
# Phrases that attribute what follows to the Prophet ﷺ, on the canonical text (D-036, D-068):
# «قال رسول الله ﷺ», «أن النبي ﷺ قال», «قال ﷺ», «قال عليه الصلاة والسلام». «عن النبي» alone is
# not one: «تحدثنا عن النبي ﷺ وسيرته» is ordinary speech.
_ATTRIBUTION_RE = re.compile(
    f"{_SAID}\\s+{_PROPHET}(?:\\s*{_BLESSING})?"
    f"|{_PROPHET}\\s*(?:{_BLESSING}\\s*)?{_SAID}"
    f"|{_canon('قال')}\\s*(?:{_BLESSING}|{_canon('عليه الصلاة والسلام')}|{_canon('عليه السلام')})"
)
_EDGE_PUNCT = " :،,.؛;-–\"'"
MIN_FABRICATED_WORDS = 3


def has_attribution(text: str) -> bool:
    """``text`` attributes words to the Prophet ﷺ."""
    return _ATTRIBUTION_RE.search(canonicalize_for_matching(text)) is not None


def fabricated_in(text: str) -> str | None:
    """A saying of the fabricated list found as whole words anywhere in ``text`` (D-068), even
    with no attribution: «اطلبوا العلم ولو في الصين» circulates bare."""
    key = f" {match_key(text)} "
    for item in load_items("fabricated"):
        for form in (item.get("text_ar", ""), *item.get("variants_ar", [])):
            form_key = match_key(form)
            if len(form_key.split()) >= MIN_FABRICATED_WORDS and f" {form_key} " in key:
                return form
    return None


def is_approved_text(text: str) -> bool:
    """The whole of ``text`` is a saying of the approved list (D-068: «الدين النصيحة» alone)."""
    key = match_key(text)
    return bool(key) and _find(key, "hadith") is not None


def hadith_quotes(text: str) -> list[str]:
    """The sayings of a hadith segment: its «…» quotes; else the words after an attribution
    phrase (as for an unbracketed verse, D-041); else a fabricated saying inside it; else the
    whole segment (an approved saying written alone)."""
    quotes = _QUOTE_RE.findall(text)
    if quotes:
        return quotes
    canon = canonicalize_for_matching(text)
    found = _ATTRIBUTION_RE.search(canon)
    if found:
        rest = canon[found.end() :].strip(_EDGE_PUNCT)
        return [rest] if match_key(rest) else []
    fabricated = fabricated_in(text)
    return [fabricated] if fabricated else [text]


def unsourced_quotes(text: str) -> list[str]:
    """The sayings found in neither the approved nor the fabricated list."""
    return [
        quote
        for quote in hadith_quotes(text)
        if match_key(quote) and _resolve_quote(match_key(quote))[1].key == "hadith_unsourced"
    ]


def resolve_hadith(text: str) -> tuple[list[SourceRef], list[Flag]]:
    """Sources and flags for a segment classified as hadith; every «…» quote is checked."""
    keys = [key for key in map(match_key, hadith_quotes(text)) if key]
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
