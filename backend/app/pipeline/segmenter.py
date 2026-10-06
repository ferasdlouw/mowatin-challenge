import re

from app.pipeline.classifier import is_fatwa_like
from app.pipeline.quran import VERSE_REF_RE, VERSE_SPAN_RE, lead_in_start

# A Quran span (ornate parentheses U+FD3F...U+FD3E) or a hadith span (guillemets) is one token.
_TOKEN_RE = re.compile(r"(﴿[^﴾]*﴾|«[^»]*»|.)", re.DOTALL)
# «?» too (D-064): a ruling question typed with a Latin question mark must end its sentence.
_SENTENCE_ENDS = {".", "؟", "?", "!", "\n"}
_CLAUSE_ENDS = {"،", "؛"}
_WORD_RE = re.compile(r"\w")


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
    for sentence in _split(_join_decimals(_TOKEN_RE.findall(text)), _SENTENCE_ENDS):
        if is_fatwa_like("".join(sentence)):
            parts = ["".join(sentence)]
        else:
            clauses = _split(sentence, _CLAUSE_ENDS)
            parts = [piece for clause in clauses for piece in _split_verses("".join(clause))]
        segments.extend(s for s in (part.strip() for part in parts) if s)
    return segments


def _join_decimals(tokens: list[str]) -> list[str]:
    """A dot with a digit on each side («3.5») joins the two digits into one token, so it never
    ends a sentence (D-064). Tokens are only regrouped: their text and order stay the same."""
    joined: list[str] = []
    i = 0
    while i < len(tokens):
        piece = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if piece == "." and joined and joined[-1][-1:].isdigit() and nxt.isdigit():
            joined[-1] += piece + nxt
            i += 2
            continue
        joined.append(piece)
        i += 1
    return joined


def _split_verses(clause: str) -> list[str]:
    """Each verse in ornate brackets is its own piece, with the words that introduce it and a
    sura reference right after it (D-051). The Quran handler outputs the verse's approved
    translation only, so commentary next to a verse must be its own segment to be translated.
    """
    pieces: list[str] = []
    pos = 0
    for match in VERSE_SPAN_RE.finditer(clause):
        before = clause[pos : match.start()]
        lead = pos + lead_in_start(before)
        ref = VERSE_REF_RE.match(clause, match.end())
        end = ref.end() if ref else match.end()
        pieces += [clause[pos:lead], clause[lead:end]]
        pos = end
    pieces.append(clause[pos:])
    return _merge_wordless(pieces)


def _merge_wordless(pieces: list[str]) -> list[str]:
    """A piece without a letter or digit («.», «: », spaces) joins the piece before it (or the
    next one at the start), so punctuation never becomes a segment and pieces stay contiguous.
    """
    merged: list[str] = []
    carry = ""
    for piece in pieces:
        if _WORD_RE.search(piece):
            merged.append(carry + piece)
            carry = ""
        elif merged:
            merged[-1] += piece
        else:
            carry += piece
    return merged or [carry]


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
