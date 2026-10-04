"""Integration tests for execute_pytest: does a real pytest run map to every
D1 outcome the way benchmarks.outcomes.classify() expects it to?

These are the only tests in the Tier 2 contract suite that actually spawn
pytest as a subprocess -- everything in tests/test_benchmarks/ is pure logic
on hand-built fixtures. This file is the bridge that proves those fixtures
are not fictional.
"""

from __future__ import annotations

from meta_real_eval.benchmarks.outcomes import (
    ERROR,
    EXPECTED_EXCEPTION,
    ORDINARY_FAIL,
    ORDINARY_PASS,
    SOURCE_EXPLICIT_RAISES,
    SOURCE_REFERENCE_XFAIL,
    TIMEOUT,
    UNEXPECTED_PASS,
    classify_run,
    static_test_info,
)
from meta_real_eval.core.sandbox import execute_pytest

MODULE = "C"
SOLUTION = (
    "class C:\n"
    "    def f(self, x):\n"
    "        return x + 1\n"
    "    def missing(self):\n"
    "        raise AttributeError('C has no such method')\n"
)

TEST_SOURCE = '''\
import pytest
import C as module_0


def test_ordinary_pass():
    assert module_0.C().f(1) == 2


def test_ordinary_fail():
    assert module_0.C().f(1) == 999


@pytest.mark.xfail(strict=True)
def test_reference_xfail():
    module_0.C().missing()


def test_explicit_raises():
    with pytest.raises(AttributeError):
        module_0.C().missing()


@pytest.mark.xfail(strict=True)
def test_unexpected_pass():
    module_0.C().f(1)


def test_collection_error():
    raise RuntimeError("boom in body")
'''

ALL_NAMES = [
    "test_ordinary_pass", "test_ordinary_fail", "test_reference_xfail",
    "test_explicit_raises", "test_unexpected_pass", "test_collection_error",
]


def _classify(select=None, timeout_s=10.0):
    run = execute_pytest(MODULE, SOLUTION, TEST_SOURCE, timeout_s=timeout_s, select=select)
    statics = static_test_info(TEST_SOURCE)
    return classify_run(run, statics, requested=select), run


def test_all_non_timeout_outcomes_end_to_end():
    outcomes, run = _classify(select=ALL_NAMES)

    assert outcomes["test_ordinary_pass"].outcome == ORDINARY_PASS

    assert outcomes["test_ordinary_fail"].outcome == ORDINARY_FAIL
    assert outcomes["test_ordinary_fail"].exc_type == "builtins.AssertionError"

    xf = outcomes["test_reference_xfail"]
    assert xf.outcome == EXPECTED_EXCEPTION
    assert xf.source == SOURCE_REFERENCE_XFAIL
    assert xf.exc_type == "builtins.AttributeError"

    er = outcomes["test_explicit_raises"]
    assert er.outcome == EXPECTED_EXCEPTION
    assert er.source == SOURCE_EXPLICIT_RAISES
    assert er.expected_exc_type == "AttributeError"

    assert outcomes["test_unexpected_pass"].outcome == UNEXPECTED_PASS

    # A RuntimeError escaping the test body is an ordinary failure, not a
    # harness "error" -- a genuine "error" needs a setup/collection failure,
    # covered separately below.
    assert outcomes["test_collection_error"].outcome == ORDINARY_FAIL
    assert outcomes["test_collection_error"].exc_type == "builtins.RuntimeError"

    assert run.timed_out_nodeids == set()


def test_import_failure_is_error_for_every_requested_test():
    """A solution that fails to import: no test ever reaches a 'call' phase,
    so every requested name is classified as an error, not silently absent."""
    broken_solution = "raise ImportError('cannot import this module')\n"
    run = execute_pytest(MODULE, broken_solution, TEST_SOURCE, timeout_s=10.0,
                         select=["test_ordinary_pass"])
    statics = static_test_info(TEST_SOURCE)
    outcomes = classify_run(run, statics, requested=["test_ordinary_pass"])
    assert outcomes["test_ordinary_pass"].outcome == ERROR


def test_setup_fixture_failure_is_error():
    solution = "class C:\n    pass\n"
    test_src = (
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def broken():\n"
        "    raise RuntimeError('fixture blew up')\n\n"
        "def test_uses_broken(broken):\n"
        "    assert True\n"
    )
    run = execute_pytest(MODULE, solution, test_src, timeout_s=10.0,
                         select=["test_uses_broken"])
    statics = static_test_info(test_src)
    outcomes = classify_run(run, statics, requested=["test_uses_broken"])
    assert outcomes["test_uses_broken"].outcome == ERROR


def test_hanging_test_is_timeout_and_does_not_block_earlier_tests():
    """pytest runs a file's tests in source order: a hang placed after the
    fast tests must not corrupt their already-logged outcomes, and must
    itself come back as TIMEOUT rather than silently missing."""
    test_src = (
        "def test_fast():\n"
        "    assert True\n\n"
        "def test_hangs():\n"
        "    while True:\n"
        "        pass\n"
    )
    run = execute_pytest(MODULE, "class C:\n    pass\n", test_src, timeout_s=3.0,
                         select=["test_fast", "test_hangs"])
    statics = static_test_info(test_src)
    outcomes = classify_run(run, statics, requested=["test_fast", "test_hangs"])

    assert outcomes["test_fast"].outcome == ORDINARY_PASS
    assert outcomes["test_hangs"].outcome == TIMEOUT
    assert "test_hangs" in run.timed_out_nodeids
