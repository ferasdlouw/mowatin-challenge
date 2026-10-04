import json
import logging
import math
import re
from functools import lru_cache
from pathlib import Path

from app.pipeline.classifier import QURAN_ATTRIBUTIONS
from app.pipeline.normalize import canonicalize_for_matching, normalize_text
from app.schemas import Flag, SourceRef

logger = logging.getLogger(__name__)


def edit_distance(s1: str, s2: str) -> int:
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2 + 1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
        distances = distances_
    return distances[-1]


TANZIL_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "quran"
    / "tanzil"
    / "quran-simple-clean.txt"
)
# The same Tanzil Simple text with full tashkeel (D-044): shown, never matched on.
TANZIL_DIACRITIZED_PATH = TANZIL_PATH.with_name("quran-simple.txt")
TRANSLATIONS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "quran" / "translations"
)

# Near-match bounds (D-035); see QuranIndex.find_near.
NEAR_MIN_CHARS = 8
NEAR_MAX_CANDIDATES = 20
NEAR_CELL_BUDGET = 400_000
# resolve_quran accepts a near match only below this error rate.
NEAR_MAX_RATE = 0.3

# Verses quoted without ornate brackets (D-041): only a whole-word run of at least this many
# words counts.
UNBRACKETED_MIN_WORDS = 3
# A segment with no formula and no brackets (D-043): a whole segment of at least
# BARE_GRAM words, or a run of at least BARE_MIN_RUN words inside it, found in one verse.
BARE_GRAM = 4
BARE_MIN_RUN = 7
# A whole segment of exactly UNBRACKETED_MIN_WORDS words counts only when it occurs in one
# place (D-047): «إنما المؤمنون إخوة» is the verse, «إن شاء الله» (6 places) stays speech.
_PLAIN_QUOTES = re.compile(r"\(([^()]*)\)|«([^«»]*)»|\"([^\"]*)\"|“([^“”]*)”")
_NON_LETTERS = re.compile(r"[^ء-ي]+")

QURAN_CLEAN_RE = re.compile(r"[\u06D6-\u06ED\u0670\u200C-\u200F\u202A-\u202E\uFEFF]")


