"""Log-safe stand-ins for user text."""

from __future__ import annotations

import hashlib
import hmac
import secrets

HASH_PREFIX_CHARS = 12
# A fresh random key per process, never stored or logged (NEW-6): a plain SHA-256 prefix
# let anyone with log access confirm a guessed short text («ما حكم صلاتي؟») by hashing it.
# Prefixes still match within one process, which is all request correlation needs.
_DIGEST_KEY = secrets.token_bytes(32)


def keyed_digest(text: str) -> str:
    """HMAC-SHA-256 prefix of ``text`` under the process key."""
    mac = hmac.new(_DIGEST_KEY, text.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()[:HASH_PREFIX_CHARS]


def fingerprint(text: str) -> dict[str, int | str]:
    """Length and a keyed hash prefix: enough to correlate requests, never the text itself."""
    return {"chars": len(text), "sha256": keyed_digest(text)}
