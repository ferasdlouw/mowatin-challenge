import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.pipeline.normalize import fold_persian, normalize_text, tokenize


class GlossaryIndex:
    def __init__(self):
        self.glossary_terms: list[tuple[tuple[str, ...], str]] = []
        # Full entries by id (first file wins on a duplicate id), for search and /health.
        self.entries: dict[str, dict[str, Any]] = {}
        self._load_data()

    def _load_data(self):
        base_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "glossary"

        for file_path in sorted(base_dir.glob("*.json")):
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    term_id = item["id"]
                    self.entries.setdefault(term_id, item)
                    phrases = [item["ar"], *item.get("variants_ar", [])]
                    for phrase in phrases:
                        norm_phrase = normalize_text(phrase)
                        phrase_tokens = tuple(w for w in norm_phrase.split() if w)
                        if phrase_tokens:
                            self.glossary_terms.append((phrase_tokens, term_id))

        # Longest match wins
        self.glossary_terms.sort(key=lambda x: len(x[0]), reverse=True)

    def detect(self, text: str) -> list[dict[str, Any]]:
        # Spans stay valid: the fold replaces one character with one.
        tokens = tokenize(fold_persian(text))
        matches = []

        i = 0
        while i < len(tokens):
            matched = False
            for phrase_tokens, term_id in self.glossary_terms:
                phrase_len = len(phrase_tokens)
                if i + phrase_len > len(tokens):
                    continue

                match_found = True
                for j in range(phrase_len):
                    text_token = tokens[i + j]

                    variant_matched = False
                    for var in text_token["variants"]:
                        if var["text"] == phrase_tokens[j]:
                            variant_matched = True
                            break

                    if not variant_matched:
                        match_found = False
                        break

                if match_found:
                    start_orig = tokens[i]["start_orig"]
                    end_orig = tokens[i + phrase_len - 1]["end_orig"]
                    matches.append({"id": term_id, "start": start_orig, "end": end_orig})
                    i += phrase_len
                    matched = True
                    break

            if not matched:
                i += 1

        return matches


@lru_cache(maxsize=1)
def get_index() -> GlossaryIndex:
    """The glossary, loaded once per process."""
    return GlossaryIndex()


def detect(text: str) -> list[dict[str, Any]]:
    return get_index().detect(text)
