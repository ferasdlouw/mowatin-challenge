"""D-063 (code audit item 11): one text cap, from the frozen contract.

The request schema had ``max_length=4000`` written in, while ``MAX_TEXT_CHARS`` accepted any
value: raised above 4000 it was silently ignored (the schema rejected the text first). It can
now only lower the cap, and a larger value fails at startup with a clear message.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app
from app.schemas import TEXT_MAX_CHARS, TranslateRequest


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, env="test", **values)  # type: ignore[arg-type]


def test_schema_and_setting_share_the_contract_cap():
    assert TEXT_MAX_CHARS == 4000
    assert TranslateRequest.model_fields["text"].metadata[-1].max_length == TEXT_MAX_CHARS
    assert _settings().max_text_chars == TEXT_MAX_CHARS


def test_raising_the_cap_fails_at_startup():
    with pytest.raises(ValidationError, match="max_text_chars"):
        _settings(max_text_chars=TEXT_MAX_CHARS + 1)


def test_lowering_the_cap_applies():
    client = TestClient(create_app(_settings(max_text_chars=100)))
    resp = client.post("/v1/translate", json={"text": "ا" * 101, "target_lang": "en"})
    assert resp.status_code == 413
    assert "100" in resp.json()["message"]
