"""D2 unit tests: the validity gate's pure classification logic."""

from __future__ import annotations

import pytest

from meta_real_eval.benchmarks.gate import (
    INVALID_ERROR,
    INVALID_NONDETERMINISTIC,
    INVALID_ORDER_DEPENDENT,
    INVALID_REFERENCE_MISMATCH,
    INVALID_TIMEOUT,
    VALID_BEHAVIOURAL,
    VALID_EXCEPTION_ORACLE,
    classify_test_validity,
    mark_trivial,
)
from meta_real_eval.benchmarks.outcomes import (
    ERROR,
    EXPECTED_EXCEPTION,
    ORDINARY_FAIL,
    ORDINARY_PASS,
    TIMEOUT,
    UNEXPECTED_PASS,
    TestOutcome,
)


def _outcome(outcome, exc_type=None, nodeid="t"):
    return TestOutcome(nodeid=nodeid, outcome=outcome, exc_type=exc_type)


def test_stable_ordinary_pass_becomes_valid_behavioural():
    runs = [_outcome(ORDINARY_PASS)] * 3
    g = classify_test_validity(runs, isolated_run=_outcome(ORDINARY_PASS))
    assert g.validity == VALID_BEHAVIOURAL
    assert g.is_valid


def test_stable_expected_exception_becomes_valid_exception_oracle():
    runs = [_outcome(EXPECTED_EXCEPTION, exc_type="builtins.KeyError")] * 3
    g = classify_test_validity(
        runs, isolated_run=_outcome(EXPECTED_EXCEPTION, exc_type="builtins.KeyError")
    )
    assert g.validity == VALID_EXCEPTION_ORACLE
    assert g.ref_exc_type == "builtins.KeyError"


def test_deterministic_ordinary_fail_is_reference_mismatch():
    runs = [_outcome(ORDINARY_FAIL, exc_type="builtins.AssertionError")] * 3
    g = classify_test_validity(runs, isolated_run=None)
    assert g.validity == INVALID_REFERENCE_MISMATCH
    assert not g.is_valid


def test_deterministic_unexpected_pass_is_reference_mismatch():
    runs = [_outcome(UNEXPECTED_PASS)] * 3
    g = classify_test_validity(runs, isolated_run=None)
    assert g.validity == INVALID_REFERENCE_MISMATCH


def test_flaky_outcome_across_runs_is_nondeterministic():
    runs = [_outcome(ORDINARY_PASS), _outcome(ORDINARY_FAIL), _outcome(ORDINARY_PASS)]
    g = classify_test_validity(runs, isolated_run=None)
    assert g.validity == INVALID_NONDETERMINISTIC


def test_flaky_exc_type_across_runs_is_nondeterministic():
    """Same D1 outcome every run, but a different exception type -- still not
    stable, since _stable_key is (outcome, exc_type)."""
    runs = [
        _outcome(EXPECTED_EXCEPTION, exc_type="builtins.KeyError"),
        _outcome(EXPECTED_EXCEPTION, exc_type="builtins.TypeError"),
        _outcome(EXPECTED_EXCEPTION, exc_type="builtins.KeyError"),
    ]
    g = classify_test_validity(runs, isolated_run=None)
    assert g.validity == INVALID_NONDETERMINISTIC


def test_any_timeout_in_full_suite_is_invalid_timeout():
    runs = [_outcome(ORDINARY_PASS), _outcome(TIMEOUT), _outcome(ORDINARY_PASS)]
    g = classify_test_validity(runs, isolated_run=None)
    assert g.validity == INVALID_TIMEOUT


def test_any_error_in_full_suite_is_invalid_error():
    runs = [_outcome(ORDINARY_PASS), _outcome(ORDINARY_PASS), _outcome(ERROR)]
    g = classify_test_validity(runs, isolated_run=None)
    assert g.validity == INVALID_ERROR


def test_isolated_run_disagreeing_is_order_dependent():
    """A test relying on class state set by an earlier test in the same
    suite: stable ordinary_pass across all 3 full-suite runs, but fails when
    run on its own."""
    runs = [_outcome(ORDINARY_PASS)] * 3
    g = classify_test_validity(runs, isolated_run=_outcome(ORDINARY_FAIL))
    assert g.validity == INVALID_ORDER_DEPENDENT


def test_isolated_run_missing_for_a_candidate_raises():
    runs = [_outcome(ORDINARY_PASS)] * 3
    with pytest.raises(ValueError):
        classify_test_validity(runs, isolated_run=None)


def test_wrong_number_of_full_suite_runs_raises():
    with pytest.raises(ValueError):
        classify_test_validity([_outcome(ORDINARY_PASS)] * 2, isolated_run=None)


def test_mismatched_nodeids_raises():
    runs = [_outcome(ORDINARY_PASS, nodeid="a"), _outcome(ORDINARY_PASS, nodeid="b"),
            _outcome(ORDINARY_PASS, nodeid="a")]
    with pytest.raises(ValueError):
        classify_test_validity(runs, isolated_run=None)


# ---------------------------------------------------------------------------
# mark_trivial
# ---------------------------------------------------------------------------

def test_trivial_behavioural_when_skeleton_also_passes():
    from meta_real_eval.benchmarks.gate import GatedTest
    gated = [GatedTest("t", VALID_BEHAVIOURAL)]
    skel = {"t": _outcome(ORDINARY_PASS)}
    out = mark_trivial(gated, skel)
    assert out[0].trivial


def test_not_trivial_behavioural_when_skeleton_fails():
    from meta_real_eval.benchmarks.gate import GatedTest
    gated = [GatedTest("t", VALID_BEHAVIOURAL)]
    skel = {"t": _outcome(ORDINARY_FAIL)}
    assert not mark_trivial(gated, skel)[0].trivial


def test_trivial_exception_oracle_requires_matching_exc_type():
    from meta_real_eval.benchmarks.gate import GatedTest
    gated = [GatedTest("t", VALID_EXCEPTION_ORACLE, ref_exc_type="builtins.KeyError")]
    same_type = {"t": _outcome(EXPECTED_EXCEPTION, exc_type="builtins.KeyError")}
    diff_type = {"t": _outcome(EXPECTED_EXCEPTION, exc_type="builtins.TypeError")}
    assert mark_trivial(gated, same_type)[0].trivial
    assert not mark_trivial(gated, diff_type)[0].trivial


def test_no_skeleton_outcome_means_not_trivial():
    from meta_real_eval.benchmarks.gate import GatedTest
    gated = [GatedTest("t", VALID_BEHAVIOURAL)]
    assert not mark_trivial(gated, {})[0].trivial


def test_invalid_test_is_never_marked_trivial():
    from meta_real_eval.benchmarks.gate import GatedTest
    gated = [GatedTest("t", INVALID_REFERENCE_MISMATCH)]
    skel = {"t": _outcome(ORDINARY_PASS)}
    assert not mark_trivial(gated, skel)[0].trivial
