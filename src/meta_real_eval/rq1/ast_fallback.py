"""AST-based fallback for LLM-like semantic mutants.

Used when Innkube is unavailable or in mock mode. Injects the kinds of
subtle faults that LLMs commonly produce:

- Off-by-one: `i` → `i + 1`, `len(x)` → `len(x) - 1`
- Wrong return: replace a return expression with a constant
- Condition flip: negate a boolean sub-expression in an `if` condition
- Missing base case: delete the first `if` guard in a function
"""

from __future__ import annotations

import ast
import copy
import random

from ..stage0.corpus_builder import Mutant


class _OffByOneTransformer(ast.NodeTransformer):
    """Replace the first `x` usage in a BinOp with `x + 1`."""

    def __init__(self) -> None:
        self._applied = False

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        if not self._applied and isinstance(node.op, (ast.Sub, ast.Add)):
            # Wrap the right operand with +1 / -1
            if isinstance(node.op, ast.Sub):
                node.right = ast.BinOp(
                    left=node.right,
                    op=ast.Add(),
                    right=ast.Constant(value=1),
                )
            else:
                node.right = ast.BinOp(
                    left=node.right,
                    op=ast.Sub(),
                    right=ast.Constant(value=1),
                )
            self._applied = True
        return self.generic_visit(node)


class _ReturnConstantTransformer(ast.NodeTransformer):
    """Replace the first non-trivial return with `return None`."""

    def __init__(self) -> None:
        self._applied = False

    def visit_Return(self, node: ast.Return) -> ast.AST:
        if not self._applied and node.value is not None:
            if not isinstance(node.value, ast.Constant):
                node.value = ast.Constant(value=None)
                self._applied = True
        return node


class _ConditionFlipTransformer(ast.NodeTransformer):
    """Negate the test in the first `if` statement."""

    def __init__(self) -> None:
        self._applied = False

    def visit_If(self, node: ast.If) -> ast.AST:
        if not self._applied:
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
            self._applied = True
        return self.generic_visit(node)


_TRANSFORMERS = [
    ("off_by_one",   _OffByOneTransformer,    "Off-by-one error in arithmetic"),
    ("return_none",  _ReturnConstantTransformer, "Replace return value with None"),
    ("flip_cond",    _ConditionFlipTransformer,  "Negate first if-condition"),
]


def generate_ast_fallback_mutants(
    prompt: str,
    canonical_solution: str,
    seed: int = 42,
) -> list[Mutant]:
    """Return one mutant per AST transform, skipping if no site is found."""
    full_code = prompt + canonical_solution
    try:
        tree = ast.parse(full_code)
    except SyntaxError:
        return []

    mutants: list[Mutant] = []
    for name, TransformerClass, description in _TRANSFORMERS:
        mutated = TransformerClass().visit(copy.deepcopy(tree))
        try:
            code = ast.unparse(mutated)
        except Exception:
            continue
        # Skip if no change was actually made
        try:
            original = ast.unparse(ast.parse(full_code))
        except Exception:
            original = ""
        if code.strip() == original.strip():
            continue
        mutants.append(Mutant(
            mutant_id=f"AST_{name}",
            operator="LLM",
            description=description,
            code=code,
        ))

    return mutants
