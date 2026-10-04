"""CORS: exact allowlist + Pages previews; everything else is refused."""

from __future__ import annotations

import pytest

from app.security.cors import parse_origins
from tests.security.conftest import PROD_ORIGIN

PREVIEW_ORIGIN = "https://3f9a1c2e.mowatin.pages.dev"


def _preflight(client, origin: str, method: str = "POST"):
    return client.options(
        "/v1/translate",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )


@pytest.mark.parametrize(
    "origin", [PROD_ORIGIN, PREVIEW_ORIGIN, "https://feat-ui.mowatin.pages.dev"]
)
def test_allowed_origin_preflight(make_client, origin):
    resp = _preflight(make_client(), origin)
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == origin
    assert "DELETE" not in resp.headers["access-control-allow-methods"]


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example.com",
        "https://evil-mowatin.pages.dev",
        "https://mowatin.pages.dev.evil.com",
        "https://x.mowatin.pages.dev.evil.com",
        "http://mowatin.pages.dev",
        "http://abc.mowatin.pages.dev",
        "https://a.b.mowatin.pages.dev",
        "null",
    ],
)
def test_foreign_origin_rejected(make_client, origin):
    client = make_client()
    preflight = _preflight(client, origin)
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers

    simple = client.post("/v1/translate", json={"text": "نص"}, headers={"Origin": origin})
    assert "access-control-allow-origin" not in simple.headers


def test_allowed_origin_on_actual_request(make_client):
    resp = make_client().post(
        "/v1/translate", json={"text": "نص"}, headers={"Origin": PREVIEW_ORIGIN}
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == PREVIEW_ORIGIN
    assert "access-control-allow-credentials" not in resp.headers


def test_only_get_and_post_allowed(make_client):
    assert _preflight(make_client(), PROD_ORIGIN, method="DELETE").status_code == 400


def test_wildcard_in_env_is_dropped(make_client):
    client = make_client(allowed_origins="*, https://evil.example.com/path, " + PROD_ORIGIN)
    assert _preflight(client, "https://evil.example.com").status_code == 400
    assert _preflight(client, PROD_ORIGIN).status_code == 200


def test_parse_origins_keeps_exact_origins_only():
    raw = " https://Mowatin.pages.dev ,*, http://localhost:5173,https://a.com/, ,"
    assert parse_origins(raw) == ["https://mowatin.pages.dev", "http://localhost:5173"]


def test_rate_limited_reply_still_carries_cors(make_client):
    client = make_client(rate_limit_per_min=1)
    headers = {"Origin": PROD_ORIGIN}
    client.post("/v1/translate", json={"text": "نص"}, headers=headers)
    resp = client.post("/v1/translate", json={"text": "نص"}, headers=headers)
    assert resp.status_code == 429
    assert resp.headers["access-control-allow-origin"] == PROD_ORIGIN
    assert "retry-after" in resp.headers["access-control-expose-headers"].lower()
