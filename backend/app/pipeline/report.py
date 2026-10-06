"""Client-facing report: flag text, review queue, summary and disclosure (ARCHITECTURE.md §4)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.schemas import Flag, Segment, SegmentFlag, Summary, TranslateResponse

MESSAGES_PATH = Path(__file__).resolve().parents[3] / "data" / "messages" / "flags.ar.json"

REVIEW_THRESHOLD = 0.75

# Fixed by the frozen contract (ARCHITECTURE.md §4 and frontend api.js); flags.ar.json has no
# `disclosure` key yet, so this is the one user-facing string that lives in code (D-017).
DISCLOSURE = "مخرجات مدعومة بالذكاء الاصطناعي، وتحتاج مراجعة بشرية مؤهلة قبل النشر."

# Flags whose `detail` is the value of a single placeholder in their message.
_SINGLE_PLACEHOLDER = {"hadith_fabricated": "ruling", "term_check_failed": "term"}

_UNFILLED_RE = re.compile(r"\{[a-z_]+\}")

# Phase SEC keys: their text is in flags.ar.json; if a key is ever removed, the closest
# existing message is shown instead, so these flags never fail a request.
_FALLBACK_KEYS = {
    "limit_reached": "general_error",
    "translation_unavailable": "general_error",
    "injection_suspected": "low_confidence",
    "raw_unprotected": "low_confidence",
    # D-051: until flags.ar.json has its own text (content slot, Eng. Rudaina).
    "quran_extra_text": "low_confidence",
    "quran_partial": "low_confidence",
}


class MessageKeyError(LookupError):
    """A flag key has no message in flags.ar.json, or a placeholder was left unfilled."""


@lru_cache(maxsize=1)
def load_messages() -> dict[str, str]:
    """The `messages` map of flags.ar.json, read once."""
    data = json.loads(MESSAGES_PATH.read_text(encoding="utf-8"))
    return data.get("messages", {})


def _placeholders(flag: Flag) -> dict[str, str]:
    """Placeholder values each stage packs into ``Flag.detail``."""
    if flag.key == "quran_mismatch":
        ref, _, correct_text = flag.detail.partition("|")
        return {"ref": ref, "correct_text": correct_text}
    if flag.key == "quran_diacritized":
        ref, _, verse = flag.detail.partition("|")
        return {"ref": ref, "verse": verse}
    if flag.key == "quran_ambiguous":
        return {"refs": flag.detail, "ref": flag.detail.split(",")[0].strip()}
    if flag.key in ("avoid_word_found", "compare_why_term"):
        term, _, word = flag.detail.partition("|")
        return {"term": term, "word": word}
    if flag.key in _SINGLE_PLACEHOLDER:
        return {_SINGLE_PLACEHOLDER[flag.key]: flag.detail}
    return {}


def render_flag(flag: Flag) -> SegmentFlag:
    """Internal flag → ``{severity, text}``.

    ``msg`` already holds text taken verbatim from a content slot; otherwise the text comes
    from flags.ar.json by key. Never falls back to the key or to English.
    """
    if flag.msg:
        return SegmentFlag(severity=flag.type, text=flag.msg)
    messages = load_messages()
    template = messages.get(flag.key)
    if template is None and flag.key in _FALLBACK_KEYS:
        template = messages.get(_FALLBACK_KEYS[flag.key])
    if template is None:
        raise MessageKeyError(f"flags.ar.json has no message for key {flag.key!r}")
    text = template
    for name, value in _placeholders(flag).items():
        text = text.replace("{" + name + "}", value)
    if _UNFILLED_RE.search(text):
        raise MessageKeyError(f"unfilled placeholder in message {flag.key!r}")
    return SegmentFlag(severity=flag.type, text=text)


def needs_review(segment: Segment) -> bool:
    """Same rule as ``needsReview()`` in ``frontend/src/lib/api.js``:
    ``(s.confidence != null && s.confidence < 0.75) || s.flags.some((f) => f.severity !== 'info')``.
    """
    low = segment.confidence is not None and segment.confidence < REVIEW_THRESHOLD
    return low or any(f.severity != "info" for f in segment.flags)


def assemble(segments: list[Segment]) -> TranslateResponse:
    """Build the contract response (summary + review queue + disclosure) from finished segments."""
    queue = [s.id for s in segments if needs_review(s)]
    avg = sum(s.confidence for s in segments) / len(segments) if segments else 0.0
    return TranslateResponse(
        segments=segments,
        summary=Summary(segments=len(segments), flagged=len(queue), avg_confidence=round(avg, 2)),
        review_queue=queue,
        disclosure=DISCLOSURE,
    )
