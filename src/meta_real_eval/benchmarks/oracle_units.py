"""Tier 2 RQ4: the oracle units of a Pynguin test file, and their removal.

The class-level analogue of Tier 1's assertion removal (``rq4/degradation.py``),
fixed in the plan (rev. 6, section 8.1) before any RQ4 result existed:

``assert`` unit        one ``assert`` in a ``valid_behavioural`` test whose
                       expression mentions the module under test or a value
                       derived from it -- the taint rule D4's scenario extractor
                       uses to drop environment observations
                       (``scenarios._extract_one``); an environment assert such
                       as ``module_1.CO_NESTED == 16`` is never a unit.
``exception_test`` unit one whole ``valid_exception_oracle`` test.

Removing an assert unit rewrites ``assert T, M`` to the expression statement
``(T)``: the same expression is evaluated, in the same order, with the same
short-circuits and side effects (the comparison operator included); only the
truth check ``bool(T)`` and the message ``M`` go. A weakened test therefore
still runs every statement and still fails on an unexpected exception -- the
explicit check is what is removed, not the execution. Removing an exception unit
drops the test from the selected suite (``DegradedSuite.subset``); this module
never edits exception tests.

The rewrite splices UTF-8 byte spans, so every other byte of the file is kept,
and it is self-checked: the result must parse to the original AST with exactly
the selected ``Assert`` nodes replaced by ``Expr(test)``, or it raises.
"""

from __future__ import annotations

import ast
import copy
import math
import random
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from .scenarios import _names, _sut_alias

ASSERT_UNIT = "assert"
EXCEPTION_UNIT = "exception_test"

_NEWLINE_RE = re.compile(rb"\r\n|\r|\n")
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


class OracleUnitError(RuntimeError):
    """A rewrite did not produce exactly the intended AST (a bug, never data)."""


@dataclass(frozen=True)
class OracleUnit:
    unit_id: str        # "<test>#a<k>" (k-th assert unit of the test) or "<test>"
    test: str
    kind: str           # ASSERT_UNIT | EXCEPTION_UNIT
    lineno: int


def _test_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")]


def _own_nodes(fn: ast.AST) -> list[ast.AST]:
    """Every node inside ``fn``'s body, not descending into nested scopes."""
    out, stack = [], list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        out.append(node)
        if not isinstance(node, _SCOPES):
            stack.extend(ast.iter_child_nodes(node))
    return out


def _target_names(target: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def _unit_asserts(fn: ast.AST, sut: str) -> list[ast.Assert]:
    """The asserts of one test that check the class under test, in source order."""
    stmts = sorted((n for n in _own_nodes(fn)
                    if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Assert))),
                   key=lambda n: (n.lineno, n.col_offset))
    tainted, units = {sut}, []
    for s in stmts:
        if isinstance(s, ast.Assert):
            # Anywhere in the test, not only the observed (left) side D4 reads: on
            # the staged corpus both give the same 7,807 asserts, and this one also
            # keeps a reversed comparison (`assert 5 == obj.count`) a unit.
            if _names(s.test) & tainted:
                units.append(s)
        elif s.value is not None and _names(s.value) & tainted:
            targets = s.targets if isinstance(s, ast.Assign) else [s.target]
            for t in targets:
                tainted |= _target_names(t)
    return units


def _units_with_nodes(tree: ast.Module, module_name: str, behavioural: set[str],
                      exception: set[str]) -> list[tuple[OracleUnit, Optional[ast.Assert]]]:
    sut = _sut_alias(tree, module_name)
    out = []
    for fn in _test_functions(tree):
        if fn.name in exception:
            out.append((OracleUnit(fn.name, fn.name, EXCEPTION_UNIT, fn.lineno), None))
        elif fn.name in behavioural:
            for k, node in enumerate(_unit_asserts(fn, sut)):
                out.append((OracleUnit(f"{fn.name}#a{k}", fn.name, ASSERT_UNIT, node.lineno), node))
    return out


def find_oracle_units(test_source: str, module_name: str, behavioural: Iterable[str],
                      exception: Iterable[str]) -> list[OracleUnit]:
    """The oracle units of a test file, in source order.

    ``behavioural`` / ``exception`` are the names of the gate's
    ``valid_behavioural`` / ``valid_exception_oracle`` tests; any other test is
    never a unit and never touched.
    """
    tree = ast.parse(test_source)
    return [u for u, _ in _units_with_nodes(tree, module_name, set(behavioural), set(exception))]


def _line_starts(data: bytes) -> list[int]:
    return [0] + [m.end() for m in _NEWLINE_RE.finditer(data)]


class _Weaken(ast.NodeTransformer):
    def __init__(self, positions: set[tuple[int, int]]):
        self.positions = positions

    def visit_Assert(self, node: ast.Assert):
        if (node.lineno, node.col_offset) in self.positions:
            return ast.Expr(value=node.test)
        return node


def weaken_asserts(test_source: str, module_name: str, behavioural: Iterable[str],
                   exception: Iterable[str], remove: Iterable[str]) -> str:
    """``test_source`` with the named assert units rewritten to ``(<test>)``.

    Exception units in ``remove`` are ignored here (they leave via the suite's
    subset). Returns ``test_source`` itself when no assert unit is named.
    """
    remove = set(remove)
    tree = ast.parse(test_source)
    nodes = [node for unit, node in _units_with_nodes(tree, module_name, set(behavioural), set(exception))
             if unit.unit_id in remove and node is not None]
    if not nodes:
        return test_source

    data = test_source.encode("utf-8")
    starts = _line_starts(data)

    def offset(line: int, col: int) -> int:
        return starts[line - 1] + col          # ast column offsets are UTF-8 byte offsets

    pieces, pos = [], 0
    for node in sorted(nodes, key=lambda n: (n.lineno, n.col_offset)):
        a, b = offset(node.lineno, node.col_offset), offset(node.end_lineno, node.end_col_offset)
        ta, tb = offset(node.test.lineno, node.test.col_offset), offset(node.test.end_lineno, node.test.end_col_offset)
        pieces += [data[pos:a], b"(", data[ta:tb], b")"]
        pos = b
    pieces.append(data[pos:])
    weakened = b"".join(pieces).decode("utf-8")

    expected = _Weaken({(n.lineno, n.col_offset) for n in nodes}).visit(copy.deepcopy(tree))
    try:
        got = ast.parse(weakened)
    except SyntaxError as exc:
        raise OracleUnitError(f"weakened test file does not parse: {exc}") from exc
    if ast.dump(got) != ast.dump(expected):
        raise OracleUnitError("weakened test file differs from the intended AST")
    return weakened


def removal_order(units: list[OracleUnit], seed_key: str) -> list[str]:
    """One seeded shuffle of the unit ids; every level removes a prefix of it."""
    ids = [u.unit_id for u in units]
    random.Random(seed_key).shuffle(ids)
    return ids


def n_removed(n_units: int, level: float) -> int:
    """Units removed at ``level``: ``ceil(level * n)``, as Tier 1's assert removal."""
    return min(math.ceil(n_units * level), n_units) if level > 0 else 0


def min_units_for_levels(levels: Iterable[float]) -> int:
    """The smallest n that keeps >= 1 unit at every level (0.8 -> 5)."""
    top = max(levels)
    return next(n for n in range(1, 10_000) if n - n_removed(n, top) >= 1)
