"""HTTP hardening: CORS, rate limit, body cap, security headers, privacy-safe logging."""

from __future__ import annotations

from fastapi import FastAPI

from app.config import Settings
from app.errors import UnhandledErrorMiddleware
from app.security.body_limit import BodySizeLimitMiddleware, max_body_bytes
from app.security.cors import add_cors
from app.security.headers import SecurityHeadersMiddleware
from app.security.rate_limit import (
    SUBNET_LIMIT_FACTOR,
    RateLimitMiddleware,
    SlidingWindowLimiter,
)
from app.security.request_log import RequestLogMiddleware

__all__ = ["install_security"]


def install_security(app: FastAPI, settings: Settings) -> None:
    """Add the middleware stack. Starlette runs the last-added middleware first.

    Order, outermost first: request log → security headers → CORS → unhandled-error
    guard → rate limit → body cap. CORS sits outside the limiter and the error guard so a
    429 or 500 still carries ``Access-Control-Allow-Origin`` and the browser shows the
    matching message instead of a network error.
    """
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=max_body_bytes(settings.max_text_chars),
        max_text_chars=settings.max_text_chars,
    )
    app.add_middleware(
        RateLimitMiddleware,
        limiter=SlidingWindowLimiter(limit=settings.rate_limit_per_min, window_s=60.0),
        trusted_proxy_hops=settings.trusted_proxy_hops,
        subnet_limiter=SlidingWindowLimiter(
            limit=settings.rate_limit_per_min * SUBNET_LIMIT_FACTOR, window_s=60.0
        ),
    )
    app.add_middleware(UnhandledErrorMiddleware)
    add_cors(app, settings.allowed_origins)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLogMiddleware)
