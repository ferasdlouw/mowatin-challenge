"""D-052: a bracketed quote matches a verse only on whole words.

Before the fix the exact match was a plain substring search, so a quote cut inside a word
(«إن الله مع الصابر», «ن الله مع الصابرين», in ornate brackets) passed as the verse, certain and not
reviewed, instead of being shown as a misquote with the correct text.
"""

from __future__ import annotations

import pytest

from app.pipeline.quran import get_index, resolve_quran


@pytest.mark.parametrize(
    ("quote", "ref"),
    [
        ("﴿إن الله مع الصابر﴾", "2:153"),
        ("﴿ن الله مع الصابرين﴾", "2:153"),
        ("﴿وما أرسلناك إلا رحمة للعالمي﴾", "21:107"),
    ],
)
def test_quote_cut_inside_a_word_is_a_misquote(quote, ref):
    result = resolve_quran(quote, "en")
    assert result["review"] is True
    blocks = [flag for flag in result["flags"] if flag.type == "block"]
    assert [flag.key for flag in blocks] == ["quran_mismatch"]
    assert blocks[0].detail.startswith(f"{ref}|")


@pytest.mark.parametrize(
    ("quote", "partial"),
    [
        # 3:103 begins «واعتصموا»: a quote may leave off a leading و or ف. It is under 40%
        # of that long verse, so it is reviewed too (D-055).
        ("﴿اعتصموا بحبل الله جميعا ولا تفرقوا﴾", True),
        # Whole words from inside 21:107.
        ("﴿أرسلناك إلا رحمة للعالمين﴾", False),
    ],
)
def test_whole_word_quote_is_still_the_verse(quote, partial):
    result = resolve_quran(quote, "en")
    keys = [flag.key for flag in result["flags"]]
    assert "quran_from_approved" in keys
    assert "quran_mismatch" not in keys
    assert result["review"] is partial


def test_every_verse_matches_a_whole_word_quote_from_inside_it():
    idx = get_index()
    for verse in idx.verses:
        words = verse["norm"].split()
        if len(words) < 3:
            continue
        middle = len(words) // 2 - 1 if len(words) > 3 else 0
        quote = " ".join(words[middle : middle + 3])
        spans = idx.exact_spans(quote)
        assert any(idx.word_aligned(span) for span in spans), verse["ref"]
