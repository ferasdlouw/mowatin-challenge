import json
from pathlib import Path

from app.pipeline.classifier import classify
from app.pipeline.segmenter import segment


def test_segmenter_basic():
    text = "التوحيد أساس الإسلام. قال الله تعالى: ﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾. وقال النبي ﷺ: «إنما الأعمال بالنيات»."
    segments = segment(text)
    assert segments == [
        "التوحيد أساس الإسلام.",
        "قال الله تعالى: ﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾.",
        "وقال النبي ﷺ: «إنما الأعمال بالنيات».",
    ]


def test_segmenter_no_punctuation_in_span():
    text = "الآية ﴿اللَّهُ لَا إِلَهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ﴾، وهذا من أعظم الذكر."
    segments = segment(text)
    assert segments == ["الآية ﴿اللَّهُ لَا إِلَهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ﴾،", "وهذا من أعظم الذكر."]


def test_segmenter_multiple_spans():
    text = "﴿آية ١﴾ و﴿آية ٢﴾."
    segments = segment(text)
    assert segments == ["﴿آية ١﴾ و﴿آية ٢﴾."]


def test_classifier_hadith():
    res = classify("قال النبي ﷺ: «إنما الأعمال بالنيات»")
    assert res["category"] == "hadith"
    # An attribution is unverified (level C) until the hadith matcher confirms it (D-013).
    assert res["level"] == "C"


# D-024: a sentence with a fatwa signal is one level-D segment.
DEV = Path(__file__).resolve().parents[2] / "data" / "testset" / "dev.jsonl"
FRANCE_QUESTION = "أنا أعيش في فرنسا، هل يجوز لي أن أتزوج من غير مسلمة؟"


def _dev(case_id: str) -> str:
    for line in DEV.read_text(encoding="utf-8").splitlines():
        if line.strip() and json.loads(line)["id"] == case_id:
            return json.loads(line)["text_ar"]
    raise KeyError(case_id)


def test_fatwa_sentence_keeps_personal_context_whole():
    assert segment(FRANCE_QUESTION) == [FRANCE_QUESTION]
    assert classify(FRANCE_QUESTION) == {"category": "fatwa_like", "level": "D"}


def test_fatwa_sentence_whole_but_next_sentence_split_as_before():
    text = FRANCE_QUESTION + " التوحيد أساس الإسلام، والصلاة عماد الدين."
    assert segment(text) == [FRANCE_QUESTION, "التوحيد أساس الإسلام،", "والصلاة عماد الدين."]


def test_dev_level_d_cases_are_one_fatwa_segment():
    for case_id in ("T086", "T140"):
        parts = segment(_dev(case_id))
        assert len(parts) == 1, case_id
        assert classify(parts[0])["level"] == "D", case_id


def test_t097_still_split_and_not_referred():
    parts = segment(_dev("T097"))
    assert len(parts) == 2
    assert all(classify(part)["category"] != "fatwa_like" for part in parts)


def test_france_question_is_one_segment_in_review_through_api(client):
    resp = client.post("/v1/translate", json={"text": FRANCE_QUESTION, "target_lang": "en"})
    body = resp.json()
    assert [(s["type"], s["level"]) for s in body["segments"]] == [("fatwa_like", "D")]
    assert body["review_queue"] == [1]
