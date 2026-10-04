"""One access-log line per request without the query string or client address.

Replaces uvicorn's access log (disabled in render.yaml), which prints the query
string, and ``/v1/glossary?q=...`` carries what the user typed.
"""

from __future__ import annotations

import json
import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.access")


class RequestLogMiddleware:
    """Log method, path, status and latency as one JSON line."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def capture_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            entry = {
                "event": "http_request",
                "method": scope["method"],
                "path": scope["path"],
                "status": status,
                "latency_ms": round((time.perf_counter() - started) * 1000),
            }
            logger.info(json.dumps(entry))
