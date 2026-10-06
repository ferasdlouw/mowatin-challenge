"""A verse pasted or typed in another Unicode form resolves like the same verse typed plainly.

Matching only: the output is always the approved translation looked up by verse id.
"""

from __future__ import annotations

import unicodedata

import pytest

from app.pipeline.glossary import detect
from app.pipeline.quran import (
    TANZIL_PATH,
    _match_words,
    _read_tanzil,
    get_index,
    input_form,
    resolve_quran,
)

TAWHEED_PLACES = ["37:35", "47:19"]


def _places(result: dict) -> list[str]:
    """The verse places a result points to: its source, or every ambiguous candidate."""
    return [s.ref for s in result["sources"]] or [c.ref for c in result.get("candidates", [])]


@pytest.mark.parametrize(
    "text",
    [
        "لا اله الا الله",
        "لا اله الا \ufdf2",  # the Allah ligature, as some keyboards and PDFs produce it
    ],
)
def test_tawheed_returns_every_place(text: str) -> None:
    result = resolve_quran(text, "en")
    assert result["output"] is None
    assert _places(result) == TAWHEED_PLACES


@pytest.mark.parametrize(
    "text",
    [
        "يا ايها الذين امنوا كتب عليكم الصيام",
        # Persian kaf and farsi yeh, as a Persian or Urdu keyboard types them
        "يا ايها الذين امنوا کتب علیکم الصيام",
        # the vocative written as one word, as Uthmani spacing has it
        "ياايها الذين امنوا كتب عليكم الصيام",
    ],
)
def test_fasting_verse_input_forms(text: str) -> None:
    plain = resolve_quran("يا ايها الذين امنوا كتب عليكم الصيام", "en")
    result = resolve_quran(text, "en")
    assert _places(result) == ["2:183"]
    assert result["output"] == plain["output"]
    assert result.get("verification") == plain.get("verification")
    assert [f.key for f in result["flags"]] == [f.key for f in plain["flags"]]


ZWNJ, ZWJ, LRM, RLM = "\u200c", "\u200d", "\u200e", "\u200f"
TAWHEED_FORMS = [
    "لا اله الا الله",
    "لَا إِلَٰهَ إِلَّا اللَّهُ",
    "لَآ إِلَٰهَ إِلَّا ٱللَّهُ",
    "لَآ إِلَٰهَ\u06df إِلَّا ٱللَّهُ\u06e1\u06d6",
    "لا إلــه إلا الله",
    f"لا إل{ZWNJ}ه إلا الل{ZWJ}ه",
    f"{RLM}لا إله{LRM} إلا الله",
    "﴿لا إله إلا الله﴾ ﴿٣٥﴾",
    "لا إله إلا الله\u06dd٣٥",
    "لا إله إلا \ufdf2",
    "لا أله الا الله",
    unicodedata.normalize("NFD", "لَا إِلَٰهَ إِلَّا اللَّهُ"),
]


def test_every_tawheed_form_gives_the_same_result() -> None:
    results = [resolve_quran(text, "en") for text in TAWHEED_FORMS]
    assert all(_places(r) == TAWHEED_PLACES for r in results)
    assert all(r.get("verification") == results[0].get("verification") for r in results)
    assert all(r["output"] is None and r["review"] for r in results)


def test_short_vocative_stays_ambiguous() -> None:
    assert len(_places(resolve_quran("يا ايها الذين امنوا", "en"))) > 50


def test_input_form_is_idempotent_and_no_verse_is_empty() -> None:
    idx = get_index()
    for verse in idx.verses:
        once = input_form(verse["text"])
        assert input_form(once) == once
        assert _match_words(once)


@pytest.mark.parametrize(
    ("text", "first", "count"),
    [
        # 55:16 pasted in Uthmani: «ءالاء» is not the stored «آلاء», so it is a near match
        ("﴿فَبِأَىِّ ءَالَآءِ رَبِّكُمَا تُكَذِّبَانِ﴾", "55:13", 31),
        # 2:122 misquoted by one letter; 2:47 has the same words
        ("﴿يا بني اسرائيل اذكروا نعمتي التي انعمت عليكم واني فضلتكم علي العالمين﴾", "2:47", 2),
    ],
)
def test_near_match_of_identical_verses_picks_no_place(text: str, first: str, count: int) -> None:
    result = resolve_quran(text, "en")
    assert result["output"] is None
    assert result["review"]
    places = _places(result)
    assert places[0] == first
    assert len(places) == count


@pytest.mark.parametrize(
    ("text", "places"),
    [
        ("لا إله إلا الله (٣٧:٣٥)", ["37:35"]),
        ("لا إله إلا الله (47:19)", ["47:19"]),
        # a reference that matches no place found leaves every place, for review
        ("لا إله إلا الله (2:255)", []),
    ],
)
def test_reference_in_plain_brackets_narrows(text: str, places: list[str]) -> None:
    result = resolve_quran(text, "en")
    assert [s.ref for s in result["sources"]] == places
    if not places:
        assert result["output"] is None and result["review"]


@pytest.mark.parametrize("ref", ["2:14", "2:255", "53:19"])
def test_uthmani_hamza_seats_find_their_verse(ref: str) -> None:
    """«مستهزءون», «يوده», «أفرءيتم»: Simple writes the hamza on another seat, or not at all."""
    uthmani = _read_tanzil(TANZIL_PATH.with_name("quran-uthmani.txt"))
    assert uthmani is not None
    result = resolve_quran(f"﴾{uthmani[ref]}﴿", "en")
    assert [s.ref for s in result["sources"]] == [ref]
    assert not any(f.key == "quran_mismatch" for f in result["flags"])


def test_glossary_reads_persian_letters() -> None:
    assert [m["id"] for m in detect("الزکاة")] == [m["id"] for m in detect("الزكاة")]
