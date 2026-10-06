"""D-062 (code audit item 10): 413 «text too long» is for the translation text only.

Before, any field over its length cap answered 413 with the 4000-character message, so a
glossary search of 201 characters was told the text was longer than 4000 characters.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, env="test")))  # type: ignore[call-arg]


def test_long_glossary_query_is_a_validation_error_not_text_too_long():
    resp = _client().get("/v1/glossary", params={"q": "ا" * 201})
    assert resp.status_code == 400
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_glossary_query_at_its_cap_is_fine():
    assert _client().get("/v1/glossary", params={"q": "ا" * 200}).status_code == 200


def test_long_translation_text_is_still_413():
    resp = _client().post("/v1/translate", json={"text": "ا" * 4001, "target_lang": "en"})
    assert resp.status_code == 413
    assert resp.json()["code"] == "TEXT_TOO_LONG"
