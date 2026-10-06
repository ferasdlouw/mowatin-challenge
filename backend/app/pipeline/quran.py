import itertools
import json
import logging
import math
import re
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from app.pipeline.normalize import canonicalize_for_matching, normalize_text
from app.schemas import Flag, SourceRef

logger = logging.getLogger(__name__)

# Formulas that attribute the words that follow to God (D-036; the Prophet's are in hadith.py).
# Without ornate brackets the quote is looked up word for word (D-041); a segment with one goes
# to the Quran handler, never to the LLM.
QURAN_ATTRIBUTIONS = tuple(
    canonicalize_for_matching(p)
    for p in ("قال الله", "قال تعالى", "قوله تعالى", "يقول الله", "يقول تعالى")
)


def edit_distance(s1: Sequence[str], s2: Sequence[str]) -> int:
    """Levenshtein distance between two strings, or two word lists."""
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
# A misquote across verses (D-054): Quran places tried per matched word window, and windows.
NEAR_RUN_ANCHORS = 20
NEAR_RUN_WINDOWS = 12

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
# Letters a quote may leave off the first word of a verse (D-052).
_DROPPABLE_PREFIXES = "وف"

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

    def word_aligned(self, span: tuple[int, int]) -> bool:
        """``span`` starts and ends on whole words of ``giant_string`` (D-052).

        The start may also follow a leading و or ف of the first word, which a quote often
        drops («اعتصموا» for «واعتصموا»). A cut anywhere else («ن الله», «الصابر» for
        «الصابرين») is not the verse as written.
        """
        start, end = span
        text = self.giant_string
        if end < len(text) and text[end] != " ":
            return False
        if start == 0 or text[start - 1] == " ":
            return True
        return text[start - 1] in _DROPPABLE_PREFIXES and (start == 1 or text[start - 2] == " ")

    def find_near_run(self, words: list[str]) -> tuple[int, int, float, tuple[int, int]]:
        """Closest run of Quran text to a quote spanning verses, by character edit rate (D-054).

        ``find_near`` scores one verse at a time, so «والعصر ان الانسان لفي صر» (103:1-2)
        found nothing. Among runs under ``NEAR_MAX_RATE`` the one keeping most of the quote's
        words wins, then the lowest rate. Returns (v_start, v_end, rate, span); rate 1.0 when
        nothing is close.
        """
        query = " ".join(words)
        best: tuple[int, int, float, tuple[int, int]] = (0, 0, 1.0, (0, 0))
        best_key: tuple[bool, int, float] = (True, 0, 1.0)
        for span, run_words in self._anchored_runs(words):
            run = " ".join(run_words)
            rate = edit_distance(query, run) / max(len(query), len(run))
            key = (rate >= NEAR_MAX_RATE, -_common_words(words, run_words), rate)
            if key < best_key:
                best_key, best = key, (*self.verse_range(span), rate, span)
        return best

    def find_near_words(self, words: list[str]) -> tuple[int, int, int, tuple[int, int]]:
        """Closest run of Quran words to an unbracketed quote, by word edit distance (D-054).

        Whole words only, so a sentence that shares a phrase with a verse and goes on in its
        own words stays far. Ties go to the run keeping most of the quote's words, then the
        lowest character rate. Returns (v_start, v_end, wrong_words, span).
        """
        query = " ".join(words)
        best: tuple[int, int, int, tuple[int, int]] = (0, 0, len(words), (0, 0))
        best_key: tuple[int, int, float] = (len(words), 0, 1.0)
        for span, run_words in self._anchored_runs(words):
            run = " ".join(run_words)
            key = (
                edit_distance(words, run_words),
                -_common_words(words, run_words),
                edit_distance(query, run) / max(len(query), len(run)),
            )
            if key < best_key:
                best_key, best = key, (*self.verse_range(span), key[0], span)
        return best

    def _anchored_runs(self, words: list[str]):
        """Quran runs aligned to ``words``, one per place: each ``BARE_GRAM``-word window of the
        quote found in the Quran (the basmala alone excepted) anchors a place, inside one sura.
        Bounded by ``NEAR_RUN_*``. At a place the run is one word fewer, as many or one more
        than the quote, whichever keeps most of its words, then the same length: «لفي صر» is
        one word from «لفي» and from «لفي خسر», and only the second covers the whole quote.
        """
        starts, tried = self._word_starts(), 0
        for i in range(len(words) - BARE_GRAM + 1):
            window = words[i : i + BARE_GRAM]
            if tuple(window) not in self.grams() or tuple(window) == _BASMALA:
                continue
            tried += 1
            if tried > NEAR_RUN_WINDOWS:
                return
            for found in self.word_spans(window)[:NEAR_RUN_ANCHORS]:
                runs = [
                    self._run(starts[found[0]] - i, count)
                    for count in range(len(words) - 1, len(words) + 2)
                ]
                runs = [run for run in runs if run is not None]
                if runs:
                    yield min(runs, key=lambda run: _run_key(words, run[1]))

    def _run(self, first: int, count: int) -> tuple[tuple[int, int], list[str]] | None:
        """``count`` Quran words from word ``first`` as (span, words), or ``None`` when they
        fall outside the text or cross into another sura."""
        all_words = self._words()
        if first < 0 or count < 1 or first + count > len(all_words):
            return None
        span = (all_words[first][0], all_words[first + count - 1][1])
        v_start, v_end = self.verse_range(span)
        if self.verses[v_start]["sura"] != self.verses[v_end]["sura"]:
            return None
        return span, self.giant_string[span[0] : span[1]].split()

    def _words(self) -> list[tuple[int, int]]:
        """Character span of every word of ``giant_string``, built on first use and kept."""
        if not hasattr(self, "_word_list"):
            self._word_list = [m.span() for m in re.finditer(r"\S+", self.giant_string)]
        return self._word_list

    def _word_starts(self) -> dict[int, int]:
        """Word number by its first character in ``giant_string``."""
        if not hasattr(self, "_start_map"):
            self._start_map = {start: n for n, (start, _end) in enumerate(self._words())}
        return self._start_map

    def is_whole_verse(self, span: tuple[int, int]) -> bool:
        """``span`` is one whole verse, or a sura's first verse without the basmala that opens
        it in the Tanzil text («والعصر» for 103:1)."""
        v_start, v_end = self.verse_range(span)
        if v_start != v_end:
            return False
        start, end = (
            self.verse_offsets[v_start],
            self.verse_offsets[v_start] + len(self.verses[v_start]["norm"]),
        )
        opening = self.verses[v_start]["aya"] == "1"
        if opening and self.verses[v_start]["norm"].startswith(_BASMALA_TEXT):
            start += len(_BASMALA_TEXT)
        return span == (start, end)

    def skeleton_spans(self, words: list[str]) -> list[tuple[int, int]]:
        """Spans of ``giant_string`` whose words have the skeletons of ``words`` (D-056).

        For Uthmani-script quotes only: alefs are optional, so a Simple-script misquote that
        differs by an alef («قال» for «قل») is never matched here.
        """
        if not words:
            return []
        text, firsts = self._skeleton_text()
        pattern = re.compile(
            r"(?<!\S)" + r" ".join(re.escape(skeleton(w)) for w in words) + r"(?!\S)"
        )
        all_words = self._words()
        spans = []
        for match in pattern.finditer(text):
            first = firsts[match.start()]
            spans.append((all_words[first][0], all_words[first + len(words) - 1][1]))
        return spans

    def _skeleton_text(self) -> tuple[str, dict[int, int]]:
        """``giant_string`` word by word as skeletons, with word number by start character."""
        if not hasattr(self, "_skeleton"):
            text, firsts, pos = [], {}, 0
            for n, (start, end) in enumerate(self._words()):
                firsts[pos] = n
                word = skeleton(self.giant_string[start:end])
                text.append(word)
                pos += len(word) + 1
            self._skeleton = (" ".join(text), firsts)
        return self._skeleton

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
        """True when every ``BARE_GRAM``-word window of ``words`` occurs in some sura."""
        grams = self.grams()
        return len(words) >= BARE_GRAM and all(
            tuple(words[i : i + BARE_GRAM]) in grams for i in range(len(words) - BARE_GRAM + 1)
        )

    def grams(self) -> frozenset[tuple[str, ...]]:
        """Every ``BARE_GRAM``-word window of every sura, built on first use and kept.

        Windows run across consecutive verses of one sura (D-053): short suras are quoted
        whole («والعصر ان الانسان لفي خسر» is 103:1-2), never across two suras.
        """
        if not hasattr(self, "_gram_set"):
            grams = set()
            for _sura, verses in itertools.groupby(self.verses, key=lambda v: v["sura"]):
                w = [word for verse in verses for word in verse["norm"].split()]
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