class QuranIndex:
    def __init__(self):
        self.verses = []
        self.giant_string = ""
        self.char_to_verse_idx = []
        self.verse_offsets = []

        if TANZIL_PATH.exists():
            with open(TANZIL_PATH, encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line:
                        continue
                    parts = line.split("|", 2)
                    if len(parts) == 3:
                        sura, aya, txt = parts
                        # extra clean for pause marks and superscript alifs
                        txt_clean = QURAN_CLEAN_RE.sub("", txt)
                        # A pause mark is its own token in the file: once removed, its two
                        # spaces would block every quote across it (D-046).
                        norm_txt = " ".join(normalize_text(txt_clean).split())
                        v_idx = len(self.verses)
                        self.verse_offsets.append(len(self.giant_string))
                        self.verses.append(
                            {
                                "sura": sura,
                                "aya": aya,
                                "ref": f"{sura}:{aya}",
                                "text": txt,
                                "norm": norm_txt,
                            }
                        )
                        self.char_to_verse_idx.extend([v_idx] * (len(norm_txt) + 1))
                        self.giant_string += norm_txt + " "
        self.diacritized = _load_diacritized(self.verses)

        self.translations = {}
        for lang in ["en", "fr"]:
            file_path = TRANSLATIONS_DIR / f"{lang}.json"
            if file_path.exists():
                with open(file_path, encoding="utf-8") as f:
                    self.translations[lang] = json.load(f)

    def get_translation(
        self, lang: str, start_idx: int, end_idx: int
    ) -> tuple[str | None, str | None]:
        """Returns (translated_text, edition) or (None, None) if missing."""
        if lang not in self.translations:
            return None, None
        data = self.translations[lang]
        if data.get("status") == "placeholder":
            return None, None

        verses_dict = data.get("verses", {})
        texts = []
        for i in range(start_idx, end_idx + 1):
            ref = self.verses[i]["ref"]
            if ref not in verses_dict:
                return None, None
            texts.append(verses_dict[ref])

        return " ".join(texts), data.get("edition")

    def verse_range(self, span: tuple[int, int]) -> tuple[int, int]:
        """First and last verse of a ``[start, end)`` span of ``giant_string``."""
        return self.char_to_verse_idx[span[0]], self.char_to_verse_idx[span[1] - 1]

    def find_exact(self, query_norm: str) -> list[tuple[int, int]]:
        return [self.verse_range(span) for span in self.exact_spans(query_norm)]

    def exact_spans(self, query_norm: str) -> list[tuple[int, int]]:
        """Every occurrence of ``query_norm`` in ``giant_string``, overlaps included."""
        spans = []
        start = 0
        while query_norm:
            idx = self.giant_string.find(query_norm, start)
            if idx == -1:
                break
            spans.append((idx, idx + len(query_norm)))
            start = idx + 1
        return spans

    def find_words(self, words: list[str]) -> list[tuple[int, int]]:
        """Verse ranges where ``words`` occur in order as whole words."""
        return [self.verse_range(span) for span in self.word_spans(words)]

    def word_spans(self, words: list[str]) -> list[tuple[int, int]]:
        """Spans of ``giant_string`` where ``words`` occur in order as whole words."""
        pattern = re.compile(r"(?<!\S)" + r"\s+".join(map(re.escape, words)) + r"(?!\S)")
        return [m.span() for m in pattern.finditer(self.giant_string)]

    def diacritized_text(self, span: tuple[int, int]) -> str | None:
        """The words of ``span`` as the diacritized Tanzil line writes them (D-044).

        Each verse part is a slice of its line, so every mark comes from the file. ``None``
        when the span starts or ends inside a word, or a verse it covers does not align.
        """
        v_start, v_end = self.verse_range(span)
        parts = []
        for v in range(v_start, v_end + 1):
            if v not in self.diacritized:
                return None
            line, marked = self.diacritized[v]
            words = [m.span() for m in re.finditer(r"\S+", self.verses[v]["norm"])]
            starts = [s for s, _e in words]
            ends = [e for _s, e in words]
            lo = span[0] - self.verse_offsets[v] if v == v_start else starts[0]
            hi = span[1] - self.verse_offsets[v] if v == v_end else ends[-1]
            if lo not in starts or hi not in ends:
                return None
            parts.append(line[marked[starts.index(lo)][0] : marked[ends.index(hi)][1]])
        return " ".join(parts)

    def diacritized_verse(self, v: int) -> str | None:
        """Whole diacritized line of verse ``v``, or ``None`` if it does not align."""
        found = self.diacritized.get(v)
        return found[0] if found else None

    def has_grams(self, words: list[str]) -> bool:
        """True when every ``BARE_GRAM``-word window of ``words`` occurs inside some verse."""
        grams = self._grams()
        return len(words) >= BARE_GRAM and all(
            tuple(words[i : i + BARE_GRAM]) in grams for i in range(len(words) - BARE_GRAM + 1)
        )

    def _grams(self) -> frozenset[tuple[str, ...]]:
        """Every ``BARE_GRAM``-word window of every verse, built on first use and kept."""
        if not hasattr(self, "_gram_set"):
            grams = set()
            for verse in self.verses:
                w = verse["norm"].split()
                grams.update(tuple(w[i : i + BARE_GRAM]) for i in range(len(w) - BARE_GRAM + 1))
            self._gram_set = frozenset(grams)
        return self._gram_set

    def find_near(self, query_norm: str) -> tuple[int, int, float]:
        """Returns (v_start, v_end, error_rate). For simplicity, checks single verses.

        Bounded (D-035): pure-Python edit distance over every verse froze the event loop for
        29 s on a 20-letter junk quote. Only queries of ``NEAR_MIN_CHARS`` or more are tried,
        only verses sharing at least half the query's words (at least one) are candidates,
        the ``NEAR_MAX_CANDIDATES`` with the most shared words are scored first, and scoring
        stops once ``NEAR_CELL_BUDGET`` edit-distance cells are spent. A query that finds
        nothing ends as ``quran_not_found`` + review.
        """
        best_v = 0
        best_rate = 1.0

        query_words = set(query_norm.split())
        if not query_words or len(query_norm) < NEAR_MIN_CHARS:
            return 0, 0, 1.0
        needed = max(1, math.ceil(len(query_words) / 2))

        candidates = []
        # A verse shorter than (1 - NEAR_MAX_RATE) x the query has rate >= NEAR_MAX_RATE
        # whatever it says, so it can never be accepted and is not scored.
        min_verse_len = len(query_norm) * (1 - NEAR_MAX_RATE)
        for i, v in enumerate(self.verses):
            if len(v["norm"]) < min_verse_len:
                continue
            overlap = len(query_words & self._verse_words(i))
            if overlap >= needed:
                candidates.append((-overlap, i))
        candidates.sort()

        spent = 0
        for _overlap, i in candidates[:NEAR_MAX_CANDIDATES]:
            v_norm = self.verses[i]["norm"]
            spent += _near_cells(len(query_norm), len(v_norm))
            if spent > NEAR_CELL_BUDGET:
                break
            rate = _best_rate(query_norm, v_norm)
            # Ties go to the earlier verse, as when every verse was scanned in order.
            if rate < best_rate or (rate == best_rate and rate < 1.0 and i < best_v):
                best_rate = rate
                best_v = i

        return best_v, best_v, best_rate

    def _verse_words(self, i: int) -> frozenset[str]:
        """Word set of verse ``i``, built on first use and kept (near-match candidate filter)."""
        verse = self.verses[i]
        if "words" not in verse:
            verse["words"] = frozenset(verse["norm"].split())
        return verse["words"]


def _near_cells(query_len: int, verse_len: int) -> int:
    """Edit-distance cells ``_best_rate`` computes for one verse."""
    if query_len < verse_len:
        return (verse_len - query_len + 1) * query_len * query_len
    return query_len * verse_len


def _best_rate(query_norm: str, v_norm: str) -> float:
    """Lowest edit-distance rate of the query against the verse (sliding window if shorter)."""
    if len(query_norm) < len(v_norm):
        return min(
            edit_distance(query_norm, v_norm[j : j + len(query_norm)]) / len(query_norm)
            for j in range(len(v_norm) - len(query_norm) + 1)
        )
    return edit_distance(query_norm, v_norm) / max(len(query_norm), len(v_norm))


def _read_tanzil(path: Path) -> dict[str, str] | None:
    """``"sura:aya" -> verse`` of a Tanzil ``sura|aya|text`` file; its ``#`` notice is
    skipped. ``None`` when the file is missing."""
    if not path.exists():
        return None
    rows = {}
    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\r\n")
            parts = line.split("|", 2)
            if len(parts) == 3 and not line.startswith("#"):
                rows[f"{parts[0]}:{parts[1]}"] = parts[2]
    return rows


def _aligned_words(verse: dict, marked_line: str) -> list[tuple[int, int]] | None:
    """For each word of the matching text, the span of the same word in the diacritized line
    (equal after ``canonicalize_for_matching``, D-036); ``None`` unless every word aligns.

    Two spelling differences between the older matching file and Tanzil Simple 1.1 are also
    accepted (D-045): one word written as two («بعدما» / «بعد ما») and a final alef written as
    alef maqsura («الزنا» / «الزنى»). The marks shown are still the file's own.
    """
    tokens = [m.span() for m in re.finditer(r"\S+", marked_line)]
    marked = [canonicalize_for_matching(marked_line[s:e]) for s, e in tokens]
    words = canonicalize_for_matching(verse["text"]).split()
    if len(words) != len(verse["norm"].split()):
        return None
    spans = []
    t = 0
    for word in words:
        if t < len(marked) and _same_word(word, marked[t]):
            spans.append(tokens[t])
            t += 1
        elif t + 1 < len(marked) and word == marked[t] + marked[t + 1]:
            spans.append((tokens[t][0], tokens[t + 1][1]))
            t += 2
        else:
            return None
    return spans if t == len(marked) else None


def _same_word(word: str, marked: str) -> bool:
    """Equal, or equal but for a final alef that the other file writes as alef maqsura."""
    if word == marked:
        return True
    return len(word) > 2 and word[:-1] == marked[:-1] and {word[-1], marked[-1]} == {"ا", "ي"}


def _load_diacritized(verses: list[dict]) -> dict[int, tuple[str, list[tuple[int, int]]]]:
    """Verse index -> (diacritized line, word spans) for every verse that aligns (D-044).

    A missing file, or a verse that does not align word for word, shows no diacritized text,
    exactly as before the feature; one counter-only warning says how many verses align.
    """
    rows = _read_tanzil(TANZIL_DIACRITIZED_PATH) or {}
    aligned = {}
    for i, verse in enumerate(verses):
        line = rows.get(verse["ref"])
        spans = None if line is None else _aligned_words(verse, line)
        if spans is not None:
            aligned[i] = (line, spans)
    if verses and len(aligned) < len(verses):
        _log_unaligned(len(aligned), len(verses))
    return aligned


def _log_unaligned(aligned: int, verses: int) -> None:
    record = {"event": "quran_diacritized_partial", "aligned": aligned, "verses": verses}
    logger.warning(json.dumps(record, sort_keys=True))


@lru_cache(maxsize=1)
def get_index() -> QuranIndex:
    return QuranIndex()


def approved_verse_count() -> int:
    """Verses the resolver can insert: the first non-placeholder translation, en then fr."""
    for lang in ("en", "fr"):
        data = get_index().translations.get(lang)
        if data and data.get("status") != "placeholder":
            return len(data.get("verses", {}))
    return 0


def _insert_translation(
    idx: QuranIndex, lang: str, v_start: int, v_end: int
) -> tuple[str | None, list[SourceRef], list[Flag]]:
    """Approved translation of the verse range in ornate brackets, plus its source.

    Shared by the exact-match and misquote paths (D-007) so both insert the same text.
    Without an approved translation: ``None`` and a pending flag, never generated text.
    """
    trans_text, edition = idx.get_translation(lang, v_start, v_end)
    if trans_text is None:
        return None, [], [Flag(type="info", key="quran_translation_pending")]
    source = SourceRef(kind="quran", ref=_ref(idx, v_start, v_end), edition=edition)
    return f"﴿{trans_text}﴾", [source], []


def _ref(idx: QuranIndex, v_start: int, v_end: int) -> str:
    ref_str = idx.verses[v_start]["ref"]
    if v_start != v_end:
        ref_str += f"-{idx.verses[v_end]['aya']}"
    return ref_str


def _diacritized_flags(idx: QuranIndex, span: tuple[int, int]) -> list[Flag]:
    """The quoted words with Tanzil's tashkeel as an info flag (D-044); none when unsure."""
    text = idx.diacritized_text(span)
    if text is None:
        return []
    ref = _ref(idx, *idx.verse_range(span))
    return [Flag(type="info", key="quran_diacritized", detail=f"{ref}|{text}")]


def _not_found() -> dict:
    flags = [Flag(type="warn", key="quran_not_found")]
    return {"output": None, "sources": [], "flags": flags, "review": True}


def _from_exact(
    idx: QuranIndex, spans: list[tuple[int, int]], matched_chars: int, lang: str
) -> dict:
    """Approved translation of the first exact match; a quote under 10% of its verse is not enough.

    A single match also gets its words with Tanzil's tashkeel (D-044); an ambiguous one does not.
    """
    matches = [idx.verse_range(span) for span in spans]
    v_start, v_end = matches[0]
    flags = []
    if len(matches) > 1:
        refs = [f"{idx.verses[s]['ref']}" for s, _e in matches]
        flags.append(Flag(type="info", key="quran_ambiguous", detail=", ".join(refs)))

    total_verse_chars = sum(len(idx.verses[i]["norm"]) for i in range(v_start, v_end + 1))
    total_verse_chars += v_end - v_start
    ratio = matched_chars / total_verse_chars if total_verse_chars > 0 else 0
    if ratio < 0.1:
        flags.append(Flag(type="warn", key="quran_not_found"))
        return {"output": None, "sources": [], "flags": flags, "review": True}

    output, sources, found_flags = _insert_translation(idx, lang, v_start, v_end)
    flags += found_flags
    if output is not None:
        flags.append(Flag(type="info", key="quran_from_approved"))
    if len(spans) == 1:
        flags += _diacritized_flags(idx, spans[0])
    return {"output": output, "sources": sources, "flags": flags, "review": False}


def _match_words(text: str) -> list[str]:
    """Words in the index's form: marks and format chars dropped, one alef, ya and ha."""
    return _NON_LETTERS.sub(" ", normalize_text(canonicalize_for_matching(text))).split()


# Words allowed between the attribution formula and an undelimited quote.
_LEAD_WORDS = frozenset(
    _match_words("تعالى سبحانه وتعالى عز وجل جل جلاله في كتابه العزيز الكريم محكم التنزيل")
)


def _unbracketed_candidates(text: str) -> list[list[str]]:
    """Word runs that may be the verse. A quote in plain brackets or quotation marks is taken
    as written. Otherwise the text after the attribution formula, minus filler such as
    «تعالى في كتابه العزيز»; a real word of the quote is never dropped, so a misquote cannot
    shrink into a match."""
    quoted = [
        _match_words(next(group for group in m.groups() if group is not None))
        for m in _PLAIN_QUOTES.finditer(text)
    ]
    candidates = quoted
    canon = canonicalize_for_matching(text)
    ends = [canon.find(a) + len(a) for a in QURAN_ATTRIBUTIONS if a in canon]
    if not quoted and ends:
        rest = _match_words(canon[min(ends) :])
        while rest and rest[0] in _LEAD_WORDS:
            rest = rest[1:]
        candidates = [rest]
    elif not quoted:
        # No formula, no brackets (D-043): only the whole segment can be the verse.
        candidates = [_match_words(text)]
    return [words for words in candidates if len(words) >= UNBRACKETED_MIN_WORDS]


def _resolve_unbracketed(idx: QuranIndex, text: str, lang: str) -> dict:
    """Attributed to God without ornate brackets (D-036, D-041): the quote must be a whole-word
    run of a verse, else nothing is inserted and nothing is translated. No near match: a
    paraphrase or commentary is never "corrected" into a verse."""
    for words in _unbracketed_candidates(text):
        spans = idx.word_spans(words)
        if spans:
            return _from_exact(idx, spans, len(" ".join(words)), lang)
    return _not_found()


def resolve_quran(text: str, target_lang: str) -> dict:
    idx = get_index()
    quotes = re.findall(r"\uFD3F(.*?)\uFD3E", text)
    if not quotes:
        return _resolve_unbracketed(idx, text, target_lang)

    query = quotes[0].strip()
    query_clean = QURAN_CLEAN_RE.sub("", query)
    query_norm = " ".join(normalize_text(query_clean).split())

    spans = idx.exact_spans(query_norm)
    if spans:
        return _from_exact(idx, spans, len(query_norm), target_lang)

    v_start, v_end, rate = idx.find_near(query_norm)
    if rate >= NEAR_MAX_RATE:
        return _not_found()
    # D-007: insert the correct verse's approved translation, block and review. The correct
    # verse is shown with Tanzil's tashkeel when it aligns (D-044).
    correct_text = idx.diacritized_verse(v_start) or idx.verses[v_start]["text"]
    ref_str = idx.verses[v_start]["ref"]
    # pass ref and correct_text to detail to fill the placeholders
    flags = [Flag(type="block", key="quran_mismatch", detail=f"{ref_str}|{correct_text}")]
    output, sources, found_flags = _insert_translation(idx, target_lang, v_start, v_end)
    return {"output": output, "sources": sources, "flags": flags + found_flags, "review": True}


def contains_bare_verse(text: str) -> bool:
    """D-043: the whole segment is a verse (``BARE_GRAM``+ words, or 3 words found in one
    place only, D-047), or a run of ``BARE_MIN_RUN``+ words inside it is, with no formula
    and no brackets. Such text must never reach the LLM: the Quran handler inserts the
    approved translation or sends it to review."""
    idx = get_index()
    words = _match_words(text)
    if idx.has_grams(words) and idx.find_words(words):
        return True
    if len(words) == UNBRACKETED_MIN_WORDS and len(idx.find_words(words)) == 1:
        return True
    run = BARE_MIN_RUN
    for start in range(len(words) - run + 1):
        window = words[start : start + run]
        if idx.has_grams(window) and idx.find_words(window):
            return True
    return False
