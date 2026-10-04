"""Security response headers."""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

NO_STORE_PATHS = frozenset({"/v1/translate"})
# Swagger UI and ReDoc load scripts from a CDN; they exist only when ENV != production.
DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    # Phase SEC (F10): the API serves JSON only, so nothing may load, run or frame it.
    "Strict-Transport-Security": "max-age=31536000",
    "X-Frame-Options": "DENY",
    # Checked only for no-cors loads; the frontend's CORS fetch is governed by CORS.
    "Cross-Origin-Resource-Policy": "same-site",
}
API_CSP = "default-src 'none'; frame-ancestors 'none'"


class SecurityHeadersMiddleware:
    """Add hardening headers to every response, and ``no-store`` on translate.

    Translate responses echo the user's text, so no browser or proxy cache may keep them,
    including error replies.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        no_store = scope["path"] in NO_STORE_PATHS
        csp = scope["path"] not in DOCS_PATHS

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in BASE_HEADERS.items():
                    headers[name] = value
                if csp:
                    headers["Content-Security-Policy"] = API_CSP
                if no_store:
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)
