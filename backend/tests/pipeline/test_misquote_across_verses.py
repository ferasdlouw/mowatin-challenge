"""D-054: a misquote is corrected from the Quran text, never by the LLM.

A quote spanning verses («والعصر ان الانسان لفي صر», 103:1-2) found nothing near before,
because the misquote check scored one verse at a time; without brackets, a wrong word in
the middle of a quote left it as plain text for the LLM.
"""

from __future__ import annotations

import random

import pytest

from app.pipeline.classifier import classify
from app.pipeline.quran import get_index, resolve_quran

AL_ASR = "﴿By time, Indeed, mankind is in loss,﴾"


def _tanzil(ref: str) -> str:
    """The verse with Tanzil's tashkeel, as the file writes it (mark order included)."""
    idx = get_index()
    line = idx.diacritized_verse(next(i for i, v in enumerate(idx.verses) if v["ref"] == ref))
    assert line is not None
    return line


def _mismatch(result: dict) -> tuple[str, str]:
    flag = next(flag for flag in result["flags"] if flag.key == "quran_mismatch")
    ref, _, correct = flag.detail.partition("|")
    return ref, correct


@pytest.mark.parametrize(
    "text",
    [
        "﴿والعصر ان الانسان لفي صر﴾",
        "والعصر ان الانسان لفي صر",
        "قال الله تعالى: والعصر ان الانسان لفي صر",
    ],
)
def test_misquote_across_verses_gets_the_correct_verse(text):
    assert classify(text)["category"] == "quran"
    result = resolve_quran(text, "en")
    assert result["output"] == AL_ASR
    assert result["review"] is True
    ref, correct = _mismatch(result)
    assert ref == "103:1-2"
    # All the correct words with Tanzil's tashkeel, without the basmala of 103:1.
    assert correct == f"{_tanzil('103:1').split()[-1]} {_tanzil('103:2')}"


def test_wrong_word_in_the_middle_of_an_unbracketed_quote():
    text = "يا ايها الذين امنوا استعينوا بالصبر والزكاة"
    assert classify(text)["category"] == "quran"
    ref, correct = _mismatch(resolve_quran(text, "en"))
    assert ref == "2:153"
    assert correct.split()[-2:] == _tanzil("2:153").split()[5:7]


@pytest.mark.parametrize("text", ["قل هو الله احد الله الصمت", "﴿قل هو الله احد الله الصمت﴾"])
def test_correction_shows_every_word_of_the_quote(text):
    # A wrong last word ties a run without it with the full run; the full run must win.
    # 112:1 opens with the basmala in Tanzil; the quote, and so the correction, does not.
    correct = " ".join([*_tanzil("112:1").split()[-4:], _tanzil("112:2")])
    assert _mismatch(resolve_quran(text, "en"))[1] == correct


@pytest.mark.parametrize(
    "text",
    [
        "إن الله مع الصابرين في كل حال",
        "بسم الله الرحمن الرحيم نبدأ الدرس",
    ],
)
def test_speech_sharing_a_phrase_is_not_corrected(text):
    assert classify(text)["category"] != "quran"


def test_commentary_after_a_formula_is_not_corrected_into_a_verse():
    result = resolve_quran("قال الله تعالى الحمد لله رب العالمين وفيه فوائد كثيرة", "en")
    assert result["output"] is None
    assert [flag.key for flag in result["flags"]] == ["quran_not_found"]


def test_one_wrong_word_across_a_verse_boundary_is_always_caught():
    idx = get_index()
    words = idx._words()
    pairs = [
        v
        for v in range(len(idx.verses) - 1)
        if idx.verses[v]["sura"] == idx.verses[v + 1]["sura"]
        and len(idx.verses[v]["norm"].split()) >= 3
        and len(idx.verses[v + 1]["norm"].split()) >= 3
    ]
    for v in random.Random(11).sample(pairs, 60):
        first = idx._word_starts()[idx.verse_offsets[v + 1]] - 3
        run = [idx.giant_string[s:e] for s, e in words[first : first + 6]]
        run[4] = "كلمه"
        quote = " ".join(run)
        for text in (quote, f"﴿{quote}﴾"):
            assert classify(text)["category"] == "quran", text
            assert "quran_mismatch" in [f.key for f in resolve_quran(text, "en")["flags"]], text
