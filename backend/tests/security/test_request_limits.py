"""Body cap (413), text cap (413), strict request schema (400) and kept 4xx codes."""

from __future__ import annotations

import json

from app.security.body_limit import max_body_bytes

URL = "/v1/translate"
JSON_HEADERS = {"Content-Type": "application/json"}


def test_413_on_declared_content_length(make_client):
    client = make_client(max_text_chars=100)
    body = json.dumps({"text": "ب" * 50, "pad": "x" * max_body_bytes(100)})
    resp = client.post(URL, content=body, headers=JSON_HEADERS)
    assert resp.status_code == 413
    assert resp.json()["code"] == "TEXT_TOO_LONG"


def test_413_on_streamed_body_without_length(make_client):
    client = make_client(max_text_chars=100)

    def chunks():
        yield b'{"text": "'
        for _ in range(4):
            yield b"x" * 512
        yield b'"}'

    resp = client.post(URL, content=chunks(), headers=JSON_HEADERS)
    assert "content-length" not in resp.request.headers
    assert resp.status_code == 413


def test_413_when_text_exceeds_configured_limit(make_client):
    client = make_client(max_text_chars=100)
    resp = client.post(URL, json={"text": "ب" * 101})
    assert resp.status_code == 413
    assert resp.json()["code"] == "TEXT_TOO_LONG"
    assert client.post(URL, json={"text": "ب" * 100}).status_code == 200


def test_413_at_schema_limit(make_client):
    assert make_client().post(URL, json={"text": "ب" * 4001}).status_code == 413


def test_400_on_extra_field(make_client):
    resp = make_client().post(URL, json={"text": "نص", "debug": True})
    assert resp.status_code == 400
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_400_on_bad_enum(make_client):
    assert make_client().post(URL, json={"text": "نص", "target_lang": "de"}).status_code == 400


def test_400_on_malformed_json(make_client):
    resp = make_client().post(URL, content=b"{not json", headers=JSON_HEADERS)
    assert resp.status_code == 400


def test_unknown_route_stays_404(make_client):
    resp = make_client().get("/nope")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_wrong_method_stays_405(make_client):
    assert make_client().get(URL).status_code == 405
