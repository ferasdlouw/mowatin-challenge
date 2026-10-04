"""Tests for POST /v1/translate — request validation and response shape (ARCHITECTURE.md §4)."""

from __future__ import annotations

CONTRACT_SEGMENT_KEYS = {
    "id",
    "source",
    "output",
    "type",
    "level",
    "locked_terms",
    "marks",
    "sources",
    "confidence",
    "flags",
    "baseline",
}


def test_valid_request(client):
    """A minimal valid request returns 200 with the §4 top-level fields only."""
    resp = client.post("/v1/translate", json={"text": "بسم الله الرحمن الرحيم"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"segments", "summary", "review_queue", "disclosure"}
    assert set(body["summary"]) == {"segments", "flagged", "avg_confidence"}
    assert isinstance(body["review_queue"], list)
    assert isinstance(body["disclosure"], str)


def test_contract_request_fields_accepted(client):
    """The request uses the §4 names the frontend sends: target_lang and audience."""
    resp = client.post(
        "/v1/translate",
        json={"text": "الدعوة إلى الله", "target_lang": "fr", "audience": "academic"},
    )
    assert resp.status_code == 200


def test_response_shape_matches_normalize(client):
    """Each segment carries every field the frontend's normalize() reads."""
    resp = client.post("/v1/translate", json={"text": "الدعوة إلى الله"})
    seg = resp.json()["segments"][0]
    assert set(seg) == CONTRACT_SEGMENT_KEYS
    assert isinstance(seg["id"], int)
    assert seg["type"] in ("quran", "hadith", "term_heavy", "general", "fatwa_like")
    assert seg["level"] in ("A", "B", "C", "D")
    assert isinstance(seg["output"], str | type(None))
    assert 0.0 <= seg["confidence"] <= 1.0
    for key in ("locked_terms", "marks", "sources", "flags"):
        assert isinstance(seg[key], list)


def test_summary_counts_segments(client):
    """summary.segments matches the segment list and flagged matches the review queue."""
    body = client.post("/v1/translate", json={"text": "بسم الله"}).json()
    assert body["summary"]["segments"] == len(body["segments"])
    assert body["summary"]["flagged"] == len(body["review_queue"])


def test_compare_mode_includes_baseline(client):
    """mode=compare should include a baseline object."""
    resp = client.post(
        "/v1/translate",
        json={"text": "بسم الله", "mode": "compare"},
    )
    assert resp.status_code == 200
    baseline = resp.json()["segments"][0]["baseline"]
    assert baseline is not None
    assert "output" in baseline
    assert "wrong" in baseline
    assert "why" in baseline


def test_localize_mode_no_baseline(client):
    """mode=localize should NOT include a baseline."""
    resp = client.post(
        "/v1/translate",
        json={"text": "بسم الله", "mode": "localize"},
    )
    assert resp.status_code == 200
    assert resp.json()["segments"][0]["baseline"] is None


def test_empty_text_rejected(client):
    """Empty text should be rejected → 400."""
    resp = client.post("/v1/translate", json={"text": ""})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] is True
    assert body["code"] == "VALIDATION_ERROR"


def test_missing_text_rejected(client):
    """Missing text field should be rejected → 400."""
    resp = client.post("/v1/translate", json={"target_lang": "en"})
    assert resp.status_code == 400


def test_text_too_long_413(client):
    """Text over 4000 chars → 413."""
    long_text = "ا" * 4001
    resp = client.post("/v1/translate", json={"text": long_text})
    assert resp.status_code == 413
    body = resp.json()
    assert body["error"] is True
    assert body["code"] == "TEXT_TOO_LONG"


def test_invalid_lang_rejected(client):
    """Invalid target_lang value → 400."""
    resp = client.post(
        "/v1/translate",
        json={"text": "بسم الله", "target_lang": "de"},
    )
    assert resp.status_code == 400


def test_invalid_audience_rejected(client):
    """Invalid audience value → 400."""
    resp = client.post(
        "/v1/translate",
        json={"text": "بسم الله", "audience": "expert"},
    )
    assert resp.status_code == 400


def test_invalid_mode_rejected(client):
    """Invalid mode value → 400."""
    resp = client.post(
        "/v1/translate",
        json={"text": "بسم الله", "mode": "debug"},
    )
    assert resp.status_code == 400


def test_extra_fields_rejected(client):
    """Extra fields in the request body → 400 (model_config extra=forbid)."""
    resp = client.post(
        "/v1/translate",
        json={"text": "بسم الله", "extra_field": "value"},
    )
    assert resp.status_code == 400


def test_legacy_lang_field_rejected(client):
    """The pre-contract name ``lang`` is an unknown field → 400."""
    resp = client.post("/v1/translate", json={"text": "بسم الله", "lang": "en"})
    assert resp.status_code == 400


def test_all_valid_langs(client):
    """Both 'en' and 'fr' are accepted."""
    for lang in ("en", "fr"):
        resp = client.post(
            "/v1/translate",
            json={"text": "بسم الله", "target_lang": lang},
        )
        assert resp.status_code == 200, f"lang={lang} should be accepted"


def test_all_valid_modes(client):
    """All three modes are accepted."""
    for mode in ("localize", "raw", "compare"):
        resp = client.post(
            "/v1/translate",
            json={"text": "بسم الله", "mode": mode},
        )
        assert resp.status_code == 200, f"mode={mode} should be accepted"


def test_all_valid_audiences(client):
    """All four §4 audiences are accepted."""
    for aud in ("general_non_muslim", "new_muslim", "youth", "academic"):
        resp = client.post(
            "/v1/translate",
            json={"text": "بسم الله", "audience": aud},
        )
        assert resp.status_code == 200, f"audience={aud} should be accepted"


def test_max_length_boundary(client):
    """Exactly 4000 chars should be accepted."""
    text = "ا" * 4000
    resp = client.post("/v1/translate", json={"text": text})
    assert resp.status_code == 200


def test_error_response_shape(client):
    """All error responses must have {error, message, code}."""
    resp = client.post("/v1/translate", json={"text": ""})
    body = resp.json()
    assert body["error"] is True
    assert isinstance(body["message"], str)
    assert body["message"]  # non-empty
    assert "code" in body


def test_no_stack_trace_in_error(client):
    """Error responses must never contain stack traces."""
    resp = client.post("/v1/translate", json={"text": ""})
    body_str = resp.text
    assert "Traceback" not in body_str
    assert 'File "' not in body_str


def test_review_queue_lists_low_confidence_and_warned_segments():
    """review_queue holds ids under 0.75 confidence or with a non-info flag, like the client."""
    from app.pipeline.report import assemble
    from app.schemas import Segment, SegmentFlag

    segments = [
        Segment(id=1, confidence=0.95),
        Segment(id=2, confidence=0.5),
        Segment(id=3, confidence=0.9, flags=[SegmentFlag(severity="warn", text="x")]),
        Segment(id=4, confidence=0.9, flags=[SegmentFlag(severity="info", text="x")]),
    ]
    body = assemble(segments)
    assert body.review_queue == [2, 3]
    assert body.summary.flagged == 2
    assert body.summary.avg_confidence == 0.81
