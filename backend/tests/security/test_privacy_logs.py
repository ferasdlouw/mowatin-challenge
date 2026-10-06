"""No user text in logs, on any path: success, 400, 413, 429, 500 and glossary search."""

from __future__ import annotations

import hashlib
import logging

import pytest

from app.pipeline import orchestrator
from app.security.privacy import fingerprint
from tests.security.conftest import PROD_ORIGIN

MARKER = "علامة_سرية_للاختبار_٧٣٩"


@pytest.fixture()
def captured(caplog):
    caplog.set_level(logging.DEBUG)
    return caplog


def _assert_marker_absent(caplog) -> None:
    assert caplog.records
    for record in caplog.records:
        rendered = record.getMessage() + str(record.exc_text or "")
        assert MARKER not in rendered, record.name


def test_text_never_logged_on_any_reply(make_client, captured):
    client = make_client(max_text_chars=200, rate_limit_per_min=4)
    text = f"قال {MARKER} شيئًا"
    statuses = [
        client.post("/v1/translate", json={"text": text}).status_code,
        client.post("/v1/translate", json={"text": text, "extra": MARKER}).status_code,
        client.post("/v1/translate", json={"text": MARKER * 20}).status_code,
        client.get("/v1/glossary", params={"q": MARKER}).status_code,
        client.post("/v1/translate", json={"text": text}).status_code,
    ]
    assert statuses == [200, 400, 413, 200, 429]
    _assert_marker_absent(captured)


def test_translate_logs_fingerprint_only(make_client, captured):
    text = f"نص {MARKER}"
    make_client().post("/v1/translate", json={"text": text})
    expected = fingerprint(text)
    lines = [r.getMessage() for r in captured.records if "translate_request" in r.getMessage()]
    assert len(lines) == 1
    assert expected["sha256"] in lines[0]
    assert f'"chars": {expected["chars"]}' in lines[0]
    _assert_marker_absent(captured)


def test_unhandled_error_logs_type_not_message(make_client, captured, monkeypatch):
    async def explode(req, router, limits=None, use_cache=True):
        raise ValueError(f"cannot handle {req.text}")

    monkeypatch.setattr(orchestrator, "translate", explode)
    resp = make_client().post(
        "/v1/translate", json={"text": MARKER}, headers={"Origin": PROD_ORIGIN}
    )
    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_ERROR"
    assert MARKER not in resp.text
    assert resp.headers["access-control-allow-origin"] == PROD_ORIGIN
    assert any("unhandled_exception type=ValueError" in r.getMessage() for r in captured.records)
    _assert_marker_absent(captured)


def test_access_log_has_no_query_string(make_client, captured):
    make_client().get("/v1/glossary", params={"q": MARKER})
    access = [r.getMessage() for r in captured.records if r.name == "app.access"]
    assert access
    assert '"path": "/v1/glossary"' in access[0]
    _assert_marker_absent(captured)


def test_fingerprint_shape():
    first = fingerprint("abc")
    assert first["chars"] == 3
    assert len(first["sha256"]) == 12
    assert fingerprint("abc") == first
    assert fingerprint("abd") != first


def test_fingerprint_cannot_be_confirmed_by_hashing_a_guess():
    # NEW-6: a plain SHA-256 prefix let anyone with log access confirm a guessed short text.
    guess = "ما حكم صلاتي؟"
    plain = hashlib.sha256(guess.encode("utf-8")).hexdigest()[:12]
    assert fingerprint(guess)["sha256"] != plain
