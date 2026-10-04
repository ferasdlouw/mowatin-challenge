import json
from pathlib import Path

import pytest

import app.pipeline.quran as quran_module
from app.pipeline.quran import resolve_quran

DEV_DATA = Path(__file__).parent.parent.parent.parent / "data" / "testset" / "dev.jsonl"


@pytest.fixture(autouse=True)
def mock_translations_dir(monkeypatch, tmp_path):
    trans_dir = tmp_path / "translations"
    trans_dir.mkdir()
    en_path = trans_dir / "en.json"
    en_path.write_text(
        json.dumps(
            {
                "status": "verified",
                "language": "en",
                "edition": "Saheeh International",
                "verses": {
                    "1:1": "In the name of Allah...",
                    "2:153": "O you who have believed, seek help through patience and prayer. Indeed, Allah is with the patient.",
                    "16:90": "Indeed, Allah orders justice and good conduct...",
                    "2:183": "O you who have believed, decreed upon you is fasting...",
                    "29:45": "Recite, [O Muhammad], what has been revealed to you...",
                    "6:162": "Say, 'Indeed, my prayer, my rites of sacrifice...'",
                    "3:159": "So by mercy from Allah, [O Muhammad], you were lenient...",
                    "16:125": "Invite to the way of your Lord with wisdom...",
                    "1:2": "[fixture 1:2]",
                    "2:256": "[fixture 2:256]",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(quran_module, "TRANSLATIONS_DIR", trans_dir)
    # Clear the global index so it reloads with the mock
    quran_module.get_index.cache_clear()
    yield
    quran_module.get_index.cache_clear()


def load_dev_cases(category):
    cases = []
    with open(DEV_DATA, encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            if data.get("category") == category:
                cases.append(data)
    return cases


def test_quran_quotes():
    cases = load_dev_cases("quran_quote")
    assert len(cases) > 0, "No quran_quote cases found in dev.jsonl"
    for case in cases:
        text = case["text_ar"]
        res = resolve_quran(text, "en")
        assert res["output"] is not None
        assert (
            "O you who have believed" in res["output"]
            or "Indeed" in res["output"]
            or "Recite" in res["output"]
            or "Say" in res["output"]
            or "Invite" in res["output"]
            or "mercy" in res["output"]
        )
        assert len(res["sources"]) == 1
        assert res["sources"][0].kind == "quran"
        assert res["sources"][0].ref in [
            "2:153",
            "16:90",
            "2:183",
            "29:45",
            "6:162",
            "3:159",
            "16:125",
        ]
        assert any(f.key == "quran_from_approved" for f in res["flags"])
        assert not res["review"]


def test_quran_misquotes():
    """D-007: the correct verse's approved translation is inserted, with a block flag + review."""
    cases = load_dev_cases("quran_misquote")
    assert len(cases) > 0, "No quran_misquote cases found in dev.jsonl"
    for case in cases:
        expected_ref = case["expect"]["quran_refs"][0]
        res = resolve_quran(case["text_ar"], "en")
        assert res["output"] == f"﴿[fixture {expected_ref}]﴾", case["id"]
        assert res["review"] is True
        assert [(s.kind, s.ref, s.edition) for s in res["sources"]] == [
            ("quran", expected_ref, "Saheeh International")
        ]
        block_flag = next(f for f in res["flags"] if f.key == "quran_mismatch")
        assert block_flag.type == "block"
        ref, correct = block_flag.detail.split("|", 1)
        assert ref == expected_ref
        assert correct
        assert not any(f.key == "quran_translation_pending" for f in res["flags"])


def test_quran_misquote_with_placeholder_slot_is_null_and_pending(tmp_path):
    """No approved translation: keep output null, block + review, and say the translation is pending."""
    (tmp_path / "translations" / "en.json").write_text(
        json.dumps({"status": "placeholder", "verses": {}}), encoding="utf-8"
    )
    quran_module.get_index.cache_clear()
    for case in load_dev_cases("quran_misquote"):
        res = resolve_quran(case["text_ar"], "en")
        assert res["output"] is None
        assert res["review"] is True
        assert res["sources"] == []
        assert [(f.type, f.key) for f in res["flags"]] == [
            ("block", "quran_mismatch"),
            ("info", "quran_translation_pending"),
        ]


def test_approved_verse_count_skips_placeholder_and_falls_back_to_fr(tmp_path):
    trans_dir = tmp_path / "translations"
    assert quran_module.approved_verse_count() == 10
    (trans_dir / "en.json").write_text(json.dumps({"status": "placeholder"}), encoding="utf-8")
    quran_module.get_index.cache_clear()
    assert quran_module.approved_verse_count() == 0
    (trans_dir / "fr.json").write_text(
        json.dumps({"status": "draft", "verses": {"1:1": "a", "1:2": "b"}}), encoding="utf-8"
    )
    quran_module.get_index.cache_clear()
    assert quran_module.approved_verse_count() == 2


def test_partial_verse_policy():
    # Less than 20% (e.g. بالصبر is 6 chars in normalized, 2:153 is 60. 6/60 = 10%)
    short_quote = "﴿بِالْعَدْلِ﴾"
    res = resolve_quran(short_quote, "en")
    assert res["output"] is None
    assert res["review"] is True
    assert any(f.key == "quran_not_found" for f in res["flags"])

    # Ambiguous match (e.g. repeated phrase "فَبِأَيِّ آلَاءِ رَبِّكُمَا تُكَذِّبَانِ")
    ambig_quote = "﴿فَبِأَيِّ آلَاءِ رَبِّكُمَا تُكَذِّبَانِ﴾"
    res = resolve_quran(ambig_quote, "en")
    assert any(f.key == "quran_ambiguous" for f in res["flags"])
    assert any(f.key == "quran_translation_pending" for f in res["flags"])
