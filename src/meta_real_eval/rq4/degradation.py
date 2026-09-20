"""Degrade test suites by removing a fraction of assertions.

The test block in HumanEval is a function `check(candidate)` containing
assert statements.  We parse it as an AST, collect the assert nodes, and
remove a given fraction of them.  A degraded version with 0% removed is the
intact baseline (included for alignment with degradation_levels=[0.0, ...]).

Three properties this has to get right, each of which was wrong before and each
of which silently weakened RQ4's trend test rather than failing loudly:

*Rounding.* ``int(n * fraction)`` truncates, so a suite of 4 asserts at the 20%
level lost ``int(0.8) == 0`` of them -- the "degraded" suite was the intact
suite. That hit 34 of the 161 tasks that have any assert, all at the 20% level,
and made the weakest degradation step a no-op for a fifth of the corpus.
``ceil`` guarantees at least one assert goes whenever a removal was asked for.

*Reach.* Collecting only ``check``'s top-level statements misses asserts nested
inside a ``for`` or ``if``. Tasks 32, 38 and 50 keep every assert inside a loop,
so they had nothing degradable at all and contributed a flat line to a trend
test about degradation.

*Nesting.* The levels have to be cumulative: the 50% suite must be missing
everything the 20% suite was missing, plus more. Re-seeding an RNG per call and
sampling ``k`` items does not guarantee that -- ``random.sample`` picks its
algorithm from ``k`` relative to the population size, so two calls with
different ``k`` are not required to agree on their common prefix. Drawing one
shuffled order per suite and taking prefixes makes the nesting structural.
Page's L (H1b) is a monotone trend test over these levels, so non-nested removal
would inject noise into precisely the signal being measured.
"""

from __future__ import annotations

import ast
import copy
import math
import random


def _assert_nodes(check: ast.FunctionDef) -> list[ast.Assert]:
    """Every assert inside ``check``, in source order.

    ``ast.walk`` is breadth-first, so it is deterministic but does not follow
    the program text; sorting by position gives an order a reader can line up
    against the suite, which matters because the removal order is seeded and
    therefore reproducible only if the starting order is well defined.
    """
    found = [n for n in ast.walk(check) if isinstance(n, ast.Assert)]
    return sorted(found, key=lambda n: (getattr(n, "lineno", 0),
                                        getattr(n, "col_offset", 0)))


class _RemoveAsserts(ast.NodeTransformer):
    """Drop the selected assert statements, keeping every body non-empty."""

    def __init__(self, doomed: set[int]) -> None:
        self._doomed = doomed

    def visit_Assert(self, node: ast.Assert):
        return None if id(node) in self._doomed else node

    def generic_visit(self, node: ast.AST) -> ast.AST:
        node = super().generic_visit(node)
        # Removing the only statement in a `for`/`if`/`with` body leaves a
        # block with no statements, which does not unparse to valid Python.
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and not block and hasattr(node, field):
                if field == "body" or isinstance(node, ast.FunctionDef):
                    setattr(node, field, [ast.Pass()])
        return node


def degrade(test_code: str, removal_fraction: float, seed: int = 42) -> str:
    """Return a copy of test_code with ``removal_fraction`` of asserts removed.

    Parameters
    ----------
    removal_fraction:
        0.0 → nothing removed; 0.8 → 80% of assert statements removed, rounded
        up, so any positive fraction removes at least one assert.
    """
    if removal_fraction <= 0.0:
        return test_code

    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        return test_code

    mutated = copy.deepcopy(tree)
    check = next(
        (n for n in ast.walk(mutated)
         if isinstance(n, ast.FunctionDef) and n.name == "check"),
        None,
    )
    if check is None:
        return test_code

    asserts = _assert_nodes(check)
    if not asserts:
        return test_code

    # One shuffled order, then a prefix: level 0.2's removals are a subset of
    # level 0.5's, which are a subset of level 0.8's.
    order = list(range(len(asserts)))
    random.Random(seed).shuffle(order)
    n_remove = min(math.ceil(len(asserts) * removal_fraction), len(asserts))
    doomed = {id(asserts[i]) for i in order[:n_remove]}

    _RemoveAsserts(doomed).visit(check)
    if not check.body:
        check.body = [ast.Pass()]
    ast.fix_missing_locations(mutated)

    try:
        return ast.unparse(mutated)
    except Exception:
        return test_code


def degrade_all_levels(
    test_code: str,
    levels: list[float],
    seed: int = 42,
) -> dict[float, str]:
    """Return {fraction: degraded_test_code} for each level in levels."""
    return {level: degrade(test_code, level, seed=seed) for level in levels}
