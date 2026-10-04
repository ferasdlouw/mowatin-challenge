"""Orchestrator end to end through POST /v1/translate, including the Phase 2d dev done-when checks.

Run with ``-s`` to see the printed counts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.pipeline.fatwa_guard as guard_module
import app.pipeline.orchestrator as orchestrator_module
import app.pipeline.quran as quran_module
from app.config import Settings
from app.pipeline.report import load_messages, needs_review
from app.schemas import TranslateResponse

DEV = Path(__file__).resolve().parents[3] / "data" / "testset" / "dev.jsonl"
TARGETS = ("en", "fr")


@pytest.fixture()
def settings() -> Settings:
    """The conftest settings with room for a full dev sweep under the per-IP limit."""
    return Settings(
        _env_file=None,
        env="test",
        llm_provider="",
        llm_api_key="",
        llm_model="",
        rate_limit_per_min=10_000,
    )  # type: ignore[call-arg]


def _dev_cases() -> list[dict]:
    with DEV.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _post(client, text: str, target: str = "en", mode: str = "localize") -> dict:
    resp = client.post("/v1/translate", json={"text": text, "target_lang": target, "mode": mode})
    assert resp.status_code == 200
    return resp.json()


def _is_hadith_review_flag(flag: dict) -> bool:
    messages = load_messages()
    fabricated_prefix = messages["hadith_fabricated"].split("{ruling}")[0]
    return flag["severity"] in ("warn", "block") and (
        flag["text"] == messages["hadith_unsourced"] or flag["text"].startswith(fabricated_prefix)
    )


def _referred(body: dict) -> bool:
    referral = load_messages()["fatwa_referral"]
    return any(
        s["level"] == "D"
        or s["type"] == "fatwa_like"
        or any(f["text"] == referral for f in s["flags"])
        for s in body["segments"]
    )


def test_dev_hadith_unsourced_all_in_review_with_flag(client):
    cases = [c for c in _dev_cases() if c["category"] == "hadith_unsourced"]
    assert cases
    passed = 0
    for case in cases:
        for target in TARGETS:
            body = _post(client, case["text_ar"], target)
            hadith = [s for s in body["segments"] if s["type"] == "hadith"]
            assert hadith, case["id"]
            for seg in hadith:
                assert seg["output"] is None, case["id"]
                assert seg["sources"] == [], case["id"]
                assert any(_is_hadith_review_flag(f) for f in seg["flags"]), case["id"]
                assert seg["id"] in body["review_queue"], case["id"]
            passed += 1
    print(f"\n[2d] hadith_unsourced in review with flag: {passed}/{len(cases) * len(TARGETS)}")
    assert passed == len(cases) * len(TARGETS)


def test_dev_level_d_all_referred_and_in_review(client):
    cases = [c for c in _dev_cases() if c["category"] == "level_d"]
    assert cases
    referral = load_messages()["fatwa_referral"]
    passed = 0
    for case in cases:
        for target in TARGETS:
            body = _post(client, case["text_ar"], target)
            guarded = [s for s in body["segments"] if s["type"] == "fatwa_like"]
            assert guarded, case["id"]
            for seg in guarded:
                assert seg["level"] == "D", case["id"]
                assert seg["output"] is None, case["id"]
                assert {"severity": "warn", "text": referral} in seg["flags"], case["id"]
                assert seg["id"] in body["review_queue"], case["id"]
            passed += 1
    print(f"\n[2d] level_d referred and in review: {passed}/{len(cases) * len(TARGETS)}")
    assert passed == len(cases) * len(TARGETS)


def test_dev_must_refer_false_not_referred(client):
    cases = [c for c in _dev_cases() if not c["expect"]["must_refer"]]
    assert cases
    referred_ids = [
        f"{case['id']}/{target}"
        for case in cases
        for target in TARGETS
        if _referred(_post(client, case["text_ar"], target))
    ]
    total = len(cases) * len(TARGETS)
    print(f"\n[2d] must_refer=false referred by the guard: {len(referred_ids)}/{total}")
    assert referred_ids == []


@pytest.mark.parametrize("mode", ["localize", "raw", "compare"])
def test_every_dev_case_returns_a_contract_valid_response(client, mode):
    for case in _dev_cases():
        body = _post(client, case["text_ar"], "en", mode)
        parsed = TranslateResponse.model_validate(body)
        assert parsed.segments, case["id"]
        assert [s.id for s in parsed.segments] == list(range(1, len(parsed.segments) + 1))
        assert body["review_queue"] == [s.id for s in parsed.segments if needs_review(s)]
        assert body["summary"]["segments"] == len(parsed.segments)
        assert body["summary"]["flagged"] == len(body["review_queue"])
        assert all((s.baseline is not None) == (mode == "compare") for s in parsed.segments)


def test_raw_mode_skips_all_handling(client):
    body = _post(client, "قال النبي ﷺ: «حب الوطن من الإيمان». هل يجوز لي ترك الصلاة؟", mode="raw")
    for seg in body["segments"]:
        assert (seg["type"], seg["level"], seg["sources"]) == ("general", "B", [])
        # D-038: raw output is unprotected, so exactly one warn flag keeps it in review.
        assert [flag["severity"] for flag in seg["flags"]] == ["warn"]
        assert seg["confidence"] == 0.0
        assert seg["id"] in body["review_queue"]
        assert seg["output"] is None


def test_llm_paths_are_null_and_in_review_until_phase_3(client, monkeypatch):
    monkeypatch.setattr(orchestrator_module, "load_messages", dict)
    body = _post(client, "التوحيد أساس الإسلام.")
    seg = body["segments"][0]
    assert seg["type"] == "term_heavy"
    assert seg["output"] is None
    assert seg["confidence"] == 0.0
    assert seg["flags"] == []
    assert seg["id"] in body["review_queue"]
    assert {"kind": "glossary", "ref": "التوحيد", "edition": None, "grade": None} in seg["sources"]


def test_general_segment_has_no_sources(client):
    seg = _post(client, "مرحبا بكم جميعا.")["segments"][0]
    assert (seg["type"], seg["level"], seg["sources"]) == ("general", "B", [])


@pytest.fixture()
def approved_verse(monkeypatch, tmp_path):
    """A tmp approved EN translation holding 2:153 only."""
    (tmp_path / "en.json").write_text(
        json.dumps(
            {"status": "verified", "edition": "Fixture Edition", "verses": {"2:153": "V."}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(quran_module, "TRANSLATIONS_DIR", tmp_path)
    quran_module.get_index.cache_clear()
    yield
    quran_module.get_index.cache_clear()


def test_quran_from_approved_translation_is_not_in_review(client, approved_verse):
    text = "﴿يَا أَيُّهَا الَّذِينَ آمَنُوا اسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ﴾"
    body = _post(client, text)
    seg = body["segments"][0]
    assert seg["type"] == "quran"
    assert seg["output"] == "﴿V.﴾"
    assert seg["confidence"] == 1.0
    assert seg["sources"][0]["ref"] == "2:153"
    # quran_from_approved, then the quoted words with Tanzil's tashkeel (D-044).
    assert [f["severity"] for f in seg["flags"]] == ["info", "info"]
    assert body["review_queue"] == []


def test_quran_pending_translation_goes_to_review(client, monkeypatch, tmp_path):
    """A placeholder translation slot: no verse text is generated, the segment goes to review."""
    (tmp_path / "en.json").write_text(json.dumps({"status": "placeholder"}), encoding="utf-8")
    monkeypatch.setattr(quran_module, "TRANSLATIONS_DIR", tmp_path)
    quran_module.get_index.cache_clear()
    try:
        body = _post(client, "﴿إِنَّ اللَّهَ مَعَ الصَّابِرِينَ﴾")
    finally:
        quran_module.get_index.cache_clear()
    seg = body["segments"][0]
    assert seg["output"] is None
    pending = load_messages()["quran_translation_pending"]
    assert {"severity": "info", "text": pending} in seg["flags"]
    assert body["review_queue"] == [seg["id"]]


@pytest.mark.parametrize(
    "messages",
    [{"glossary_source": "المسرد: {term}"}, {"glossary_source": " المسرد: {term} "}],
)
def test_glossary_ref_uses_message_key(monkeypatch, messages):
    monkeypatch.setattr(orchestrator_module, "load_messages", lambda: messages)
    assert orchestrator_module.glossary_ref("التوحيد") == "المسرد: التوحيد"


@pytest.mark.parametrize(
    "messages",
    [
        {},
        {"glossary_source": ""},
        {"glossary_source": None},
        {"glossary_source": "المسرد"},
        {"glossary_source": "{term} {other}"},
    ],
)
def test_glossary_ref_falls_back_to_bare_term(monkeypatch, messages):
    """D-019: never raise, never return the key name."""
    monkeypatch.setattr(orchestrator_module, "load_messages", lambda: messages)
    assert orchestrator_module.glossary_ref("التوحيد") == "التوحيد"


def test_glossary_source_label_reaches_the_response(client, monkeypatch):
    monkeypatch.setattr(
        orchestrator_module, "load_messages", lambda: {"glossary_source": "المسرد: {term}"}
    )
    seg = _post(client, "التوحيد أساس الإسلام.")["segments"][0]
    assert {"kind": "glossary", "ref": "المسرد: التوحيد", "edition": None, "grade": None} in seg[
        "sources"
    ]


def test_corrected_misquote_is_inserted_but_not_certain(client, monkeypatch, tmp_path):
    """D-007 through the API: approved text of the correct verse, block flag, confidence 0."""
    (tmp_path / "en.json").write_text(
        json.dumps({"status": "verified", "edition": "Fixture Edition", "verses": {"1:2": "V."}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(quran_module, "TRANSLATIONS_DIR", tmp_path)
    quran_module.get_index.cache_clear()
    try:
        body = _post(client, "قال الله تعالى: ﴿الْحَمْدُ لِلَّهِ رَبِّ الْمُسْلِمِينَ﴾.")
    finally:
        quran_module.get_index.cache_clear()
    seg = body["segments"][0]
    assert seg["output"] == "﴿V.﴾"
    assert seg["sources"][0]["ref"] == "1:2"
    assert seg["confidence"] == 0.0
    assert [f["severity"] for f in seg["flags"]] == ["block"]
    assert body["review_queue"] == [seg["id"]]


@pytest.fixture()
def fatwa_llm(monkeypatch, tmp_path):
    """Fake literal translation + verifier for level D, and a tmp referral slot."""
    seen: dict[str, str] = {}

    async def fake_raw(text, lang, router):
        return f"Question ({lang})?", []

    async def fake_verify(text, output, *_rest, **_kw):
        seen["verified"] = output
        return 0.9, [], []

    path = tmp_path / "referral.json"
    path.write_text(
        json.dumps(
            {
                "status": "draft",
                "message": {"ar": "نص", "en": "See a scholar.", "fr": "Voyez un savant."},
                "bodies": {
                    "en": [{"name": "Body", "country": "UK", "url": "https://b.example"}],
                    "fr": [{"name": "Corps", "country": "France", "url": "https://c.example"}],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(orchestrator_module, "raw_translate", fake_raw)
    monkeypatch.setattr(orchestrator_module, "verify", fake_verify)
    monkeypatch.setattr(guard_module, "REFERRAL_PATH", path)
    guard_module.referral_message_ar.cache_clear()
    guard_module.referral_text.cache_clear()
    yield seen
    guard_module.referral_message_ar.cache_clear()
    guard_module.referral_text.cache_clear()


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("en", "Question (en)?\n\nSee a scholar.\n- Body (UK): https://b.example"),
        ("fr", "Question (fr)?\n\nVoyez un savant.\n- Corps (France): https://c.example"),
    ],
)
def test_level_d_output_is_literal_question_then_referral(client, fatwa_llm, target, expected):
    body = _post(client, "هل يجوز لي ترك الصلاة؟", target)
    seg = body["segments"][0]
    assert (seg["type"], seg["level"]) == ("fatwa_like", "D")
    assert seg["output"] == expected
    assert fatwa_llm["verified"] == f"Question ({target})?"
    assert seg["id"] in body["review_queue"]
