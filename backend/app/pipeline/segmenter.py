import re

from app.pipeline.classifier import is_fatwa_like

# A Quran span (ornate parentheses U+FD3F...U+FD3E) or a hadith span (guillemets) is one token.
_TOKEN_RE = re.compile(r"(﴿[^﴾]*﴾|«[^»]*»|.)", re.DOTALL)
_SENTENCE_ENDS = {".", "؟", "!", "\n"}
_CLAUSE_ENDS = {"،", "؛"}


def _split(tokens: list[str], ends: set[str]) -> list[list[str]]:
    """Group tokens into runs that each end at one of ``ends`` (the last run may not)."""
    groups: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        current.append(token)
        if token in ends:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def segment(text: str) -> list[str]:
    """Split text into sentences, then clauses; Quran and hadith spans stay intact.

    A sentence with a fatwa signal stays one segment (D-024): split at «،», its personal
    context («أنا أعيش في فرنسا،») would become a general segment outside the referral.
    """
    if not text:
        return []
    segments: list[str] = []
    for sentence in _split(_TOKEN_RE.findall(text), _SENTENCE_ENDS):
        parts = [sentence] if is_fatwa_like("".join(sentence)) else _split(sentence, _CLAUSE_ENDS)
        segments.extend(s for s in ("".join(part).strip() for part in parts) if s)
    return segments


def segment_capped(text: str, max_segments: int) -> tuple[list[str], str]:
    """The first ``max_segments`` segments, and the rest of ``text`` as one string (D-034).

    Segments are stripped substrings of ``text`` in order, so the rest starts right after
    the last kept segment. ``""`` when nothing was cut.
    """
    parts = segment(text)
    if len(parts) <= max_segments:
        return parts, ""
    end = 0
    for part in parts[:max_segments]:
        end = text.index(part, end) + len(part)
    return parts[:max_segments], text[end:].strip()
