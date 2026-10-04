"""D3: scoring policies (see the Tier 2 plan, "D3").

Every metric here is derived entirely from already-classified D1 outcomes
plus the D2 gate's verdicts -- nothing in this module executes anything. A
policy change (say, adding a new sensitivity metric) never needs
re-running a completion, which is exactly the property RQ4's degraded-suite
reuse (recomputing scores from stored outcomes restricted to a subset of
tests) depends on: see :func:`score_completion`'s docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .gate import VALID_BEHAVIOURAL, VALID_EXCEPTION_ORACLE, GatedTest
from .outcomes import EXPECTED_EXCEPTION, ORDINARY_PASS, TestOutcome


@dataclass(frozen=True)
class Scores:
    # Primary: a valid_exception_oracle test succeeds only if the raised
    # exception's type matches what was expected (see _succeeds_primary).
    pass_rate: float
    # Sensitivity 1: exception-oracle tests excluded entirely.
    behavioural_pass_rate: Optional[float]
    # Sensitivity 2: trivial tests (ones the empty skeleton already passes)
    # excluded.
    nontrivial_pass_rate: Optional[float]
    # Diagnostic only, comparable with the published protocol, never the
    # metric a ranking is computed from: pytest's own xfail rule, where any
    # exception satisfies an expected_exception test regardless of type.
    pytest_native_pass_rate: float
    # Secondary, comparable with Tier 1's pass@k: every valid test succeeds
    # under the primary policy.
    passed_all: bool
    n_valid: int


def _succeeds_primary(gated: GatedTest, result: TestOutcome) -> bool:
    if gated.validity == VALID_BEHAVIOURAL:
        return result.outcome == ORDINARY_PASS
    if gated.validity == VALID_EXCEPTION_ORACLE:
        return result.outcome == EXPECTED_EXCEPTION and result.exc_type == gated.ref_exc_type
    raise ValueError(f"{gated.nodeid} is not a valid test (validity={gated.validity!r})")


def _succeeds_native(result: TestOutcome) -> bool:
    """pytest's own xfail rule: any exception satisfies an xfail/raises test."""
    return result.outcome in (ORDINARY_PASS, EXPECTED_EXCEPTION)


def score_completion(
    valid_tests: list[GatedTest],
    results: dict[str, TestOutcome],
) -> Scores:
    """Score one completion against its task's valid tests.

    ``valid_tests`` must all be ``VALID_BEHAVIOURAL`` or
    ``VALID_EXCEPTION_ORACLE`` (the D2 gate's output, filtered to
    ``is_valid``) -- passing an invalid test raises via
    :func:`_succeeds_primary`. ``results`` is the completion's own classified
    outcome per nodeid; a valid test missing from it raises ``KeyError``
    rather than silently scoring as a failure, since a hole in the results is
    a bug in the caller, not a 0.

    RQ4's degraded-suite reuse depends on this function being a pure
    aggregation over ``valid_tests``: computing a degraded-suite score is
    exactly this same function called on a *subset* of ``valid_tests``, with
    ``results`` unchanged, and no re-execution. That equivalence only holds
    because dropping a whole test never changes another test's outcome
    (guaranteed by the D2 order-independence check) and because this
    function never looks past the tests it is given.
    """
    if not valid_tests:
        raise ValueError("score_completion requires at least one valid test")

    behavioural = [g for g in valid_tests if g.validity == VALID_BEHAVIOURAL]
    nontrivial = [g for g in valid_tests if not g.trivial]

    primary_hits = native_hits = behavioural_hits = nontrivial_hits = 0
    for g in valid_tests:
        r = results[g.nodeid]
        ok = _succeeds_primary(g, r)
        primary_hits += ok
        native_hits += _succeeds_native(r)
        if g.validity == VALID_BEHAVIOURAL:
            behavioural_hits += ok
        if not g.trivial:
            nontrivial_hits += ok

    n = len(valid_tests)
    return Scores(
        pass_rate=primary_hits / n,
        behavioural_pass_rate=(behavioural_hits / len(behavioural)) if behavioural else None,
        nontrivial_pass_rate=(nontrivial_hits / len(nontrivial)) if nontrivial else None,
        pytest_native_pass_rate=native_hits / n,
        passed_all=(primary_hits == n),
        n_valid=n,
    )
