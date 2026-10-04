"""D3 unit tests: the scoring policies, on hand-built outcomes."""

from __future__ import annotations

import pytest

from meta_real_eval.benchmarks.gate import GatedTest, VALID_BEHAVIOURAL, VALID_EXCEPTION_ORACLE
from meta_real_eval.benchmarks.outcomes import (
    EXPECTED_EXCEPTION,
    ORDINARY_FAIL,
    ORDINARY_PASS,
    TestOutcome,
)
from meta_real_eval.benchmarks.scoring import score_completion


def _oc(outcome, exc_type=None):
    return TestOutcome(nodeid="_", outcome=outcome, exc_type=exc_type)


def test_all_pass_scores_one_everywhere():
    valid = [GatedTest("a", VALID_BEHAVIOURAL), GatedTest("b", VALID_BEHAVIOURAL)]
    results = {"a": _oc(ORDINARY_PASS), "b": _oc(ORDINARY_PASS)}
    s = score_completion(valid, results)
    assert s.pass_rate == 1.0
    assert s.behavioural_pass_rate == 1.0
    assert s.nontrivial_pass_rate == 1.0
    assert s.pytest_native_pass_rate == 1.0
    assert s.passed_all
    assert s.n_valid == 2


def test_partial_behavioural_pass_rate():
    valid = [GatedTest("a", VALID_BEHAVIOURAL), GatedTest("b", VALID_BEHAVIOURAL)]
    results = {"a": _oc(ORDINARY_PASS), "b": _oc(ORDINARY_FAIL)}
    s = score_completion(valid, results)
    assert s.pass_rate == 0.5
    assert not s.passed_all


def test_exception_oracle_requires_matching_type_for_primary():
    valid = [GatedTest("a", VALID_EXCEPTION_ORACLE, ref_exc_type="builtins.KeyError")]
    wrong_type = {"a": _oc(EXPECTED_EXCEPTION, exc_type="builtins.TypeError")}
    right_type = {"a": _oc(EXPECTED_EXCEPTION, exc_type="builtins.KeyError")}
    assert score_completion(valid, wrong_type).pass_rate == 0.0
    assert score_completion(valid, right_type).pass_rate == 1.0


def test_pytest_native_gives_credit_for_any_exception():
    """The diagnostic native metric must NOT require type matching -- this is
    exactly the gap the primary metric exists to close (a completion that
    raises the wrong exception gets no primary credit but does get native
    credit)."""
    valid = [GatedTest("a", VALID_EXCEPTION_ORACLE, ref_exc_type="builtins.KeyError")]
    wrong_type = {"a": _oc(EXPECTED_EXCEPTION, exc_type="builtins.TypeError")}
    s = score_completion(valid, wrong_type)
    assert s.pass_rate == 0.0
    assert s.pytest_native_pass_rate == 1.0


def test_behavioural_pass_rate_excludes_exception_oracle_tests():
    valid = [
        GatedTest("a", VALID_BEHAVIOURAL),
        GatedTest("b", VALID_EXCEPTION_ORACLE, ref_exc_type="builtins.KeyError"),
    ]
    results = {"a": _oc(ORDINARY_PASS), "b": _oc(ORDINARY_FAIL)}
    s = score_completion(valid, results)
    assert s.behavioural_pass_rate == 1.0          # only "a" counts
    assert s.pass_rate == 0.5                       # both count


def test_behavioural_pass_rate_none_when_no_behavioural_tests():
    valid = [GatedTest("a", VALID_EXCEPTION_ORACLE, ref_exc_type="builtins.KeyError")]
    results = {"a": _oc(EXPECTED_EXCEPTION, exc_type="builtins.KeyError")}
    assert score_completion(valid, results).behavioural_pass_rate is None


def test_nontrivial_pass_rate_excludes_trivial_tests():
    valid = [
        GatedTest("a", VALID_BEHAVIOURAL, trivial=True),
        GatedTest("b", VALID_BEHAVIOURAL, trivial=False),
    ]
    results = {"a": _oc(ORDINARY_FAIL), "b": _oc(ORDINARY_FAIL)}
    s = score_completion(valid, results)
    assert s.pass_rate == 0.0          # trivial test still counts in the primary metric
    assert s.nontrivial_pass_rate == 0.0
    valid[1] = GatedTest("b", VALID_BEHAVIOURAL, trivial=False)
    results["b"] = _oc(ORDINARY_PASS)
    s2 = score_completion(valid, results)
    assert s2.nontrivial_pass_rate == 1.0   # only "b" (nontrivial) counts
    assert s2.pass_rate == 0.5


def test_nontrivial_pass_rate_none_when_all_trivial():
    valid = [GatedTest("a", VALID_BEHAVIOURAL, trivial=True)]
    results = {"a": _oc(ORDINARY_PASS)}
    assert score_completion(valid, results).nontrivial_pass_rate is None


def test_empty_valid_tests_raises():
    with pytest.raises(ValueError):
        score_completion([], {})


def test_missing_result_for_a_valid_test_raises():
    valid = [GatedTest("a", VALID_BEHAVIOURAL)]
    with pytest.raises(KeyError):
        score_completion(valid, {})


def test_invalid_gated_test_raises():
    from meta_real_eval.benchmarks.gate import INVALID_REFERENCE_MISMATCH
    valid = [GatedTest("a", INVALID_REFERENCE_MISMATCH)]
    with pytest.raises(ValueError):
        score_completion(valid, {"a": _oc(ORDINARY_PASS)})


# ---------------------------------------------------------------------------
# RQ4 reuse identity (plan review #15 / #17): scoring a *subset* of
# valid_tests with the same results must equal recomputing from stored
# per-test outcomes -- this is the property the RQ4 degradation shortcut
# depends on. Full execution-level identity (against a real degraded pytest
# run) is checked in the M1/M6 pilot per the plan; this is the algebraic half
# of that guarantee.
# ---------------------------------------------------------------------------

def test_subset_scoring_matches_full_results_restricted_to_subset():
    valid = [
        GatedTest("a", VALID_BEHAVIOURAL),
        GatedTest("b", VALID_BEHAVIOURAL),
        GatedTest("c", VALID_EXCEPTION_ORACLE, ref_exc_type="builtins.KeyError"),
    ]
    results = {
        "a": _oc(ORDINARY_PASS),
        "b": _oc(ORDINARY_FAIL),
        "c": _oc(EXPECTED_EXCEPTION, exc_type="builtins.KeyError"),
    }
    full = score_completion(valid, results)
    subset = score_completion(valid[:2], results)  # degrade away test "c"
    assert full.pass_rate == 2 / 3
    assert subset.pass_rate == 1 / 2
    # The subset score depends only on the tests kept -- recomputing it from
    # the SAME stored `results` dict (no re-execution) is what "reuse" means.
    assert subset.n_valid == 2
