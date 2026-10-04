"""Tests for GET /health."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

import app.pipeline.hadith as hadith_module
import app.pipeline.quran as quran_module


def test_health_returns_ok(client):
    """Health endpoint returns status=ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "glossary_terms" in body
    assert "quran_verses" in body
    assert "hadith_entries" in body
    assert "version" in body


def test_one_version_everywhere(client, app):
    """/health, the OpenAPI title block, pyproject.toml and the frontend share one version."""
    repo = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((repo / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((repo / "frontend" / "package.json").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    assert client.get("/health").json()["version"] == version
    assert app.version == version
    assert package["version"] == version


def test_health_no_secrets(client):
    """Health response must not contain any secret or key."""
    resp = client.get("/health")
    body_str = resp.text.lower()
    for word in ("api_key", "secret", "password", "token"):
        assert word not in body_str


@pytest.fixture()
def slots(monkeypatch, tmp_path):
    """Point the Quran and hadith loaders at tmp slot dirs; returns the dir."""
    (tmp_path / "translations").mkdir()
    (tmp_path / "hadith").mkdir()
    monkeypatch.setattr(quran_module, "TRANSLATIONS_DIR", tmp_path / "translations")
    monkeypatch.setattr(hadith_module, "HADITH_DIR", tmp_path / "hadith")
    _clear_caches()
    yield tmp_path
    _clear_caches()


def _clear_caches() -> None:
    quran_module.get_index.cache_clear()
    hadith_module.load_items.cache_clear()


def _write(path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_health_counts_placeholder_slots_as_zero(client, slots):
    _write(slots / "translations" / "en.json", {"status": "placeholder", "verses": {"1:1": "x"}})
    _write(slots / "translations" / "fr.json", {"status": "placeholder", "verses": {}})
    _write(slots / "hadith" / "hadith.json", {"status": "placeholder", "items": [{"id": "x"}]})
    body = client.get("/health").json()
    assert (body["quran_verses"], body["hadith_entries"]) == (0, 0)


@pytest.mark.parametrize("status", ["draft", "verified"])
def test_health_counts_loaded_items(client, slots, status):
    verses = {f"1:{n}": "x" for n in range(1, 8)}
    _write(slots / "translations" / "en.json", {"status": status, "verses": verses})
    items = [{"id": f"h{n}"} for n in range(3)]
    _write(slots / "hadith" / "hadith.json", {"status": status, "items": items})
    body = client.get("/health").json()
    assert (body["quran_verses"], body["hadith_entries"]) == (7, 3)


def test_health_uses_fr_when_en_is_placeholder(client, slots):
    _write(slots / "translations" / "en.json", {"status": "placeholder", "verses": {}})
    _write(slots / "translations" / "fr.json", {"status": "draft", "verses": {"1:1": "x"}})
    assert client.get("/health").json()["quran_verses"] == 1


def test_health_with_real_repo_files(client):
    _clear_caches()
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"status", "glossary_terms", "quran_verses", "hadith_entries", "version"}
    assert body["quran_verses"] >= 0
    assert body["hadith_entries"] >= 0
