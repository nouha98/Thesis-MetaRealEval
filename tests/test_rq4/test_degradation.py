"""Tests for test-suite degradation (the RQ4 oracle-weakening manipulation)."""

import ast

from meta_real_eval.rq4.degradation import degrade, degrade_all_levels

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
