import re
import unicodedata

TASHKEEL_TATWEEL = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0640]")
# Every Arabic mark a writer may add or omit: tashkeel incl. maddah/hamza marks (U+0653-065F),
# superscript alef (U+0670), Quranic annotation signs (U+06D6-06ED), tatweel.
_ALL_MARKS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")


def _is_format_char(char: str) -> bool:
    """Unicode Cf: zero-width (U+200B-200F), bidi controls (U+202A-202E, U+2066-2069), tags."""
    return unicodedata.category(char) == "Cf"


def strip_format_chars(text: str) -> str:
    """Drop invisible format characters, which can split a word without changing how it looks."""
    return "".join(char for char in text if not _is_format_char(char))


def strip_marks(text: str) -> str:
    """Drop format characters, every Arabic mark and tatweel; letters stay as written."""
    return _ALL_MARKS.sub("", strip_format_chars(text))


def canonicalize_for_matching(text: str) -> str:
    """One form for every safety match (fatwa phrases, scripture attribution), D-036.

    ``strip_marks`` plus one alef (incl. wasla) and ya for alef maqsura, so a vocalised,
    stretched or zero-width-split \u00ab\u0645\u0627 \u062d\u0643\u0645\u00bb still reads \u00ab\u0645\u0627 \u062d\u0643\u0645\u00bb. Ta marbuta is kept: unified
    with ha, \u00ab\u0645\u0627 \u062d\u0643\u0645\u0647\u061f\u00bb (a ruling question) would equal the exclusion \u00ab\u0645\u0627 \u062d\u0643\u0645\u0629\u00bb.
    Matching only: segments keep their original text for output.
    """
    text = re.sub(r"[\u0623\u0625\u0622\u0671]", "\u0627", strip_marks(text))
    return text.replace("\u0649", "\u064a")


def normalize_text(text: str) -> str:
    """Basic normalization for simple matching without span tracking."""
    text = TASHKEEL_TATWEEL.sub("", strip_format_chars(text))
    text = re.sub(r"[أإآ]", "ا", text)
    text = text.replace("ة", "ه")
    text = text.replace("ى", "ي")
    return text


def normalize_with_mapping(text: str) -> tuple[str, list[int]]:
    """
    Returns (normalized_text, orig_indices)
    where orig_indices[i] is the index in `text` corresponding to normalized_text[i].
    """
    norm_chars = []
    orig_indices = []

    for i, char in enumerate(text):
        if TASHKEEL_TATWEEL.match(char) or _is_format_char(char):
            continue

        if char in "أإآ":
            norm_char = "ا"
        elif char == "ة":
            norm_char = "ه"
        elif char == "ى":
            norm_char = "ي"
        else:
            norm_char = char

        norm_chars.append(norm_char)
        orig_indices.append(i)

    orig_indices.append(len(text))
    return "".join(norm_chars), orig_indices


PREFIXES = [
    "وبال",
    "وفال",
    "وكال",
    "ولل",
    "وال",
    "فال",
    "بال",
    "كال",
    "لل",
    "ال",
    "و",
    "ف",
    "ب",
    "ك",
    "ل",
]


def get_word_variants(word: str) -> list[tuple[str, int]]:
    """
    Returns a list of (variant, prefix_length) for a given word.
    For example, 'والصبر' -> [('والصبر', 0), ('صبر', 3)]
    """
    variants = [(word, 0)]
    for p in PREFIXES:
        if word.startswith(p) and len(word) > len(p):
            variants.append((word[len(p) :], len(p)))
    return variants


def tokenize(text: str) -> list[dict]:
    """
    Tokenize normalized text, keeping track of spans.
    But since we need attached-prefix handling,
    this should probably return the words and their possible stripped variants.
    """
    norm_text, mapping = normalize_with_mapping(text)

    tokens = []
    for match in re.finditer(r"\w+", norm_text):
        word = match.group()
        start_norm = match.start()
        end_norm = match.end()

        variants = []
        for v, p_len in get_word_variants(word):
            v_start_norm = start_norm + p_len
            variants.append(
                {"text": v, "start_orig": mapping[v_start_norm], "end_orig": mapping[end_norm]}
            )

        tokens.append(
            {
                "word": word,
                "start_orig": mapping[start_norm],
                "end_orig": mapping[end_norm],
                "variants": variants,
                "start_norm": start_norm,
                "end_norm": end_norm,
            }
        )

    return tokens
