"""CORS policy: an exact origin allowlist plus Cloudflare Pages preview subdomains."""

from __future__ import annotations

import logging
import re

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# Cloudflare Pages previews look like https://<hash-or-branch>.mowatin.pages.dev.
# Starlette matches this with fullmatch, so suffix tricks like
# "x.mowatin.pages.dev.evil.com" or "evil-mowatin.pages.dev" do not pass.
PREVIEW_ORIGIN_REGEX = r"https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.mowatin\.pages\.dev"

_ORIGIN_SHAPE = re.compile(r"https?://[a-z0-9.-]+(?::\d{1,5})?")

ALLOWED_METHODS = ["GET", "POST"]
ALLOWED_HEADERS = ["Content-Type"]
# Lets the frontend read the wait time on a 429.
EXPOSED_HEADERS = ["Retry-After"]


def parse_origins(raw: str) -> list[str]:
    """Split ``ALLOWED_ORIGINS`` into exact origins.

    Entries that are not a bare ``scheme://host[:port]`` (a wildcard, a path, a
    trailing slash) are dropped with a warning that names the problem, never the value.
    """
    origins: list[str] = []
    for entry in raw.split(","):
        origin = entry.strip().lower()
        if not origin:
            continue
        if _ORIGIN_SHAPE.fullmatch(origin):
            origins.append(origin)
        else:
            logger.warning("cors_origin_dropped reason=not_an_exact_origin")
    return origins


def add_cors(app: FastAPI, allowed_origins: str) -> None:
    """Attach Starlette's CORS middleware with the Muwattin policy."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=parse_origins(allowed_origins),
        allow_origin_regex=PREVIEW_ORIGIN_REGEX,
        allow_methods=ALLOWED_METHODS,
        allow_headers=ALLOWED_HEADERS,
        expose_headers=EXPOSED_HEADERS,
        allow_credentials=False,
        max_age=600,
    )
