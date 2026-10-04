"""Prompt-injection guards (Phase SEC, F4, decision D-037).

Untrusted text (the user's text, and an LLM's output that is fed to the next prompt) is put
inside data tags. ``neutralize_tags`` keeps it from closing or opening those tags; the
post-checks send a segment to review when its output looks steered.
"""

from __future__ import annotations

import re

from app.pipeline.normalize import canonicalize_for_matching, strip_format_chars

DATA_TAGS = ("user_text", "original", "translation")

# ASCII, fullwidth and small-form angle brackets: all read as a tag by a model.
_OPEN = "<" + chr(0xFF1C) + chr(0xFE64)
_CLOSE = ">" + chr(0xFF1E) + chr(0xFE65)
_TAG_RE = re.compile(
    rf"[{_OPEN}]\s*/?\s*(?:{'|'.join(DATA_TAGS)})\b[^{_CLOSE}]*[{_CLOSE}]?",
    re.IGNORECASE,
)
# Shown instead of "<": a single angle quotation mark, which no prompt treats as a tag.
_SAFE_OPEN = chr(0x2039)

# Phrases that address the model instead of being content (English, French, Arabic). Kept
# narrow: "you are now" or "new instructions" also occur in ordinary religious texts.
_OVERRIDE_PHRASES = (
    "ignore previous instructions",
    "ignore all previous",
    "ignore the above",
    "disregard previous",
    "disregard the above",
    "disregard all previous",
    "system prompt",
    "ignore les instructions",
    "ignorez les instructions",
    "ignore toutes les instructions",
    "تجاهل التعليمات",
    "تجاهل جميع التعليمات",
    "تجاهل كل التعليمات",
    "تجاهل ما سبق",
    "انس التعليمات",
)
_SCORE_RE = re.compile(r"""["']?score["']?\s*[:=]""", re.IGNORECASE)

# Output/source length ratio bounds, from the dev raw run of 2026-10-03 (112 segments:
# observed 0.73-5.75): half the lowest and 1.5 x the highest. Short sources vary too much.
MIN_RATIO, MAX_RATIO = 0.35, 8.6
MIN_SOURCE_CHARS = 20


def neutralize_tags(text: str) -> str:
    """``text`` with every opening or closing data tag defused, so it stays inside its block.

    Format characters are dropped first, so a zero-width char inside ``</user_text>`` cannot
    hide the tag from this check while a model still reads it.
    """
    return _TAG_RE.sub(lambda m: _SAFE_OPEN + m.group(0)[1:], strip_format_chars(text))


def has_override_marker(text: str) -> bool:
    """A data tag, an instruction-override phrase or a score assignment in ``text``."""
    if _TAG_RE.search(strip_format_chars(text)):
        return True
    canon = " ".join(canonicalize_for_matching(text).lower().split())
    if any(canonicalize_for_matching(phrase) in canon for phrase in _OVERRIDE_PHRASES):
        return True
    return bool(_SCORE_RE.search(text))


def ratio_out_of_bounds(source: str, output: str) -> bool:
    """Output much shorter or longer than any dev translation of a source this long."""
    if len(source.strip()) < MIN_SOURCE_CHARS:
        return False
    ratio = len(output) / len(source)
    return not MIN_RATIO <= ratio <= MAX_RATIO


def looks_steered(source: str, output: str) -> bool:
    """Deterministic post-check: ``True`` sends the segment to review (warn flag)."""
    return (
        has_override_marker(source)
        or has_override_marker(output)
        or ratio_out_of_bounds(source, output)
    )
