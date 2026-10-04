"""Security headers, and the API docs hidden in production."""

from __future__ import annotations

import pytest

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


def test_security_headers_on_every_response(make_client):
    client = make_client()
    for resp in (client.get("/health"), client.get("/nope")):
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["referrer-policy"] == "no-referrer"


def test_no_store_on_translate_including_errors(make_client):
    client = make_client(rate_limit_per_min=2)
    ok = client.post("/v1/translate", json={"text": "نص"})
    bad = client.post("/v1/translate", json={"text": "نص", "x": 1})
    limited = client.post("/v1/translate", json={"text": "نص"})
    assert [r.status_code for r in (ok, bad, limited)] == [200, 400, 429]
    for resp in (ok, bad, limited):
        assert resp.headers["cache-control"] == "no-store"
    assert "cache-control" not in client.get("/health").headers


@pytest.mark.parametrize("env", ["production", "Production", " PRODUCTION "])
def test_docs_hidden_in_production(make_client, env):
    client = make_client(env=env)
    for path in DOC_PATHS:
        assert client.get(path).status_code == 404, path
    assert client.get("/health").status_code == 200


def test_docs_visible_in_development(make_client):
    client = make_client(env="development")
    for path in DOC_PATHS:
        assert client.get(path).status_code == 200, path


# Phase SEC Batch 7 (F10): the API cannot be framed, sniffed or used as a script source.
HARDENING = {
    "strict-transport-security": "max-age=31536000",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "x-frame-options": "DENY",
    "cross-origin-resource-policy": "same-site",
}


def test_hardening_headers_on_every_api_response(make_client):
    client = make_client(rate_limit_per_min=1)
    responses = [
        client.get("/health"),
        client.get("/nope"),
        client.post("/v1/translate", json={"text": "نص"}),
        client.post("/v1/translate", json={"text": "نص"}),  # 429
        client.get("/v1/glossary", params={"q": "x" * 201}),  # 429 too
    ]
    assert responses[3].status_code == 429
    for resp in responses:
        for name, value in HARDENING.items():
            assert resp.headers[name] == value, (resp.status_code, name)


def test_cors_still_works_with_hardening_headers(make_client):
    client = make_client()
    origin = "https://mowatin.pages.dev"
    preflight = client.options(
        "/v1/translate",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
    resp = client.post("/v1/translate", json={"text": "نص"}, headers={"Origin": origin})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == origin
    assert resp.headers["cross-origin-resource-policy"] == "same-site"


def test_docs_pages_keep_working_in_development(make_client):
    client = make_client(env="development")
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "content-security-policy" not in resp.headers
