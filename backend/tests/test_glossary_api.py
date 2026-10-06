"""/health and /v1/glossary read the same index as the pipeline: every data/glossary/*.json."""

from __future__ import annotations

import builtins
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.pipeline import glossary as glossary_module

GLOSSARY_DIR = Path(__file__).resolve().parents[2] / "data" / "glossary"


def _ids_from_files() -> set[str]:
    ids: set[str] = set()
    for path in GLOSSARY_DIR.glob("*.json"):
        ids |= {item["id"] for item in json.loads(path.read_text(encoding="utf-8"))}
    return ids


def test_health_counts_unique_ids_across_all_files(client):
    expected = _ids_from_files()
    assert expected
    assert client.get("/health").json()["glossary_terms"] == len(expected)


def test_search_arabic_finds_tawhid(client):
    resp = client.get("/v1/glossary", params={"q": "التوحيد"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert "tawhid" in [r["id"] for r in results]
    tawhid = next(r for r in results if r["id"] == "tawhid")
    assert tawhid["en"] and tawhid["fr"]


def test_search_ignores_tashkeel(client):
    ids = [r["id"] for r in client.get("/v1/glossary", params={"q": "التَّوْحِيد"}).json()["results"]]
    assert "tawhid" in ids


def test_search_matches_en_and_fr_preferred(client):
    term = json.loads((GLOSSARY_DIR / "aqeedah.json").read_text(encoding="utf-8"))[0]
    for lang in ("en", "fr"):
        query = term[lang]["preferred"].upper()
        ids = [r["id"] for r in client.get("/v1/glossary", params={"q": query}).json()["results"]]
        assert term["id"] in ids, lang


def test_search_matches_a_variant(client):
    ids = [r["id"] for r in client.get("/v1/glossary", params={"q": "اللهم"}).json()["results"]]
    assert "allah" in ids


@pytest.mark.parametrize("q", ["", "   "])
def test_empty_query_returns_no_results(client, q):
    resp = client.get("/v1/glossary", params={"q": q})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


def test_missing_query_returns_no_results(client):
    assert client.get("/v1/glossary").json() == {"results": []}


def test_results_have_unique_ids(client):
    ids = [r["id"] for r in client.get("/v1/glossary", params={"q": "ال"}).json()["results"]]
    assert ids
    assert len(ids) == len(set(ids))


def test_nothing_is_read_from_en_or_fr_json(settings, monkeypatch):
    opened: list[str] = []
    real_open = builtins.open

    def spy_open(file, *args, **kwargs):
        opened.append(Path(file).name)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy_open)
    glossary_module.get_index.cache_clear()
    with TestClient(create_app(settings=settings)) as client:
        client.get("/health")
        client.get("/v1/glossary", params={"q": "التوحيد"})

    assert "aqeedah.json" in opened  # the spy saw the real loader
    assert "en.json" not in opened
    assert "fr.json" not in opened
