"""D-056 (code audit item 4): a verse in Uthmani script is the verse, not a misquote.

The index is the Simple text. Before, «ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ» kept its alef wasla
and lost its small alef, so a correct quote copied from an Uthmani mushaf was blocked as a
misquote; quotes with «وٰ», «ءا» or a vocative found nothing at all.
"""

from __future__ import annotations

import pytest

from app.pipeline.classifier import classify
from app.pipeline.quran import has_uthmani_marks, resolve_quran, uthmani_to_simple

# Well-known verses as an Uthmani mushaf writes them, with the reference each must reach.
UTHMANI = [
    ("ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ", "1:2"),
    ("ذَٰلِكَ ٱلْكِتَٰبُ لَا رَيْبَ ۛ فِيهِ", "2:2"),
    ("يَٰٓأَيُّهَا ٱلَّذِينَ ءَامَنُوا۟ ٱسْتَعِينُوا۟ بِٱلصَّبْرِ وَٱلصَّلَوٰةِ", "2:153"),
    ("وَأَقِيمُوا۟ ٱلصَّلَوٰةَ وَءَاتُوا۟ ٱلزَّكَوٰةَ", "2:43"),
    ("إِنَّ ٱللَّهَ وَمَلَٰٓئِكَتَهُۥ يُصَلُّونَ عَلَى ٱلنَّبِىِّ", "33:56"),
    ("وَإِذِ ٱبْتَلَىٰٓ إِبْرَٰهِـۧمَ رَبُّهُۥ بِكَلِمَٰتٍ", "2:124"),
    ("يَٰٓأَيُّهَا ٱلَّذِينَ ءَامَنُوا۟ كُتِبَ عَلَيْكُمُ ٱلصِّيَامُ", "2:183"),
    ("وَٱعْتَصِمُوا۟ بِحَبْلِ ٱللَّهِ جَمِيعًا وَلَا تَفَرَّقُوا۟", "3:103"),
    ("إِنَّمَا ٱلْمُؤْمِنُونَ إِخْوَةٌ", "49:10"),
    ("وَمَآ أَرْسَلْنَٰكَ إِلَّا رَحْمَةً لِّلْعَٰلَمِينَ", "21:107"),
    ("أَلَا بِذِكْرِ ٱللَّهِ تَطْمَئِنُّ ٱلْقُلُوبُ", "13:28"),
    ("فَإِنَّ مَعَ ٱلْعُسْرِ يُسْرًا إِنَّ مَعَ ٱلْعُسْرِ يُسْرًا", "94:5-6"),
    ("لَا يُكَلِّفُ ٱللَّهُ نَفْسًا إِلَّا وُسْعَهَا", "2:286"),
    ("وَقَضَىٰ رَبُّكَ أَلَّا تَعْبُدُوٓا۟ إِلَّآ إِيَّاهُ وَبِٱلْوَٰلِدَيْنِ إِحْسَٰنًا", "17:23"),
    ("وَٱلْعَصْرِ إِنَّ ٱلْإِنسَٰنَ لَفِى خُسْرٍ", "103:1-2"),
    ("قُلْ هُوَ ٱللَّهُ أَحَدٌ ٱللَّهُ ٱلصَّمَدُ", "112:1-2"),
    ("إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ", "1:5"),
    ("رَبَّنَآ ءَاتِنَا فِى ٱلدُّنْيَا حَسَنَةً وَفِى ٱلْءَاخِرَةِ حَسَنَةً وَقِنَا عَذَابَ ٱلنَّارِ", "2:201"),
    ("وَقُل رَّبِّ زِدْنِى عِلْمًا", "20:114"),
    ("لَا تَقْنَطُوا۟ مِن رَّحْمَةِ ٱللَّهِ", "39:53"),
    ("أَطِيعُوا۟ ٱللَّهَ وَأَطِيعُوا۟ ٱلرَّسُولَ", "4:59"),
    ("ٱدْعُ إِلَىٰ سَبِيلِ رَبِّكَ بِٱلْحِكْمَةِ وَٱلْمَوْعِظَةِ ٱلْحَسَنَةِ", "16:125"),
    ("إِنَّ ٱلصَّلَوٰةَ تَنْهَىٰ عَنِ ٱلْفَحْشَآءِ وَٱلْمُنكَرِ", "29:45"),
    ("وَإِذَا سَأَلَكَ عِبَادِى عَنِّى فَإِنِّى قَرِيبٌ", "2:186"),
]


def _found_at(result: dict, ref: str) -> bool:
    refs = [source.ref for source in result["sources"]]
    ambiguous = [flag.detail for flag in result["flags"] if flag.key == "quran_ambiguous"]
    return ref in refs or any(ref in detail.split(", ") for detail in ambiguous)


@pytest.mark.parametrize(("text", "ref"), UTHMANI)
@pytest.mark.parametrize("bracketed", [True, False])
def test_uthmani_verse_is_the_verse(text, ref, bracketed):
    quote = f"﴿{text}﴾" if bracketed else text
    assert classify(quote)["category"] == "quran"
    result = resolve_quran(quote, "en")
    keys = [flag.key for flag in result["flags"]]
    assert "quran_mismatch" not in keys
    assert "quran_not_found" not in keys
    assert _found_at(result, ref)


def test_uthmani_misquote_is_still_a_misquote():
    result = resolve_quran("﴿ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْمُسْلِمِينَ﴾", "en")
    assert "quran_mismatch" in [flag.key for flag in result["flags"]]
    assert result["review"] is True


def test_simple_script_misquote_differing_by_an_alef_is_still_caught():
    # «قال» for «قل»: alefs are optional only for text with Uthmani marks.
    result = resolve_quran("﴿قال هو الله أحد﴾", "en")
    assert "quran_mismatch" in [flag.key for flag in result["flags"]]


def test_uthmani_final_alef_for_alef_maqsura_is_reviewed_not_certain():
    # Known limit: «ٱلْأَقْصَا» (Simple «الأقصى»). It ends as a correction, always reviewed.
    text = "﴿سُبْحَٰنَ ٱلَّذِىٓ أَسْرَىٰ بِعَبْدِهِۦ لَيْلًا مِّنَ ٱلْمَسْجِدِ ٱلْحَرَامِ إِلَى ٱلْمَسْجِدِ ٱلْأَقْصَا﴾"
    assert resolve_quran(text, "en")["review"] is True


def test_simple_text_is_not_converted():
    text = "إن الله مع الصابرين"
    assert not has_uthmani_marks(text)
    assert uthmani_to_simple(text) == text
