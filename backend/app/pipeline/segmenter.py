import re

from app.pipeline.classifier import is_fatwa_like
from app.pipeline.hadith import find_bare

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


def _keep_hadith_whole(clauses: list[list[str]]) -> list[list[str]]:
    """Join the clauses that hold a known hadith (D-052), widest run first.

    The run whose text is the hadith and its attribution only becomes one segment, the
    clauses around it stay apart (a comment after it is translated as plain text). With no
    such run the sentence stays whole, and the hadith handler sends the extra words to review.
    """
    n = len(clauses)
    for size in range(n, 0, -1):
        for start in range(n - size + 1):
            merged = [token for clause in clauses[start : start + size] for token in clause]
            found = find_bare("".join(merged))
            if found is not None and found[2]:
                return [*clauses[:start], merged, *clauses[start + size :]]
    return [[token for clause in clauses for token in clause]]


def segment(text: str) -> list[str]:
    """Split text into sentences, then clauses; Quran and hadith spans stay intact.

    A sentence with a fatwa signal stays one segment (D-024): split at «،», its personal
    context («أنا أعيش في فرنسا،») would become a general segment outside the referral.
    A sentence holding a known hadith stays whole too (D-052), so «إنما الأعمال بالنيات،
    وإنما لكل امرئ ما نوى» is matched as one text, not as two clauses.
    """
    if not text:
        return []
    segments: list[str] = []
    for sentence in _split(_TOKEN_RE.findall(text), _SENTENCE_ENDS):
        joined = "".join(sentence)
        if is_fatwa_like(joined):
            parts = [sentence]
        else:
            parts = _split(sentence, _CLAUSE_ENDS)
            if find_bare(joined) is not None:
                parts = _keep_hadith_whole(parts)
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
