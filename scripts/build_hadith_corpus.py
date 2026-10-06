#!/usr/bin/env python3
"""Builds data/hadith/corpus_bukhari_muslim.json.gz from the reference file of PR #81.

The input is the test-case JSONL `data/testset/testset_bukhari_muslim_all.jsonl` of branch
`data/testset-bukhari-muslim` (read it with `git show`; it is not on main). Each record keeps
its collection, its record id inside that file (NOT a printed takhrij number), its text exactly
as given (isnad included: the matn start is not delimited reliably, see D-077) and its
`match_key` form, so the server does not canonicalize 14k texts at start-up. Output is
deterministic: records ordered bukhari then muslim then record id, gzip with mtime 0.

Usage:
  git show origin/data/testset-bukhari-muslim:data/testset/testset_bukhari_muslim_all.jsonl > /tmp/bm.jsonl
  python3 scripts/build_hadith_corpus.py /tmp/bm.jsonl
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "hadith" / "corpus_bukhari_muslim.json.gz"
COLLECTIONS = {"bukhari": "صحيح البخاري", "muslim": "صحيح مسلم"}


def _match_key():
    """The server's own matching form, so the stored keys equal what it computes (D-036)."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.pipeline.hadith import match_key

    return match_key


def _record(row: dict, match_key) -> dict:
    (ref,) = row["expect"]["hadith_refs"]
    collection, kind, number = ref.split(":")
    if collection not in COLLECTIONS or kind != "record":
        raise ValueError(f"{row['id']}: unexpected hadith_ref {ref!r}")
    return {"c": collection, "r": int(number), "t": row["text_ar"], "k": match_key(row["text_ar"])}


def build(source: Path) -> dict:
    raw = source.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    order = list(COLLECTIONS)
    key_of = _match_key()
    items = sorted((_record(row, key_of) for row in rows), key=lambda item: (order.index(item["c"]), item["r"]))
    return {
        "status": "draft",
        "description": "Derived corpus for partial-hadith completion suggestions (D-077). "
        "Needs content-owner review; origin and licence of the reference file are unknown.",
        "derived_from": {
            "file": "data/testset/testset_bukhari_muslim_all.jsonl (PR #81)",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(rows),
        },
        "record_id_note": "r is the record id inside the reference file, not a printed takhrij number",
        "grade": None,
        "collections": COLLECTIONS,
        "items": items,
    }


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    data = build(Path(sys.argv[1]))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with OUTPUT.open("wb") as handle, gzip.GzipFile(
        filename="", mode="wb", fileobj=handle, mtime=0, compresslevel=9
    ) as gz:
        gz.write(payload)
    print(f"{len(data['items'])} records -> {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
