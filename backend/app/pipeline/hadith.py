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


# A known text found without «…» (D-052): at least this many words, so a common phrase
# such as «الأعمال بالنيات» alone inside a longer sentence is not taken for the hadith.
BARE_MIN_WORDS = 3
# Words that may surround an unquoted hadith without being part of it: the attribution
# formula, the ﷺ salutation spelled out, and «وفي الحديث».
_FRAME_WORDS = frozenset(
    match_key(
        "قال يقول رسول الله النبي ﷺ صلى عليه وسلم وفي في الحديث الشريف عن أنه رضي عنه"
    ).split()
)


def _forms(item: dict[str, Any]) -> list[str]:
    return [
        k for k in map(match_key, [item.get("text_ar", ""), *item.get("variants_ar", [])]) if k
    ]


def _covered(words: list[str], form: list[str]) -> set[int]:
    """Positions of ``words`` inside any whole-word occurrence of ``form``."""
    n = len(form)
    return {i + k for i in range(len(words) - n + 1) if words[i : i + n] == form for k in range(n)}


def find_bare(text: str) -> tuple[str, dict[str, Any], bool] | None:
    """A known hadith (or fabricated saying) whose text occurs in ``text`` as whole words.

    Returns ``(list_name, item, exact)``; ``exact`` when every word is covered by the item's
    forms (text and variants together) or belongs to the attribution frame. Fabricated
    first, then exact, then the longest form, so a forged saying never passes as sourced.
    """
    words = match_key(text).split()
    found = []
    for name in ("fabricated", "hadith"):
        for item in load_items(name):
            covered: set[int] = set()
            longest = 0
            for form in (f.split() for f in _forms(item)):
                if len(form) < BARE_MIN_WORDS and form != words:
                    continue
                hit = _covered(words, form)
                if hit:
                    covered |= hit
                    longest = max(longest, len(form))
            if covered:
                rest = (w for i, w in enumerate(words) if i not in covered)
                exact = all(w in _FRAME_WORDS for w in rest)
                found.append((name == "hadith", not exact, -longest, name, item, exact))
    if not found:
        return None
    *_rank, name, item, exact = min(found, key=lambda f: f[:3])
    return name, item, exact


def _resolve_bare(text: str) -> tuple[list[SourceRef], list[Flag]]:
    """No «…» quote (D-052): find the known text inside the segment and show it in full."""
    found = find_bare(text)
    if found is None:
        return [], [Flag(type="warn", key="hadith_unsourced")]
    name, item, exact = found
    if name == "fabricated":
        return [], [Flag(type="block", key="hadith_fabricated", detail=item.get("ruling", ""))]
    ref = f"{item.get('collection', '')} {item.get('number', '')}".strip()
    source = SourceRef(kind="hadith", ref=ref, grade=item.get("grade"))
    full = Flag(type="info", key="hadith_identified", detail=f"{ref}|{item.get('text_ar', '')}")
    if not exact:
        # Words beyond the hadith must not inherit its grade: show it, translate nothing.
        return [source], [full, Flag(type="warn", key="hadith_partial")]
    return [source], [Flag(type="info", key="hadith_sourced"), full]


def resolve_hadith(text: str) -> tuple[list[SourceRef], list[Flag]]:
    """Sources and flags for a segment classified as hadith; every «…» quote is checked."""
    keys = [key for key in map(match_key, _QUOTE_RE.findall(text)) if key]
    if not keys:
        return _resolve_bare(text)
    sources: list[SourceRef] = []
    flags: list[Flag] = []
    for key in keys:
        source, flag = _resolve_quote(key)
        if source:
            sources.append(source)
        if flag not in flags:
            flags.append(flag)
    return sources, flags
