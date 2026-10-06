"""Partial-hadith completion from the derived Bukhari/Muslim corpus (D-077).

A quote that is a contiguous run of whole words of a corpus record gets a completion
SUGGESTION: the record's own words that follow the quote, verbatim from the file and capped.
It is never substituted for the user's text and never produced by an LLM. When the matching
records continue differently, no completion is offered at all (the Quran lesson, D-076):
the candidates are listed and the segment goes to review.

The corpus carries no grade, and its record ids are ids inside the reference file, not
printed takhrij numbers; both facts are stated in every source this module returns.
"""

from __future__ import annotations

import gzip
import json
import logging
from array import array
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

# The module, not its names: hadith.py imports this module to resolve quotes.
from app.pipeline import hadith
from app.pipeline.report import load_messages
from app.schemas import SourceRef

logger = logging.getLogger("app.pipeline.hadith_corpus")

CORPUS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "hadith" / "corpus_bukhari_muslim.json.gz"
)
COLLECTION_ORDER = ("bukhari", "muslim")
MIN_TOKENS = 4
MIN_CONTENT_TOKENS = 3
MAX_COMPLETION_WORDS = 40
MAX_LISTED_SOURCES = 5
# Past this many matching records a quote is too generic to complete; it is listed as
# ambiguous without reading each continuation, which keeps a request's work bounded.
MAX_COMPARED_RECORDS = 50
# Attribution and transmission formulas: a quote made mostly of these says nothing about
# which hadith is meant («قال رسول الله صلى الله عليه وسلم» is in thousands of records).
_FORMULAS = (
    "قال رسول الله صلى عليه وسلم النبي حدثنا حدثني أخبرنا أخبرني عن أن سمعت يقول "
    "قالت ابن بن أبي رضي عنه عنها"
)


@lru_cache(maxsize=1)
def _formula_words() -> frozenset[str]:
    return frozenset(hadith.match_key(_FORMULAS).split())


@dataclass(frozen=True)
class Record:
    collection: str
    record_id: int
    text: str
    key: str


@dataclass(frozen=True)
class Corpus:
    records: tuple[Record, ...]
    collections: dict[str, str]
    postings: dict[str, array]


@dataclass(frozen=True)
class Completion:
    """The outcome for one quote: ``text`` is None when the candidates disagree."""

    text: str | None
    sources: tuple[Record, ...]


def _index(records: tuple[Record, ...]) -> dict[str, array]:
    """Token → ids of the records holding it; a quote's rarest token picks the candidates."""
    postings: dict[str, array] = {}
    for position, record in enumerate(records):
        for token in set(record.key.split()):
            postings.setdefault(token, array("I")).append(position)
    return postings


@lru_cache(maxsize=1)
def load_corpus() -> Corpus | None:
    """The corpus, read and indexed once on first use; absent file → no corpus."""
    if not CORPUS_PATH.exists():
        return None
    data: dict[str, Any] = json.loads(gzip.decompress(CORPUS_PATH.read_bytes()).decode("utf-8"))
    records = tuple(
        Record(item["c"], int(item["r"]), item["t"], item["k"]) for item in data.get("items", [])
    )
    logger.info(json.dumps({"event": "hadith_corpus_loaded", "records": len(records)}))
    return Corpus(records, dict(data.get("collections", {})), _index(records))


def is_specific(quote_key: str) -> bool:
    """At least ``MIN_TOKENS`` words, ``MIN_CONTENT_TOKENS`` of them outside the formulas."""
    tokens = quote_key.split()
    content = [token for token in tokens if token not in _formula_words()]
    return len(tokens) >= MIN_TOKENS and len(content) >= MIN_CONTENT_TOKENS


def _candidates(corpus: Corpus, quote_key: str) -> list[Record]:
    """Records whose key holds the quote as a contiguous run of whole tokens."""
    tokens = quote_key.split()
    lists = [corpus.postings.get(token) for token in tokens]
    if any(found is None for found in lists):
        return []
    rarest = min(lists, key=len)
    padded = f" {quote_key} "
    hits = [corpus.records[i] for i in rarest if padded in f" {corpus.records[i].key} "]
    order = {name: rank for rank, name in enumerate(COLLECTION_ORDER)}
    return sorted(hits, key=lambda r: (order.get(r.collection, len(order)), r.record_id))


def _continuation(record: Record, quote_key: str) -> tuple[str, str]:
    """The record's own words after the first occurrence of the quote (verbatim, capped),
    with their matching key for grouping. Words are the file's whitespace-split words."""
    quote_tokens = quote_key.split()
    words = record.text.split()
    token_end: list[int] = []  # for each canonical token, the index of the word it came from
    for index, word in enumerate(words):
        token_end += [index] * len(hadith.match_key(word).split())
    tokens = record.key.split()
    for start in range(len(tokens) - len(quote_tokens) + 1):
        if tokens[start : start + len(quote_tokens)] == quote_tokens:
            after = words[token_end[start + len(quote_tokens) - 1] + 1 :]
            shown = " ".join(after[:MAX_COMPLETION_WORDS])
            if len(after) > MAX_COMPLETION_WORDS:
                shown += " …"
            return shown, hadith.match_key(" ".join(after[:MAX_COMPLETION_WORDS]))
    return "", ""


def complete(quote_key: str) -> Completion | None:
    """Completion for a quote already known to be neither fabricated nor approved.

    None: no corpus, a quote too short or made of formulas, or no record holds it.
    """
    corpus = load_corpus()
    if corpus is None or not is_specific(quote_key):
        return None
    candidates = _candidates(corpus, quote_key)
    if not candidates:
        return None
    if len(candidates) > MAX_COMPARED_RECORDS:
        return Completion(text=None, sources=tuple(candidates))
    groups: dict[str, str] = {}
    for record in candidates:
        shown, key = _continuation(record, quote_key)
        groups.setdefault(key, shown)
    text = next(iter(groups.values())) if len(groups) == 1 else None
    return Completion(text=text, sources=tuple(candidates))


def source_ref(record: Record) -> SourceRef:
    """Collection in Arabic plus the record id, labelled as not a takhrij number; no grade."""
    collection = load_corpus().collections.get(record.collection, record.collection)
    ref = load_messages()["hadith_corpus_record"]
    ref = ref.replace("{collection}", collection).replace("{record}", str(record.record_id))
    return SourceRef(kind="hadith", ref=ref, grade=None)


def refs_text(sources: tuple[Record, ...]) -> str:
    """Up to ``MAX_LISTED_SOURCES`` refs, then «+N» for the rest."""
    shown = "، ".join(source_ref(r).ref for r in sources[:MAX_LISTED_SOURCES])
    extra = len(sources) - MAX_LISTED_SOURCES
    return f"{shown}، +{extra}" if extra > 0 else shown
