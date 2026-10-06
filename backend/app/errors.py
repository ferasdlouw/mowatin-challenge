"""Exception handlers — maps errors to contract-shaped HTTP responses.

All user-facing messages are in Arabic. Stack traces and provider
details are never leaked to the client, and user text never reaches the logs.
"""

from __future__ import annotations

import json
import logging
import traceback
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Load Arabic flag messages once at module level
_FLAGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "messages" / "flags.ar.json"
_FLAGS: dict[str, str] = {}
if _FLAGS_PATH.exists():
    _FLAGS = json.loads(_FLAGS_PATH.read_text(encoding="utf-8")).get("messages", {})

_HTTP_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}


class TextTooLongError(Exception):
    """The request text exceeds ``MAX_TEXT_CHARS``."""

    def __init__(self, max_chars: int) -> None:
        super().__init__("text exceeds MAX_TEXT_CHARS")
        self.max_chars = max_chars


def _arabic(key: str, **kwargs: Any) -> str:
    """Get an Arabic message by key, filling placeholders."""
    tpl = _FLAGS.get(key, "حدث خطأ أثناء المعالجة — يُرجى المحاولة لاحقًا")
    try:
        return tpl.format(**kwargs)
    except (KeyError, IndexError):
        return tpl


def _error_json(
    status: int, code: str, msg: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": True, "message": msg, "code": code},
        headers=headers,
    )


def text_too_long_response(max_chars: int) -> JSONResponse:
    """413 reply, shared by the body-size middleware and the handlers below."""
    return _error_json(413, "TEXT_TOO_LONG", _arabic("text_too_long", max_chars=max_chars))


def rate_limited_response(retry_after: int) -> JSONResponse:
    """429 reply with ``Retry-After`` in whole seconds."""
    return _error_json(
        429,
        "RATE_LIMITED",
        _arabic("rate_limited", retry_after=retry_after),
        headers={"Retry-After": str(retry_after)},
    )


def _max_chars(request: Request) -> int:
    return int(request.app.state.settings.max_text_chars)


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic / FastAPI validation errors → 400 or 413.

    ``exc.errors()`` holds the rejected input, so it is inspected but never logged.
    """
    if any(_text_too_long(error) for error in exc.errors()):
        return text_too_long_response(_max_chars(request))
    return _error_json(400, "VALIDATION_ERROR", _arabic("validation_error"))


def _text_too_long(error: dict[str, Any]) -> bool:
    """Only the translation text over its cap is 413 «text too long» (D-062). Any other field
    over its own cap (``q`` of ``/v1/glossary``, 200 chars) is a plain 400: the 413 message
    names ``MAX_TEXT_CHARS``, which says nothing about that field."""
    return error.get("type") == "string_too_long" and tuple(error.get("loc", ())) == (
        "body",
        "text",
    )


async def _text_too_long_handler(_request: Request, exc: TextTooLongError) -> JSONResponse:
    return text_too_long_response(exc.max_chars)


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Keep the status code of client errors; hide the detail of everything."""
    if exc.status_code == 429:
        return rate_limited_response(60)
    if exc.status_code == 413:
        return text_too_long_response(_max_chars(request))
    if 400 <= exc.status_code < 500:
        code = _HTTP_CODES.get(exc.status_code, "BAD_REQUEST")
        return _error_json(
            exc.status_code, code, _arabic("general_error"), dict(exc.headers or {})
        )
    return _error_json(500, "INTERNAL_ERROR", _arabic("general_error"))


class UnhandledErrorMiddleware:
    """Turn any uncaught exception into a generic 500 without logging its message.

    Starlette's own server-error handler re-raises after replying, and uvicorn then
    prints the exception message, which may quote user text. This middleware stops
    the exception here and logs only its type and stack frames.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            frames = "".join(traceback.format_tb(exc.__traceback__))
            logger.error("unhandled_exception type=%s\n%s", type(exc).__name__, frames)
            if not response_started:
                reply = _error_json(500, "INTERNAL_ERROR", _arabic("general_error"))
                await reply(scope, receive, send)


def register_error_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the app."""
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(TextTooLongError, _text_too_long_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
