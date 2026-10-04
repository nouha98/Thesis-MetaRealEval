"""D1: the per-test outcome vocabulary (see the Tier 2 plan, section "D1").

Execution never collapses a test's result to a boolean. Every (test, run)
lands in exactly one of six outcomes:

    ordinary_pass        non-xfail test passed
    expected_exception    an xfail or `pytest.raises` test raised
    ordinary_fail         a non-xfail assertion failed, or an exception escaped
    unexpected_pass       a strict-xfail test did NOT raise
    error                 collection, import or setup failure
    timeout                the test exceeded the time limit

This module classifies :class:`~meta_real_eval.core.sandbox.RawTestReport`
sequences (pytest's own passed/failed/skipped vocabulary, per phase) into
that six-way outcome, using a static, source-level pass over the test
function (:func:`static_test_info`) to tell an ``expected_exception`` whose
type is asserted by the test itself (``with pytest.raises(E):``) apart from
one whose type is only known from running the reference implementation
(a bare ``@pytest.mark.xfail(strict=True)``).

Why this needs a static pass at all: pytest's report vocabulary alone cannot
tell the two apart, and conflating them lets `xfail(strict=True)` (which
accepts *any* exception) give a broken completion credit for raising the
wrong thing. The mapping from pytest's report fields to these six outcomes
was verified empirically against the installed pytest (9.1.1); see the
docstring on ``RawTestReport`` for the one surprising case (XPASS(strict)
reports ``wasxfail=None``, not a truthy value).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional

from ..core.sandbox import PytestRunResult, RawTestReport

ORDINARY_PASS = "ordinary_pass"
EXPECTED_EXCEPTION = "expected_exception"
ORDINARY_FAIL = "ordinary_fail"
UNEXPECTED_PASS = "unexpected_pass"
ERROR = "error"
TIMEOUT = "timeout"

SOURCE_EXPLICIT_RAISES = "explicit_pytest_raises"
SOURCE_REFERENCE_XFAIL = "reference_xfail"


@dataclass(frozen=True)
class StaticTestInfo:
    """Source-level facts about one test function.

    A static property of the *test*, not of any one run: computed once from
    the suite's source and reused across every execution of it (the gate's 3
    full-suite runs, its isolated run, the skeleton run, and every
    completion's run).
    """

    has_xfail_marker: bool = False
    strict: bool = False
    has_pytest_raises: bool = False
    # Best-effort: the exception type named in `with pytest.raises(E):`,
    # unparsed from the AST. None if there isn't exactly one such block in
    # the test, or the argument isn't a simple name/attribute (e.g. a tuple
    # of types) -- both are rare in the Pynguin-generated corpus but must not
    # crash the pass.
    raises_type: Optional[str] = None


@dataclass(frozen=True)
class TestOutcome:
    """The classified D1 outcome for one (test, run)."""

    # Tells pytest's own collector this is a data class, not a test class --
    # its name just happens to start with "Test".
    __test__ = False

    nodeid: str
    outcome: str
    exc_type: Optional[str] = None
    # The following two are set only when outcome == EXPECTED_EXCEPTION.
    source: Optional[str] = None
    expected_exc_type: Optional[str] = None


# ---------------------------------------------------------------------------
# Static analysis
# ---------------------------------------------------------------------------

def _is_pytest_raises(expr: ast.expr) -> bool:
    if not isinstance(expr, ast.Call):
        return False
    name = ast.unparse(expr.func)
    return name in ("pytest.raises", "raises")


def _raises_type_name(with_node: ast.With) -> Optional[str]:
    raises_items = [i for i in with_node.items if _is_pytest_raises(i.context_expr)]
    if len(raises_items) != 1:
        return None
    call = raises_items[0].context_expr
    if not call.args:
        return None
    arg = call.args[0]
    if isinstance(arg, (ast.Name, ast.Attribute)):
        return ast.unparse(arg)
    return None  # a tuple of types, or something else not worth guessing at


def static_test_info(test_source: str) -> dict[str, StaticTestInfo]:
    """AST-inspect a test module. Returns ``{function_name: StaticTestInfo}``.

    Only top-level ``def test*``/``async def test*`` functions are
    considered, matching pytest's own default collection and the Pynguin
    suites' shape (no test classes).
    """
    tree = ast.parse(test_source)
    result: dict[str, StaticTestInfo] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test"):
            continue

        xfail_deco = next(
            (d for d in node.decorator_list if "xfail" in ast.unparse(d)), None
        )
        strict = xfail_deco is not None and "strict=True" in ast.unparse(xfail_deco).replace(" ", "")

        raises_withs = [
            n for n in ast.walk(node)
            if isinstance(n, ast.With) and any(_is_pytest_raises(i.context_expr) for i in n.items)
        ]
        raises_type = _raises_type_name(raises_withs[0]) if len(raises_withs) == 1 else None

        result[node.name] = StaticTestInfo(
            has_xfail_marker=xfail_deco is not None,
            strict=strict,
            has_pytest_raises=bool(raises_withs),
            raises_type=raises_type,
        )
    return result


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify(
    nodeid: str,
    reports: list[RawTestReport],
    static: StaticTestInfo,
    *,
    ref_exc_type: Optional[str] = None,
    timed_out: bool = False,
) -> TestOutcome:
    """Classify one test's raw phase reports (for one run) into its D1 outcome.

    ``ref_exc_type`` is the reference implementation's own ``exc_type`` for
    this test. It is used only for a ``reference_xfail``-sourced expected
    exception (the type is not stated in the test itself, so it can only
    come from having run the reference); the gate supplies it. It is unused
    for ``explicit_pytest_raises``, where ``static.raises_type`` already
    names the expected type.
    """
    if timed_out:
        return TestOutcome(nodeid, TIMEOUT)

    setup_or_teardown_failed = any(
        r.when in ("setup", "teardown") and r.pytest_outcome == "failed" for r in reports
    )
    if setup_or_teardown_failed:
        return TestOutcome(nodeid, ERROR)

    call = next((r for r in reports if r.when == "call"), None)
    if call is None:
        # Collected but never produced a "call"-phase report (e.g. the whole
        # module failed to import) -- an error, not silently "no test ran".
        return TestOutcome(nodeid, ERROR)

    # Order matters: a "passed" report with wasxfail set is a non-strict
    # XPASS, which must be classified before the plain-pass / raises-pass
    # branches below.
    if call.pytest_outcome == "passed" and call.wasxfail is not None:
        return TestOutcome(nodeid, UNEXPECTED_PASS)

    if call.pytest_outcome == "passed":
        if static.has_pytest_raises:
            # The exception was raised and caught *inside* the test's own
            # `with pytest.raises(E):` block, so it never escapes to this
            # hook (call.exc_type is None here by construction) -- the best
            # available signal for what type occurred is the type the test
            # itself demanded.
            return TestOutcome(
                nodeid, EXPECTED_EXCEPTION,
                exc_type=static.raises_type,
                source=SOURCE_EXPLICIT_RAISES,
                expected_exc_type=static.raises_type,
            )
        return TestOutcome(nodeid, ORDINARY_PASS)

    if call.pytest_outcome == "skipped" and call.wasxfail is not None:
        # An xfail-marked test that raised. Confirmed empirically: pytest
        # reports this as outcome="skipped" with wasxfail set (even to "").
        source = SOURCE_EXPLICIT_RAISES if static.has_pytest_raises else SOURCE_REFERENCE_XFAIL
        expected = static.raises_type if source == SOURCE_EXPLICIT_RAISES else ref_exc_type
        return TestOutcome(
            nodeid, EXPECTED_EXCEPTION,
            exc_type=call.exc_type, source=source, expected_exc_type=expected,
        )

    if call.pytest_outcome == "failed" and call.exc_type is None and static.has_xfail_marker:
        # XPASS(strict): pytest converts an unraised strict-xfail into a
        # failure with no exception attached. Confirmed empirically: this
        # report's wasxfail is None, not a truthy marker -- exc_type is the
        # only reliable signal here, guarded by the static xfail marker so a
        # genuinely exception-free ordinary failure (which should not exist
        # in pytest, but defensively) is never miscategorised this way.
        return TestOutcome(nodeid, UNEXPECTED_PASS)

    if call.pytest_outcome == "failed":
        return TestOutcome(nodeid, ORDINARY_FAIL, exc_type=call.exc_type)

    return TestOutcome(nodeid, ERROR)


def classify_run(
    run: PytestRunResult,
    statics: dict[str, StaticTestInfo],
    *,
    ref_exc_types: Optional[dict[str, str]] = None,
    requested: Optional[list[str]] = None,
) -> dict[str, TestOutcome]:
    """Classify every test in one :func:`execute_pytest` run.

    ``requested`` should be the full list of test function names the caller
    asked for (``select``, if one was passed to ``execute_pytest``); a name
    in it with no report at all (collection failed outright, so nothing was
    ever attempted) is still classified, as ``error`` unless it is in
    ``run.timed_out_nodeids``. Without ``requested``, only names that
    produced at least one report are classified.
    """
    ref_exc_types = ref_exc_types or {}
    names = set(requested) if requested is not None else set()
    names |= {nodeid.rsplit("::", 1)[-1] for nodeid in run.reports}

    result: dict[str, TestOutcome] = {}
    for name in names:
        nodeid = next((n for n in run.reports if n.rsplit("::", 1)[-1] == name), name)
        result[name] = classify(
            name,
            run.reports.get(nodeid, []),
            statics.get(name, StaticTestInfo()),
            ref_exc_type=ref_exc_types.get(name),
            timed_out=name in run.timed_out_nodeids,
        )
    return result
