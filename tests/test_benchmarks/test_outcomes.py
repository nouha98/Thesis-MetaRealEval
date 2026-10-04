"""D1 unit tests: pure classification logic, no subprocess.

End-to-end verification that a real pytest run actually produces the report
shapes assumed here lives in tests/test_core/test_sandbox_pytest.py.
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
    StaticTestInfo,
    classify,
    static_test_info,
)
from meta_real_eval.core.sandbox import RawTestReport


def _report(nodeid="t", when="call", pytest_outcome="passed", wasxfail=None, exc_type=None):
    return RawTestReport(nodeid=nodeid, when=when, pytest_outcome=pytest_outcome,
                         wasxfail=wasxfail, exc_type=exc_type)


PLAIN = StaticTestInfo()
XFAIL_BARE = StaticTestInfo(has_xfail_marker=True, strict=True)
RAISES_ONLY = StaticTestInfo(has_pytest_raises=True, raises_type="KeyError")
XFAIL_WITH_RAISES = StaticTestInfo(has_xfail_marker=True, strict=True,
                                   has_pytest_raises=True, raises_type="ValueError")


# ---------------------------------------------------------------------------
# classify(): each D1 outcome, from raw report shapes confirmed empirically
# against the installed pytest (see sandbox.py's RawTestReport docstring).
# ---------------------------------------------------------------------------

def test_ordinary_pass():
    o = classify("t", [_report()], PLAIN)
    assert o.outcome == ORDINARY_PASS
    assert o.exc_type is None and o.source is None


def test_ordinary_fail():
    o = classify("t", [_report(pytest_outcome="failed", exc_type="builtins.AssertionError")], PLAIN)
    assert o.outcome == ORDINARY_FAIL
    assert o.exc_type == "builtins.AssertionError"


def test_expected_exception_reference_xfail():
    """A bare `@pytest.mark.xfail(strict=True)` that raised: pytest reports
    this as outcome="skipped", wasxfail set (even to "")."""
    o = classify("t", [_report(pytest_outcome="skipped", wasxfail="",
                               exc_type="builtins.ValueError")],
                 XFAIL_BARE, ref_exc_type="builtins.ValueError")
    assert o.outcome == EXPECTED_EXCEPTION
    assert o.source == SOURCE_REFERENCE_XFAIL
    assert o.exc_type == "builtins.ValueError"
    assert o.expected_exc_type == "builtins.ValueError"


def test_expected_exception_explicit_raises_passes():
    """`with pytest.raises(E):` that caught its exception internally never
    reaches the hook (call.exc_type is None) -- the expected type comes from
    the test's own source, not from a run."""
    o = classify("t", [_report(pytest_outcome="passed")], RAISES_ONLY)
    assert o.outcome == EXPECTED_EXCEPTION
    assert o.source == SOURCE_EXPLICIT_RAISES
    assert o.exc_type == "KeyError"
    assert o.expected_exc_type == "KeyError"


def test_expected_exception_xfail_wrapping_raises_uses_raises_type():
    """xfail(strict=True) AND an inner pytest.raises(E): if the wrong type
    escapes, xfail still catches it, but the *expected* type is the one the
    test itself named, not whatever the reference happened to raise."""
    o = classify("t", [_report(pytest_outcome="skipped", wasxfail="",
                               exc_type="builtins.TypeError")],
                 XFAIL_WITH_RAISES, ref_exc_type="builtins.KeyError")
    assert o.source == SOURCE_EXPLICIT_RAISES
    assert o.expected_exc_type == "ValueError"  # from static.raises_type, not ref_exc_type
    assert o.exc_type == "builtins.TypeError"    # what actually escaped


def test_unexpected_pass_strict_xfail_no_exception():
    """XPASS(strict): confirmed empirically that pytest reports this as
    outcome="failed" with wasxfail=None (NOT a truthy wasxfail) -- exc_type
    is None because nothing raised, and the static xfail marker is what
    distinguishes this from an ordinary failure."""
    o = classify("t", [_report(pytest_outcome="failed", wasxfail=None, exc_type=None)],
                 XFAIL_BARE)
    assert o.outcome == UNEXPECTED_PASS


def test_unexpected_pass_nonstrict_xfail():
    """Non-strict XPASS: outcome="passed" with wasxfail set (confirmed
    empirically) -- checked before the plain-pass branch."""
    o = classify("t", [_report(pytest_outcome="passed", wasxfail="")],
                 StaticTestInfo(has_xfail_marker=True, strict=False))
    assert o.outcome == UNEXPECTED_PASS


def test_error_on_setup_failure():
    reports = [
        _report(when="setup", pytest_outcome="failed", exc_type="builtins.RuntimeError"),
        _report(when="teardown", pytest_outcome="passed"),
    ]
    assert classify("t", reports, PLAIN).outcome == ERROR


def test_error_on_missing_call_report():
    """No 'call' phase report at all (e.g. the whole module failed to
    import): an error, not silently absent."""
    assert classify("t", [], PLAIN).outcome == ERROR


def test_timeout_overrides_everything():
    o = classify("t", [_report(pytest_outcome="passed")], PLAIN, timed_out=True)
    assert o.outcome == TIMEOUT


# ---------------------------------------------------------------------------
# static_test_info()
# ---------------------------------------------------------------------------

def test_static_info_plain_test():
    info = static_test_info("def test_a():\n    assert True\n")
    assert info["test_a"] == StaticTestInfo()


def test_static_info_xfail_strict():
    src = "import pytest\n\n@pytest.mark.xfail(strict=True)\ndef test_a():\n    raise ValueError()\n"
    info = static_test_info(src)["test_a"]
    assert info.has_xfail_marker and info.strict


def test_static_info_xfail_nonstrict():
    src = "import pytest\n\n@pytest.mark.xfail()\ndef test_a():\n    pass\n"
    info = static_test_info(src)["test_a"]
    assert info.has_xfail_marker and not info.strict


def test_static_info_pytest_raises_single_name():
    src = "import pytest\n\ndef test_a():\n    with pytest.raises(KeyError):\n        {}['x']\n"
    info = static_test_info(src)["test_a"]
    assert info.has_pytest_raises
    assert info.raises_type == "KeyError"


def test_static_info_pytest_raises_attribute_name():
    src = "import pytest, mymod\n\ndef test_a():\n    with pytest.raises(mymod.MyError):\n        f()\n"
    info = static_test_info(src)["test_a"]
    assert info.raises_type == "mymod.MyError"


def test_static_info_ignores_non_test_functions():
    src = "def helper():\n    pass\n\ndef test_a():\n    pass\n"
    info = static_test_info(src)
    assert set(info) == {"test_a"}
