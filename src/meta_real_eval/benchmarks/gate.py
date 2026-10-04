"""D2: test validity vs. reference correctness (see the Tier 2 plan, "D2").

This module is pure logic: it takes already-classified per-run
:class:`~meta_real_eval.benchmarks.outcomes.TestOutcome` sequences (one
run = one classified outcome per test, from ``outcomes.classify``) and
decides which Pynguin-generated tests are usable as a correctness oracle,
and why the rest are not. It does no execution itself, which is what makes
it testable on synthetic reference behaviour without spawning pytest -- the
real gate script (``scripts/validate_realclasseval.py``, not yet written)
supplies the three full-suite runs, the per-candidate isolated run, and the
skeleton run.

Gate algorithm (exact, cost-bounded -- reviewed and fixed in plan rev. 2):

1. Run the full reference suite 3 times.
2. A test is *stable* if its (outcome, exc_type) is identical across all 3.
3. Every stable test that is a *candidate* (a stable ``ordinary_pass`` or
   ``expected_exception``) is run once more, in isolation.
4. If the isolated result differs from the full-suite result, the test is
   ``invalid_order_dependent``.
5. The skeleton (an empty ``pass``-bodied class) is run once, to flag
   ``trivial`` tests -- ones an empty implementation already satisfies.

Nothing is silently dropped: every original test lands in exactly one of the
seven classes below, and the excluded ones are reported, not discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from .outcomes import ERROR, EXPECTED_EXCEPTION, ORDINARY_PASS, TIMEOUT, TestOutcome

VALID_BEHAVIOURAL = "valid_behavioural"
VALID_EXCEPTION_ORACLE = "valid_exception_oracle"
INVALID_REFERENCE_MISMATCH = "invalid_reference_mismatch"
INVALID_NONDETERMINISTIC = "invalid_nondeterministic"
INVALID_ORDER_DEPENDENT = "invalid_order_dependent"
INVALID_TIMEOUT = "invalid_timeout"
INVALID_ERROR = "invalid_error"
# Plan amendment A4: every assertion in the test is about some module other
# than the class under test (e.g. `assert module_1.CO_NESTED == 16` on
# `inspect`), so its oracle measures the interpreter, not the implementation.
INVALID_ENVIRONMENT_ASSERTION = "invalid_environment_assertion"

VALID = frozenset({VALID_BEHAVIOURAL, VALID_EXCEPTION_ORACLE})


@dataclass(frozen=True)
class GatedTest:
    nodeid: str
    validity: str
    ref_exc_type: Optional[str] = None  # set only for VALID_EXCEPTION_ORACLE
    trivial: bool = False

    @property
    def is_valid(self) -> bool:
        return self.validity in VALID


def _stable_key(o: TestOutcome) -> tuple:
    return (o.outcome, o.exc_type)


def classify_test_validity(
    full_suite_runs: list[TestOutcome],
    isolated_run: Optional[TestOutcome],
) -> GatedTest:
    """Steps 2-4 of the gate algorithm, for one test.

    ``full_suite_runs`` must be exactly the 3 classified outcomes for this
    same test, in run order. ``isolated_run`` is required (raises
    ``ValueError`` if missing) whenever the full-suite result turns out to be
    a stable candidate -- callers only need to actually run the isolated
    check for candidates, so a caller that skips it for a non-candidate test
    can safely pass ``None``.
    """
    if len(full_suite_runs) != 3:
        raise ValueError(f"expected exactly 3 full-suite runs, got {len(full_suite_runs)}")
    nodeid = full_suite_runs[0].nodeid
    if any(o.nodeid != nodeid for o in full_suite_runs):
        raise ValueError("full_suite_runs must all be for the same test")

    if any(o.outcome == TIMEOUT for o in full_suite_runs):
        return GatedTest(nodeid, INVALID_TIMEOUT)
    if any(o.outcome == ERROR for o in full_suite_runs):
        return GatedTest(nodeid, INVALID_ERROR)

    keys = {_stable_key(o) for o in full_suite_runs}
    if len(keys) > 1:
        return GatedTest(nodeid, INVALID_NONDETERMINISTIC)

    stable = full_suite_runs[0]
    if stable.outcome not in (ORDINARY_PASS, EXPECTED_EXCEPTION):
        # A deterministic ordinary_fail or unexpected_pass: the reference
        # itself does not satisfy its own generated test.
        return GatedTest(nodeid, INVALID_REFERENCE_MISMATCH)

    if isolated_run is None:
        raise ValueError(f"{nodeid}: a stable candidate requires an isolated run")
    if _stable_key(isolated_run) != _stable_key(stable):
        return GatedTest(nodeid, INVALID_ORDER_DEPENDENT)

    if stable.outcome == ORDINARY_PASS:
        return GatedTest(nodeid, VALID_BEHAVIOURAL)
    return GatedTest(nodeid, VALID_EXCEPTION_ORACLE, ref_exc_type=stable.exc_type)


def apply_environment_rule(
    gated: list[GatedTest],
    env_only: set[str],
) -> list[GatedTest]:
    """A4: a test whose assertions are *all* environment assertions is
    invalid, however stably the reference passes it.

    ``env_only`` names the tests with at least one assertion and none that
    depends on the class under test (computed by the scenario extractor's
    taint analysis). A test with no assertions at all is not in it -- it is a
    "does not raise" check on the class, a different (if weak) oracle -- and
    a test that mixes environment and class assertions keeps its class
    assertions and stays valid.
    """
    return [replace(g, validity=INVALID_ENVIRONMENT_ASSERTION, ref_exc_type=None)
            if g.is_valid and g.nodeid in env_only else g
            for g in gated]


def mark_trivial(
    gated: list[GatedTest],
    skeleton_outcomes: dict[str, TestOutcome],
) -> list[GatedTest]:
    """Step 5: flag a valid test that the empty (``pass``-bodied) skeleton
    already satisfies.

    A ``valid_exception_oracle`` test is trivial only when the skeleton
    raises the *same* exception type as the reference -- an unrelated crash
    on the empty skeleton is not the oracle being vacuous, it is a different
    failure altogether, so exc_type must match too.
    """
    out = []
    for g in gated:
        skel = skeleton_outcomes.get(g.nodeid)
        trivial = False
        if skel is not None and g.is_valid:
            if g.validity == VALID_BEHAVIOURAL:
                trivial = skel.outcome == ORDINARY_PASS
            else:  # VALID_EXCEPTION_ORACLE
                trivial = skel.outcome == EXPECTED_EXCEPTION and skel.exc_type == g.ref_exc_type
        out.append(replace(g, trivial=trivial))
    return out
