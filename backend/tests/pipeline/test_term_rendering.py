"""D-065 (code audit item 13): the approved rendering is found as a whole word.

Before, the term check was a substring search on the lowercased output: «Hajj» was found in
«Hajjaj», and a character whose lowercase is longer («İ») shifted the mark to the wrong span.
"""

from __future__ import annotations

import pytest

from app.pipeline.verifier import _term_check, find_rendering
from app.schemas import LockedTerm

HAJJ = LockedTerm(ar="الحج", out="Hajj", glossary_id="hajj")


def test_rendering_inside_another_word_is_not_the_rendering():
    score, marks, flags = _term_check("Al-Hajjaj travelled to Makkah.", "en", [HAJJ])
    assert (score, marks) == (0.0, [])
    assert [flag.key for flag in flags] == ["term_check_failed"]


def test_mark_is_the_exact_span_even_after_a_long_lowercase_character():
    assert _term_check("İİ then Hajj today.", "en", [HAJJ])[:2] == (1.0, ["Hajj"])


@pytest.mark.parametrize(
    ("rendering", "text", "mark"),
    [
        ("prophet", "All the prophets were sent.", "prophets"),
        ("prière", "Les prières du jour.", "prières"),
        ("Hajj", "The Hajj's rites.", "Hajj"),
        ("Allah", "ALLAH is One.", "ALLAH"),
        ("ijma'", "By ijma' of the scholars.", "ijma'"),
        ("'aqidah", "Sound 'aqidah matters.", "'aqidah"),
    ],
)
def test_whole_word_rendering_is_found(rendering, text, mark):
    found = find_rendering(rendering, text)
    assert found is not None and found.group(0) == mark


@pytest.mark.parametrize(("rendering", "text"), [("Hajj", "Hajjaj"), ("salah", "salahuddin")])
def test_rendering_glued_to_other_letters_is_not_found(rendering, text):
    assert find_rendering(rendering, text) is None
