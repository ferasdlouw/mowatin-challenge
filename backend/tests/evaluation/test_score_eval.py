"""Audit item 18: inter-rater agreement (Cohen's kappa) in scripts/score_eval.py."""

from __future__ import annotations

import pytest
import score_eval


def test_identical_ratings_agree_fully():
    assert score_eval.kappa(["OK", "E1", "OK"], ["OK", "E1", "OK"]) == (1.0, 1.0)


def test_known_value():
    # po = 3/4; rater 1: OK 2, E1 2; rater 2: OK 1, E1 3 -> pe = (2*1 + 2*3) / 16 = 0.5;
    # kappa = (0.75 - 0.5) / (1 - 0.5)
    po, k = score_eval.kappa(["OK", "OK", "E1", "E1"], ["OK", "E1", "E1", "E1"])
    assert (po, k) == (0.75, 0.5)


def test_no_ratings_is_a_clear_error_not_a_division_by_zero():
    with pytest.raises(ValueError, match="no ratings"):
        score_eval.kappa([], [])


def test_unequal_lists_are_refused_not_silently_truncated():
    with pytest.raises(ValueError, match="2 and 1"):
        score_eval.kappa(["OK", "E1"], ["OK"])