# A quote under this share of its verse is not enough to insert it (D-006 as built).
MIN_VERSE_SHARE = 0.1
# Under this share the whole verse's translation is inserted but reviewed (D-055, D-006's 40%).
PARTIAL_REVIEW_SHARE = 0.4


def _from_exact(
    idx: QuranIndex, spans: list[tuple[int, int]], matched_chars: int, lang: str
) -> dict:
    """Approved translation of the first exact match (D-055 adds the review cases).

    Not inserted: a quote under ``MIN_VERSE_SHARE`` of its verse, or under
    ``UNBRACKETED_MIN_WORDS`` words unless it is a whole verse («مدهامتان»). Reviewed: a quote
    under ``PARTIAL_REVIEW_SHARE`` of its verse (the whole verse is inserted), or one found in
    places whose translations differ. A single match also gets its words with Tanzil's
    tashkeel (D-044); an ambiguous one does not.
    """
    spans = _without_sura_openings(idx, spans)
    matches = [idx.verse_range(span) for span in spans]
    v_start, v_end = matches[0]
    flags = _ambiguity_flags(idx, matches, lang)
    share = _verse_share(idx, v_start, v_end, matched_chars)
    short = len(idx.giant_string[spans[0][0] : spans[0][1]].split()) < UNBRACKETED_MIN_WORDS
    if share < MIN_VERSE_SHARE or (short and not idx.is_whole_verse(spans[0])):
        flags.append(Flag(type="warn", key="quran_not_found"))
        return {"output": None, "sources": [], "flags": flags, "review": True}

    output, sources, found_flags = _insert_translation(idx, lang, v_start, v_end)
    flags += found_flags
    if output is not None:
        flags.append(Flag(type="info", key="quran_from_approved"))
    if output is not None and share < PARTIAL_REVIEW_SHARE:
        flags.append(Flag(type="warn", key="quran_partial"))
    if len(spans) == 1:
        flags += _diacritized_flags(idx, spans[0])
    return {"output": output, "sources": sources, "flags": flags, "review": _reviewed(flags)}


