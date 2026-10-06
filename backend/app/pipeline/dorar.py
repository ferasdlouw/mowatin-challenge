"""Hadith references from the Dorar encyclopedia (dorar.net), for the reviewer only (D-067).

Dorar's «خلاصة حكم المحدث» is each scholar's own wording and often differs between results
for one hadith, so it is never turned into a verdict here: a quote not in the approved lists
stays unsourced (``output: null`` + review), and the matching Dorar entries are attached as
references with the grade text exactly as Dorar gives it.

Only the quoted saying is sent, never the rest of the user's text; logs carry its length and
keyed hash prefix only.
"""

from __future__ import annotations

import html
import json
import logging
import re
from collections import OrderedDict
from dataclasses import dataclass

import httpx

from app.pipeline.hadith import match_key
from app.schemas import SourceRef
from app.security.privacy import fingerprint

logger = logging.getLogger("app.pipeline.dorar")

API_URL = "https://dorar.net/dorar_api.json"
EDITION = "dorar.net"
# Says who is asking: some sites refuse the library's default agent string.
USER_AGENT = "Mowatin/1.0 (+https://mowatin.pages.dev)"
TIMEOUT_S = 3.0
MAX_REFERENCES = 5
# A quote shorter than this many words matches too many sayings to be a useful reference.
MIN_QUOTE_WORDS = 3
CACHE_SIZE = 500
MAX_FIELD_CHARS = 200

_ENTRY_RE = re.compile(
    r'<div class="hadith"[^>]*>(?P<text>.*?)</div>\s*<div class="hadith-info">(?P<info>.*?)</div>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_NUMBER_RE = re.compile(r"^\s*\d+\s*-\s*")
_DOTS_RE = re.compile(r"[\s.]+$")
_LABELS = {
    "rawi": "الراوي",
    "muhaddith": "المحدث",
    "book": "المصدر",
    "number": "الصفحة أو الرقم",
    "grade": "خلاصة حكم المحدث",
}


@dataclass(frozen=True)
class DorarEntry:
    """One search result: the saying as Dorar shows it and the scholar's grading."""

    text: str
    rawi: str
    muhaddith: str
    book: str
    number: str
    grade: str

    def as_source(self) -> SourceRef:
        ref = " ".join(part for part in (self.book, self.number) if part)
        if self.muhaddith:
            ref = f"{ref} ({self.muhaddith})" if ref else self.muhaddith
        grade = f"{self.muhaddith}: {self.grade}" if self.muhaddith and self.grade else self.grade
        return SourceRef(kind="hadith", ref=ref, grade=grade or None, edition=EDITION)


def _plain(fragment: str) -> str:
    """Tags removed, entities decoded, spaces collapsed, length bounded."""
    text = " ".join(html.unescape(_TAG_RE.sub(" ", fragment)).split())
    return text[:MAX_FIELD_CHARS]


def _field(info: str, label: str) -> str:
    """The value after ``<span class="info-subtitle">label:</span>``, up to the next label."""
    pattern = rf'<span class="info-subtitle">{re.escape(label)}:</span>(.*?)(?=<span class="info-subtitle">|$)'
    found = re.search(pattern, info, re.DOTALL)
    return _plain(found.group(1)) if found else ""


def parse(payload: object) -> list[DorarEntry]:
    """Entries of a ``dorar_api.json`` answer; anything malformed gives no entry."""
    result = payload.get("ahadith", {}) if isinstance(payload, dict) else {}
    body = result.get("result") if isinstance(result, dict) else None
    if not isinstance(body, str):
        return []
    entries = []
    for match in _ENTRY_RE.finditer(body):
        text = _DOTS_RE.sub("", _NUMBER_RE.sub("", _plain(match.group("text"))))
        fields = {name: _field(match.group("info"), label) for name, label in _LABELS.items()}
        if text:
            entries.append(DorarEntry(text=text, **fields))
    return entries


def matching(quote: str, entries: list[DorarEntry]) -> list[DorarEntry]:
    """Entries whose saying is the quote, or holds it, or is held by it (Dorar often cuts a
    long saying short with «. . .»); at most ``MAX_REFERENCES``, in Dorar's order."""
    key = match_key(quote)
    if len(key.split()) < MIN_QUOTE_WORDS:
        return []
    found = []
    for entry in entries:
        entry_key = match_key(entry.text)
        if entry_key and (entry_key in key or key in entry_key):
            found.append(entry)
    return found[:MAX_REFERENCES]


class DorarLookup:
    """Asks Dorar once per distinct quote (small in-memory cache) and never raises."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http
        self._cache: OrderedDict[str, list[DorarEntry]] = OrderedDict()

    async def references(self, quote: str, timeout_s: float = TIMEOUT_S) -> list[SourceRef]:
        """Dorar references for one quoted saying; ``[]`` on any failure or no match."""
        key = match_key(quote)
        if len(key.split()) < MIN_QUOTE_WORDS or timeout_s <= 0:
            return []
        if key not in self._cache:
            entries = await self._search(quote, min(timeout_s, TIMEOUT_S))
            if entries is None:
                return []
            self._cache[key] = matching(quote, entries)
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        self._cache.move_to_end(key)
        return [entry.as_source() for entry in self._cache[key]]

    async def _search(self, quote: str, timeout_s: float) -> list[DorarEntry] | None:
        record: dict[str, object] = {"event": "hadith_lookup", "outcome": "ok"}
        try:
            response = await self._http.get(
                API_URL,
                params={"skey": quote},
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=timeout_s,
            )
            record["status"] = response.status_code
            response.raise_for_status()
            return parse(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            record["outcome"] = type(exc).__name__
            return None
        finally:
            logger.info(json.dumps({**record, **fingerprint(quote)}, sort_keys=True))
