"""D-064 (code audit item 12): decimals and the Latin question mark in the segmenter.

Before, «3.5» was cut into two segments at its dot, and a question ending in «?» did not end
its sentence like one ending in «؟».
"""

from __future__ import annotations

import pytest

from app.pipeline.classifier import classify
from app.pipeline.segmenter import segment, segment_capped


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("سعر 3.5 دينار. ثم", ["سعر 3.5 دينار.", "ثم"]),
        ("زكاة ٢.٥ بالمئة من المال.", ["زكاة ٢.٥ بالمئة من المال."]),
        ("نسبة 12.75 في المئة", ["نسبة 12.75 في المئة"]),
        # A dot after a number at the end of a sentence still ends it.
        ("العدد 1. ثم 2.", ["العدد 1.", "ثم 2."]),
    ],
)
def test_a_decimal_point_does_not_end_a_sentence(text, expected):
    assert segment(text) == expected


def test_latin_question_mark_ends_a_sentence_like_the_arabic_one():
    latin, arabic = (
        segment("ما حكم صلاتي? التوحيد أساس الدين."),
        segment("ما حكم صلاتي؟ التوحيد أساس الدين."),
    )
    assert len(latin) == len(arabic) == 2
    assert classify(latin[0])["category"] == "fatwa_like"
    assert classify(latin[1])["category"] != "fatwa_like"


def test_capped_rest_starts_after_a_kept_decimal():
    parts, rest = segment_capped("سعر 3.5 دينار. ثم 1.25 كيلو. ثم شيء آخر.", 1)
    assert parts == ["سعر 3.5 دينار."]
    assert rest == "ثم 1.25 كيلو. ثم شيء آخر."