def _without_sura_openings(idx: QuranIndex, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Drop matches that lie inside the basmala opening a sura's first verse in the Tanzil
    text (112 of them), unless nothing else matched: the basmala quoted alone is 1:1 (or
    27:30), not the start of every sura."""
    kept = [span for span in spans if not _in_sura_opening(idx, span)]
    return kept or spans


def _in_sura_opening(idx: QuranIndex, span: tuple[int, int]) -> bool:
    v_start, v_end = idx.verse_range(span)
    verse = idx.verses[v_start]
    opening = verse["aya"] == "1" and verse["ref"] != "1:1"
    end = idx.verse_offsets[v_start] + len(_BASMALA_TEXT)
    return (
        opening and v_start == v_end and verse["norm"].startswith(_BASMALA_TEXT) and span[1] < end
    )


def _verse_share(idx: QuranIndex, v_start: int, v_end: int, matched_chars: int) -> float:
    """The quote's share of the verses it falls in, by normalized characters; the basmala
    that opens a sura's first verse in the Tanzil text is not counted («والعصر» is 103:1)."""
    total = sum(len(idx.verses[i]["norm"]) for i in range(v_start, v_end + 1)) + v_end - v_start
    if idx.verses[v_start]["norm"].startswith(_BASMALA_TEXT) and idx.verses[v_start]["aya"] == "1":
        total -= len(_BASMALA_TEXT)
    return matched_chars / total if total > 0 else 0.0


def _ambiguity_flags(idx: QuranIndex, matches: list[tuple[int, int]], lang: str) -> list[Flag]:
    """A quote found in several places: reviewed when the places' approved translations
    differ (the first place may be the wrong one), info when they are all the same text
    («فبأي آلاء ربكما تكذبان», 31 places)."""
    if len(matches) < 2:
        return []
    refs = ", ".join(idx.verses[s]["ref"] for s, _e in matches)
    texts = {_TRAILING_PUNCT.sub("", idx.get_translation(lang, s, e)[0] or "") for s, e in matches}
    same = len(texts) == 1 and "" not in texts
    return [Flag(type="info" if same else "warn", key="quran_ambiguous", detail=refs)]


# Saheeh International ends a verse that runs on with « -» or «,»: the same translation.
_TRAILING_PUNCT = re.compile(r"[\s\-\u2013\u2014,;:.]+$")


def _reviewed(flags: list[Flag]) -> bool:
    return any(flag.type != "info" for flag in flags)


def _match_words(text: str) -> list[str]:
    """Words in the index's form: marks and format chars dropped, one alef, ya and ha."""
    return _NON_LETTERS.sub(" ", normalize_text(canonicalize_for_matching(text))).split()


_BASMALA = tuple(_match_words("بسم الله الرحمن الرحيم"))
# The basmala and its space, as it opens the first verse of a sura in the Tanzil text.
_BASMALA_TEXT = " ".join(_BASMALA) + " "

# Uthmani script (D-056): marks that the Simple text never has. Text with any of them was
# copied from an Uthmani mushaf, and only such text is matched on the alef-free skeleton.
_UTHMANI_RE = re.compile("[\u0671\u0670\u06d6-\u06ed]")
_HARAKA = "[\u064b-\u0652]*"
# The vocative «يٰٓأيها» is two words in Simple («يا أيها»), and so is «هٰٓأنتم».
_VOCATIVE_RE = re.compile(f"(?<!\\S)([يه]){_HARAKA}\u0670\u0653?(?={_HARAKA}[\u0623\u0627])")
# «ٱلصَّلَوٰةَ» is «الصلاة»: a waw carrying the alef before ta marbuta or alef.
_WAW_ALEF_RE = re.compile(f"و{_HARAKA}\u0670(?={_HARAKA}[\u0629\u0627])")
# Small waw / small ya lengthening a pronoun («بِهِۦ», «لَهُۥ»): not written in Simple.
_SILAH_RE = re.compile("[\u06e5\u06e6](?!\\w)")


def has_uthmani_marks(text: str) -> bool:
    return _UTHMANI_RE.search(text) is not None


def uthmani_to_simple(text: str) -> str:
    """Uthmani spelling brought close to the Simple text (D-056): alef wasla, the small alef
    (written as alef; the skeleton makes it optional), waw-alef, small ya/waw, and the marks
    the Simple text does not have. Text without Uthmani marks is returned unchanged."""
    if not has_uthmani_marks(text):
        return text
    text = _VOCATIVE_RE.sub(r"\1ا ", text)
    text = _WAW_ALEF_RE.sub("ا", text)
    text = _SILAH_RE.sub("", text)
    text = text.replace("\u0671", "ا").replace("\u0670", "ا")
    text = text.replace("\u06e6", "ي").replace("\u06e7", "ي").replace("\u06e5", "")
    return re.sub("[\u06d6-\u06ed]", "", text)


def skeleton(word: str) -> str:
    """A word without the alefs after its first letter (hamza + alef counts as alef): Uthmani
    writes the small alef where Simple writes an alef («العٰلمين») and where it writes none
    («ذٰلك»)."""
    word = word.replace("ءا", "ا")
    return word[:1] + word[1:].replace("ا", "")


# Words allowed between the attribution formula and an undelimited quote.
_LEAD_WORDS = frozenset(
    _match_words("تعالى سبحانه وتعالى عز وجل جل جلاله في كتابه العزيز الكريم محكم التنزيل")
)


# Words that introduce a quoted verse (D-051): the segmenter keeps them in the verse's
# segment, and they are not text the verse's approved translation leaves out.
_SPEECH_WORDS = frozenset(_match_words("قال يقول قوله لقوله الآية آية"))
_INTRO_WORDS = _LEAD_WORDS | frozenset(_match_words("الله ربنا كما الكريمة ورد جاء"))
_CONNECTORS = frozenset(_match_words("و ف ثم أو"))
_PREFIXES = "وفكل"

VERSE_SPAN_RE = re.compile("﴿[^﴾]*﴾")
# A sura reference right after a verse: «[البقرة: 153]», «(سورة آل عمران: ٢٠٠)».
VERSE_REF_RE = re.compile(
    r"\s*[\[(](?:سورة\s+)?[ء-ي\s]{2,30}[:،]\s*[\d٠-٩]+"
    r"(?:\s*[-–]\s*[\d٠-٩]+)?\s*[\])]"
)


def _intro_kind(word: str) -> str | None:
    """``speech``, ``intro`` or ``connector`` for a word that introduces a verse, else ``None``.
    ``word`` is in ``_match_words`` form; one attached و/ف/ك/ل is allowed («وقال», «لقوله»)."""
    for form in (word, word[1:] if len(word) > 1 and word[0] in _PREFIXES else ""):
        if form in _SPEECH_WORDS:
            return "speech"
        if form in _INTRO_WORDS:
            return "intro"
    return "connector" if word in _CONNECTORS else None


def lead_in_start(text: str) -> int:
    """Where the words introducing a verse that follows ``text`` begin, or ``len(text)``.

    The lead-in is the longest run of introducing words at the end of ``text``. It counts only
    with a word of speech («كما قال تعالى:», «الآية») or when it is only connectors («و»), so
    a sentence that merely ends in «الله» keeps all its words.
    """
    start, kinds = len(text), []
    for match in reversed(list(re.finditer(r"\S+", text))):
        found = [_intro_kind(word) for word in _match_words(match.group())]
        if None in found:
            break
        kinds += found
        start = match.start()
    if "speech" in kinds or (kinds and set(kinds) == {"connector"}):
        return start
    return len(text)


def has_extra_text(rest: str) -> bool:
    """``rest`` (the segment without its matched quote) holds words the approved translation
    does not cover: another verse, or anything but introducing words and a sura reference."""
    if VERSE_SPAN_RE.search(rest):
        return True
    words = _match_words(VERSE_REF_RE.sub(" ", rest))
    return any(_intro_kind(word) is None for word in words)


def _flag_extra_text(result: dict, rest: str) -> dict:
    """A found verse with other words around it: the output is the verse alone, so the
    segment is reviewed instead of passing as certain (D-051)."""
    if result["output"] is not None and has_extra_text(rest):
        result["flags"].append(Flag(type="warn", key="quran_extra_text"))
        result["review"] = True
    return result


def _unbracketed_candidates(text: str) -> list[tuple[list[str], str]]:
    """Word runs that may be the verse, each with the text around it. A quote in plain
    brackets or quotation marks is taken as written. Otherwise the text after the attribution
    formula, minus filler such as «تعالى في كتابه العزيز»; a real word of the quote is never
    dropped, so a misquote cannot shrink into a match."""
    quoted = [
        (
            _match_words(next(group for group in m.groups() if group is not None)),
            f"{text[: m.start()]} {text[m.end() :]}",
        )
        for m in _PLAIN_QUOTES.finditer(text)
    ]
    candidates = quoted
    canon = canonicalize_for_matching(text)
    present = [a for a in QURAN_ATTRIBUTIONS if a in canon]
    if not quoted and present:
        rest = _match_words(canon[min(canon.find(a) + len(a) for a in present) :])
        while rest and rest[0] in _LEAD_WORDS:
            rest = rest[1:]
        candidates = [(rest, canon[: min(canon.find(a) for a in present)])]
    elif not quoted:
        # No formula, no brackets (D-043): only the whole segment can be the verse.
        candidates = [(_match_words(text), "")]
    return [(words, rest) for words, rest in candidates if len(words) >= UNBRACKETED_MIN_WORDS]


def _resolve_unbracketed(idx: QuranIndex, text: str, lang: str) -> dict:
    """Attributed to God or quoted without ornate brackets (D-036, D-041): a whole-word run of
    a verse gets its approved translation. Otherwise only a near-verse (D-053) may be taken
    for a misquote and corrected (D-054); a paraphrase or commentary is never "corrected"
    into a verse, it stays ``output: null`` + review."""
    uthmani = has_uthmani_marks(text)
    for words, rest in _unbracketed_candidates(uthmani_to_simple(text)):
        spans = idx.word_spans(words) or (idx.skeleton_spans(words) if uthmani else [])
        if spans:
            return _flag_extra_text(_from_exact(idx, spans, len(" ".join(words)), lang), rest)
        if _near_words(idx, words):
            v_start, v_end, _wrong, span = idx.find_near_words(words)
            return _flag_extra_text(_misquote_run(idx, lang, v_start, v_end, span), rest)
    return _not_found()


def _common_words(left: list[str], right: list[str]) -> int:
    """Words the two lists share in order (longest common subsequence)."""
    row = [0] * (len(right) + 1)
    for word in left:
        diagonal = 0
        for j, other in enumerate(right, start=1):
            diagonal, row[j] = row[j], diagonal + 1 if word == other else max(row[j], row[j - 1])
    return row[-1]


def _run_key(words: list[str], run_words: list[str]) -> tuple[int, int]:
    """Rank the runs at one place: most of the quote's words kept, then the same length."""
    return -_common_words(words, run_words), abs(len(run_words) - len(words))


def _misquote_run(idx: QuranIndex, lang: str, v_start: int, v_end: int, span) -> dict:
    """D-007 for a run of words: the correct words with Tanzil's tashkeel when they align."""
    correct = idx.diacritized_text(span) or idx.giant_string[span[0] : span[1]]
    return _misquote(idx, lang, (v_start, v_end), _ref(idx, v_start, v_end), correct)


def _misquote(
    idx: QuranIndex, lang: str, verses: tuple[int, int], ref: str, correct_text: str
) -> dict:
    """D-007: insert the correct verse's approved translation, block and review."""
    flags = [Flag(type="block", key="quran_mismatch", detail=f"{ref}|{correct_text}")]
    output, sources, found_flags = _insert_translation(idx, lang, *verses)
    return {"output": output, "sources": sources, "flags": flags + found_flags, "review": True}


def resolve_quran(text: str, target_lang: str) -> dict:
    idx = get_index()
    match = VERSE_SPAN_RE.search(text)
    if match is None:
        return _resolve_unbracketed(idx, text, target_lang)
    rest = f"{text[: match.start()]} {text[match.end() :]}"
    return _flag_extra_text(_resolve_bracketed(idx, match.group()[1:-1], target_lang), rest)


def _resolve_bracketed(idx: QuranIndex, quote: str, target_lang: str) -> dict:
    """The quote inside ornate brackets: exact match, else a near match is a misquote (D-007)."""
    query = uthmani_to_simple(quote).strip()
    query_clean = QURAN_CLEAN_RE.sub("", query)
    query_norm = " ".join(normalize_text(query_clean).split())

    # Whole words only (D-052): a quote cut inside a word goes on to the misquote check.
    spans = [span for span in idx.exact_spans(query_norm) if idx.word_aligned(span)]
    if not spans and has_uthmani_marks(quote):
        spans = idx.skeleton_spans(_match_words(query))
    if spans:
        return _from_exact(
            idx, spans, len(idx.giant_string[spans[0][0] : spans[0][1]]), target_lang
        )

    v_start, v_end, rate = idx.find_near(query_norm)
    if rate < NEAR_MAX_RATE:
        # The correct verse is shown with Tanzil's tashkeel when it aligns (D-044).
        correct_text = idx.diacritized_verse(v_start) or idx.verses[v_start]["text"]
        ref = idx.verses[v_start]["ref"]
        return _misquote(idx, target_lang, (v_start, v_end), ref, correct_text)
    # A quote spanning verses (D-054).
    v_start, v_end, rate, span = idx.find_near_run(query_norm.split())
    if rate < NEAR_MAX_RATE:
        return _misquote_run(idx, target_lang, v_start, v_end, span)
    return _not_found()


# A near-verse (D-053): this many words or more, mostly covered by Quran word windows.
NEAR_VERSE_MIN_WORDS = 5
NEAR_VERSE_COVERAGE = 0.75


def _near_verse(idx: QuranIndex, words: list[str]) -> bool:
    """Most words of ``words`` lie in ``BARE_GRAM``-word runs of the Quran (D-053).

    A misquote such as «والعصر ان الانسان لفي صر» has no exact match, yet an LLM given it
    translates the verse from memory and silently corrects it. The basmala alone does not
    count: it opens ordinary speech too.
    """
    if len(words) < NEAR_VERSE_MIN_WORDS:
        return False
    grams = idx.grams()
    covered = [False] * len(words)
    for i in range(len(words) - BARE_GRAM + 1):
        window = tuple(words[i : i + BARE_GRAM])
        if window in grams and window != _BASMALA:
            covered[i : i + BARE_GRAM] = [True] * BARE_GRAM
    return sum(covered) >= NEAR_VERSE_COVERAGE * len(words) or _near_words(idx, words)


def _near_words(idx: QuranIndex, words: list[str]) -> bool:
    """One wrong word in four at most (and at least one) against an aligned Quran run (D-054):
    a misquote with a wrong word in the middle is still a verse, not speech."""
    if len(words) < NEAR_VERSE_MIN_WORDS:
        return False
    return idx.find_near_words(words)[2] <= max(1, len(words) // 4)


def contains_bare_verse(text: str) -> bool:
    """D-043: the whole segment is a verse (``BARE_GRAM``+ words, or 3 words found in one
    place only, D-047), or a run of ``BARE_MIN_RUN``+ words inside it is, or it is a
    near-verse (D-053), with no formula and no brackets. Such text must never reach the LLM:
    the Quran handler inserts the approved translation or sends it to review."""
    idx = get_index()
    words = _match_words(uthmani_to_simple(text))
    if idx.has_grams(words) and idx.find_words(words):
        return True
    # Uthmani script (D-056): the whole segment, alefs optional.
    long_enough = len(words) >= UNBRACKETED_MIN_WORDS
    if long_enough and has_uthmani_marks(text) and idx.skeleton_spans(words):
        return True
    if len(words) == UNBRACKETED_MIN_WORDS and len(idx.find_words(words)) == 1:
        return True
    run = BARE_MIN_RUN
    for start in range(len(words) - run + 1):
        window = words[start : start + run]
        if idx.has_grams(window) and idx.find_words(window):
            return True
    return _near_verse(idx, words)
