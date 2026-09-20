"""Tests for test-suite degradation (the RQ4 oracle-weakening manipulation)."""

import ast

from meta_real_eval.rq4.degradation import degrade, degrade_all_levels
from meta_real_eval.rq4.runner import task_stratum

SUITE = (
    "def check(candidate):\n"
    "    assert candidate(1, 2) == 3\n"
    "    assert candidate(-1, 1) == 0\n"
    "    assert candidate(0, 0) == 0\n"
    "    assert candidate(5, 5) == 10\n"
)


def _n_asserts(code: str) -> int:
    return sum(
        1
        for node in ast.walk(ast.parse(code))
        if isinstance(node, ast.Assert)
    )


def test_zero_degradation_is_identity():
    assert degrade(SUITE, 0.0) == SUITE


def test_removes_the_requested_fraction():
    assert _n_asserts(SUITE) == 4
    assert _n_asserts(degrade(SUITE, 0.5)) == 2
    assert _n_asserts(degrade(SUITE, 0.25)) == 3


def test_never_empties_the_suite():
    """A body with no statements is a SyntaxError; degrade() must keep it valid."""
    degraded = degrade(SUITE, 1.0)
    assert _n_asserts(degraded) == 0
    ast.parse(degraded)          # still parses
    assert "def check" in degraded


def test_is_deterministic_given_a_seed():
    assert degrade(SUITE, 0.5, seed=7) == degrade(SUITE, 0.5, seed=7)


def test_malformed_suite_is_returned_unchanged():
    broken = "def check(candidate:\n"
    assert degrade(broken, 0.5) == broken


def test_degrade_all_levels_keys_every_level():
    levels = [0.0, 0.2, 0.5, 0.8]
    out = degrade_all_levels(SUITE, levels)
    assert sorted(out) == levels
    # more degradation never leaves more assertions behind
    counts = [_n_asserts(out[lv]) for lv in levels]
    assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# Rounding. int() truncation made a positive removal fraction a no-op whenever
# n * fraction < 1 -- 34 of the 161 tasks with any assert, all at the 20% level.
# The weakest degradation step was then literally the intact suite, and RQ4's
# trend test was fed a duplicated point.
# ---------------------------------------------------------------------------

def test_a_small_suite_still_loses_an_assert_at_the_weakest_level():
    """4 asserts x 0.2 = 0.8, which int() floors to zero removals."""
    assert _n_asserts(SUITE) == 4
    degraded = degrade(SUITE, 0.2)
    assert _n_asserts(degraded) == 3, "20% of 4 asserts must remove one, not none"
    assert degraded != SUITE


def test_any_positive_fraction_removes_at_least_one():
    tiny = "def check(candidate):\n    assert candidate(1) == 1\n"
    assert _n_asserts(degrade(tiny, 0.01)) == 0


# ---------------------------------------------------------------------------
# Nesting. The levels must be cumulative for Page's L, which tests for a
# monotone trend across them: the 50% suite has to be missing everything the
# 20% suite was missing, plus more.
# ---------------------------------------------------------------------------

def _surviving_asserts(code: str) -> set[str]:
    return {
        ast.unparse(n) for n in ast.walk(ast.parse(code))
        if isinstance(n, ast.Assert)
    }


def test_degradation_levels_are_nested_subsets():
    big = "def check(candidate):\n" + "".join(
        f"    assert candidate({i}) == {i}\n" for i in range(10)
    )
    out = degrade_all_levels(big, [0.0, 0.2, 0.5, 0.8])
    survivors = [_surviving_asserts(out[lv]) for lv in (0.0, 0.2, 0.5, 0.8)]
    for weaker, stronger in zip(survivors, survivors[1:]):
        assert stronger < weaker, "each level must drop a superset of the last"


# ---------------------------------------------------------------------------
# Reach. Asserts nested inside a loop were invisible, so tasks whose whole
# suite sits in a `for` (HumanEval 32, 38, 50) had nothing degradable and
# contributed a flat line to a trend test about degradation.
# ---------------------------------------------------------------------------

NESTED_SUITE = (
    "def check(candidate):\n"
    "    for i in range(3):\n"
    "        assert candidate(i) == i\n"
    "        assert candidate(i + 1) == i + 1\n"
)


def test_asserts_inside_a_loop_are_degradable():
    assert _n_asserts(NESTED_SUITE) == 2
    assert _n_asserts(degrade(NESTED_SUITE, 0.5)) == 1


def test_emptying_a_loop_body_keeps_the_suite_parseable():
    """Removing every assert in a `for` body leaves a block needing `pass`."""
    degraded = degrade(NESTED_SUITE, 1.0)
    assert _n_asserts(degraded) == 0
    ast.parse(degraded)                      # would raise without the Pass fill
    assert "pass" in degraded


def test_a_suite_with_no_asserts_is_returned_unchanged():
    no_asserts = "def check(candidate):\n    candidate(1)\n"
    assert degrade(no_asserts, 0.8) == no_asserts


# ---------------------------------------------------------------------------
# Task strata. Both RQ4 manipulations are monotone (verified over the corpus:
# degradation never lowered a score in 1,476 observations, augmentation never
# raised one), which pins what each stratum can show. Classifying from the
# INTACT suite keeps this a pre-treatment covariate rather than the outcome.
# ---------------------------------------------------------------------------

def test_all_models_perfect_is_saturated():
    assert task_stratum({"a": 1.0, "b": 1.0, "c": 1.0}) == "saturated"


def test_all_models_zero_is_floor():
    assert task_stratum({"a": 0.0, "b": 0.0, "c": 0.0}) == "floor"


def test_any_difference_is_discriminating():
    assert task_stratum({"a": 1.0, "b": 1.0, "c": 0.9}) == "discriminating"


def test_all_tied_but_not_at_an_extreme_is_discriminating():
    """A mid tie still admits movement in both directions, unlike 1.0 or 0.0."""
    assert task_stratum({"a": 0.5, "b": 0.5, "c": 0.5}) == "discriminating"


def test_no_scores_is_unknown():
    assert task_stratum({}) == "unknown"
