"""Request body cap, enforced before the body is parsed."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import text_too_long_response

# Worst case a character is sent as a 6-byte JSON escape (\uXXXX); the slack
# covers the other request fields and the JSON punctuation.
BYTES_PER_CHAR = 6
ENVELOPE_BYTES = 1024


def max_body_bytes(max_text_chars: int) -> int:
    """Largest body a valid ``/v1/translate`` request can need."""
    return max_text_chars * BYTES_PER_CHAR + ENVELOPE_BYTES


class BodySizeLimitMiddleware:
    """413 when ``Content-Length`` or a chunked body exceeds ``max_bytes``.

    The server already holds a body to its declared ``Content-Length``, so a declared
    length is checked up front. A chunked body has no length: it is read up to the cap
    here and replayed, because FastAPI turns any error raised while it reads the body
    into a 400.
    """

    def __init__(self, app: ASGIApp, max_bytes: int, max_text_chars: int) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.max_text_chars = max_text_chars

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = _declared_length(scope)
        if declared is not None:
            if declared > self.max_bytes:
                await text_too_long_response(self.max_text_chars)(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        body = await self._read_capped(receive)
        if body is None:
            await text_too_long_response(self.max_text_chars)(scope, receive, send)
            return
        await self.app(scope, _replay(body, receive), send)

    async def _read_capped(self, receive: Receive) -> bytes | None:
        """The whole body, or ``None`` as soon as it passes the cap."""
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return b"".join(chunks)
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                return None
            chunks.append(chunk)
            if not message.get("more_body", False):
                return b"".join(chunks)


def _declared_length(scope: Scope) -> int | None:
    for key, value in scope.get("headers", []):
        if key == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


def _replay(body: bytes, receive: Receive) -> Receive:
    """A ``receive`` that yields the buffered body once, then defers to the real one."""
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay
