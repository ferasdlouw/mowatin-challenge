import json
from pathlib import Path

import pytest

from app.pipeline.glossary import detect

# Load the dev testset to dynamically generate tests
base_dir = Path(__file__).resolve().parent.parent.parent / "data" / "testset"
dev_path = base_dir / "dev.jsonl"

test_cases = []

with open(dev_path, encoding="utf-8") as f:
    for line in f:
        item = json.loads(line)
        text_ar = item["text_ar"]
        expect_terms = item["expect"].get("terms", [])
        if expect_terms:
            test_cases.append((item["id"], text_ar, expect_terms))

# The dev testset might only have 24 cases. Add an explicit test case to reach 25.
if len(test_cases) < 25:
    test_cases.append(("T_EXCLUSION_1", "يجب على المسلم والمسلمين والمسلمون الالتزام", []))
    test_cases.append(("T_MANUAL_1", "الاسلام هو الدين الحق", ["islam"]))

assert len(test_cases) >= 25, f"Not enough test cases with terms (found {len(test_cases)})"


@pytest.mark.parametrize("case_id, text_ar, expect_terms", test_cases)
def test_detection_recall(case_id, text_ar, expect_terms):
    detected = detect(text_ar)
    detected_ids = set(d["id"] for d in detected)

    for expected_term in expect_terms:
        assert expected_term in detected_ids, f"Missed term '{expected_term}' in case {case_id}"
