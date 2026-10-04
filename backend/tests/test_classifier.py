import json
from pathlib import Path

from app.pipeline.classifier import classify
from app.pipeline.segmenter import segment

DEV = Path(__file__).resolve().parents[2] / "data" / "testset" / "dev.jsonl"


def test_classifier_quran():
    res = classify("قال الله: ﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾")
    assert res["category"] == "quran"
    assert res["level"] == "A"


def test_classifier_hadith():
    res = classify("قال النبي ﷺ: «إنما الأعمال بالنيات»")
    assert res["category"] == "hadith"
    assert res["level"] == "C"  # We agreed it defaults to C


def test_classifier_fatwa():
    res = classify("هل يجوز لي أن أفعل كذا؟")
    assert res["category"] == "fatwa_like"
    assert res["level"] == "D"


def test_classifier_term_heavy():
    # 'الإسلام' is a term
    res = classify("الإسلام دين السلام.")
    assert res["category"] == "term_heavy"
    assert res["level"] == "A"


def test_classifier_general():
    res = classify("صباح الخير يا صديقي.")
    assert res["category"] == "general"
    assert res["level"] == "B"


def test_classifier_over_referral():
    # T097
    text = "الحلال والحرام من المصطلحات الشرعية، لكن تحديد حكم معاملة شخصية بعينها يحتاج إلى معرفة تفاصيل الحالة وإحالة عند الحاجة."
    res = classify(text)
    assert res["category"] != "fatwa_like"

    text2 = "من أراد معرفة حكم كذا فليسأل"
    res2 = classify(text2)
    assert res2["category"] != "fatwa_like"


def test_fatwa_question_quoting_a_hadith_is_fatwa_like():
    """D-018: the fatwa check runs before the hadith check."""
    res = classify("قال النبي ﷺ: «الدين النصيحة»، فهل يجوز لي أن أنصح والدي أمام الناس؟")
    assert res == {"category": "fatwa_like", "level": "D"}


def test_fatwa_question_quoting_a_verse_is_fatwa_like():
    """D-018: the fatwa check runs before the quran check."""
    res = classify("قال تعالى: ﴿وَأَقِيمُوا الصَّلَاةَ﴾، ما حكم صلاتي في العمل وأنا مسافر؟")
    assert res == {"category": "fatwa_like", "level": "D"}


def test_plain_hadith_with_salutation_is_still_hadith():
    assert classify("قال النبي ﷺ: «الدين النصيحة».") == {"category": "hadith", "level": "C"}


def test_plain_verse_is_still_quran():
    assert classify("قال تعالى: ﴿وَأَقِيمُوا الصَّلَاةَ﴾.")["category"] == "quran"


EXPECTED_TYPE = {
    "quran_quote": "quran",
    "quran_misquote": "quran",
    "hadith_quote": "hadith",
    "hadith_unsourced": "hadith",
    "level_d": "fatwa_like",
}


def test_dev_categories_all_correct():
    """Phase 2b done-when, re-checked after the order change: 100% per dev category, and no
    other case is fatwa_like (T097 included). T100 and T148 are in the sealed test set."""
    per_category: dict[str, list[bool]] = {}
    for line in DEV.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        types = {classify(part)["category"] for part in segment(case["text_ar"])}
        expected = EXPECTED_TYPE.get(case["category"])
        if expected:
            ok = expected in types and (expected == "fatwa_like" or "fatwa_like" not in types)
        else:
            ok = "fatwa_like" not in types
        per_category.setdefault(case["category"], []).append(ok)
    for category, results in sorted(per_category.items()):
        print(f"\n[2.1] {category}: {sum(results)}/{len(results)}")
    assert all(all(results) for results in per_category.values()), per_category
