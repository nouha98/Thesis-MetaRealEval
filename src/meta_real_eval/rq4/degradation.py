"""Degrade test suites by removing a fraction of assertions.

The test block in HumanEval is a function `check(candidate)` containing
assert statements.  We parse it as an AST, collect the assert nodes, and
randomly drop a given fraction of them.  A degraded version with 0% removed
is the intact baseline (included for alignment with degradation_levels=[0.0, ...]).
"""

from __future__ import annotations

import ast
import copy
import random


def _collect_assert_indices(test_code: str) -> list[int]:
    """Return indices of ast.Assert nodes in the check() function body."""
    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        return []
    indices: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "check":
            for i, stmt in enumerate(node.body):
                if isinstance(stmt, ast.Assert):
                    indices.append(i)
            break
    return indices


def degrade(test_code: str, removal_fraction: float, seed: int = 42) -> str:
    """Return a copy of test_code with ``removal_fraction`` of asserts removed.

    Parameters
    ----------
    removal_fraction:
        0.0 → nothing removed; 0.8 → 80% of assert statements removed.
    """
    if removal_fraction <= 0.0:
        return test_code

    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        return test_code

    mutated = copy.deepcopy(tree)
    for node in ast.walk(mutated):
        if isinstance(node, ast.FunctionDef) and node.name == "check":
            assert_indices = [
                i for i, stmt in enumerate(node.body)
                if isinstance(stmt, ast.Assert)
            ]
            rng = random.Random(seed)
            n_remove = int(len(assert_indices) * removal_fraction)
            to_remove = set(rng.sample(assert_indices, min(n_remove, len(assert_indices))))
            node.body = [stmt for i, stmt in enumerate(node.body) if i not in to_remove]
            # Ensure body is never empty
            if not node.body:
                node.body = [ast.Pass()]
            break

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
