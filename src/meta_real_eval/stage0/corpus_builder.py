"""Generate a corpus of traditional (AOR, ROR, SDL) mutants for one task.

Each mutant is produced by applying exactly one syntactic change to the
canonical solution.  The resulting code is stored as a full executable
string (prompt + mutated body) so it can be run directly in the sandbox.
"""

from __future__ import annotations

import ast
import copy
import random
from dataclasses import dataclass


@dataclass
class Mutant:
    mutant_id: str       # e.g. "AOR_3"
    operator: str        # "AOR" | "ROR" | "SDL"
    description: str
    code: str            # prompt + mutated body — ready for sandbox


# ---------------------------------------------------------------------------
# Operator tables
# ---------------------------------------------------------------------------

_ARITH_REPLACEMENTS: dict[type, list[type]] = {
    ast.Add:      [ast.Sub, ast.Mult, ast.FloorDiv],
    ast.Sub:      [ast.Add, ast.Mult, ast.FloorDiv],
    ast.Mult:     [ast.Add, ast.Sub, ast.FloorDiv],
    ast.FloorDiv: [ast.Add, ast.Sub, ast.Mult],
    ast.Div:      [ast.Sub, ast.Mult, ast.FloorDiv],
    ast.Mod:      [ast.Add, ast.Sub, ast.Mult],
}

_CMP_REPLACEMENTS: dict[type, list[type]] = {
    ast.Lt:    [ast.LtE, ast.Gt,  ast.GtE, ast.Eq,    ast.NotEq],
    ast.LtE:   [ast.Lt,  ast.Gt,  ast.GtE, ast.Eq,    ast.NotEq],
    ast.Gt:    [ast.Lt,  ast.LtE, ast.GtE, ast.Eq,    ast.NotEq],
    ast.GtE:   [ast.Lt,  ast.LtE, ast.Gt,  ast.Eq,    ast.NotEq],
    ast.Eq:    [ast.Lt,  ast.LtE, ast.Gt,  ast.GtE,   ast.NotEq],
    ast.NotEq: [ast.Lt,  ast.LtE, ast.Gt,  ast.GtE,   ast.Eq],
}


# ---------------------------------------------------------------------------
# Mutation site discovery
# ---------------------------------------------------------------------------

def _find_binop_sites(tree: ast.AST) -> list[tuple[ast.BinOp, int]]:
    """Return list of (BinOp node, binop_index) where index counts only BinOp nodes.

    The index must refer to position within the BinOp-only list so that
    _apply_aor can index into the same list after deepcopy.
    """
    sites = []
    binop_idx = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and type(node.op) in _ARITH_REPLACEMENTS:
            sites.append((node, binop_idx))
            binop_idx += 1
    return sites


def _find_cmp_sites(tree: ast.AST) -> list[tuple[ast.Compare, int, int]]:
    """Return list of (Compare node, comparator_index, site_index)."""
    sites = []
    site_idx = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for op_idx, op in enumerate(node.ops):
                if type(op) in _CMP_REPLACEMENTS:
                    sites.append((node, op_idx, site_idx))
                    site_idx += 1
    return sites


def _collect_deletable_stmts(func_body: list[ast.stmt]) -> list[tuple[list[ast.stmt], int]]:
    """Return (parent_body, stmt_index) pairs for statements safe to delete."""
    result = []
    for idx, stmt in enumerate(func_body):
        # Don't delete the only statement or a return-only body
        if len(func_body) > 1:
            result.append((func_body, idx))
        # Recurse into if/for/while/with bodies
        for child in ast.walk(stmt):
            if child is stmt:
                continue
            for attr in ("body", "orelse", "handlers"):
                sub = getattr(child, attr, [])
                if isinstance(sub, list) and len(sub) > 1:
                    for si, s in enumerate(sub):
                        if isinstance(s, ast.stmt):
                            result.append((sub, si))
    return result


# ---------------------------------------------------------------------------
# Mutant generation
# ---------------------------------------------------------------------------

def _apply_aor(tree: ast.AST, site_idx: int, replacement_op_type: type) -> ast.AST:
    mutated = copy.deepcopy(tree)
    sites = [n for n in ast.walk(mutated)
             if isinstance(n, ast.BinOp) and type(n.op) in _ARITH_REPLACEMENTS]
    sites[site_idx].op = replacement_op_type()
    return mutated


def _apply_ror(tree: ast.AST, node_path: list, op_idx: int, replacement_op_type: type) -> ast.AST:
    mutated = copy.deepcopy(tree)
    cmp_nodes = [n for n in ast.walk(mutated)
                 if isinstance(n, ast.Compare)]
    # Find the same node by position
    for n in cmp_nodes:
        if op_idx < len(n.ops) and type(n.ops[op_idx]) in _CMP_REPLACEMENTS:
            n.ops[op_idx] = replacement_op_type()
            break
    return mutated


def _apply_sdl(tree: ast.AST, func_name: str, stmt_idx_in_body: int) -> ast.AST | None:
    """Delete statement at stmt_idx_in_body from the function body."""
    mutated = copy.deepcopy(tree)
    for node in ast.walk(mutated):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            if len(node.body) > 1 and stmt_idx_in_body < len(node.body):
                del node.body[stmt_idx_in_body]
                return mutated
    return None


def generate_mutants(
    prompt: str,
    canonical_solution: str,
    entry_point: str,
    operators: list[str],
    max_per_operator: int = 5,
    seed: int = 42,
) -> list[Mutant]:
    """Generate up to max_per_operator first-order mutants per operator.

    Returns a list of Mutant objects.  Empty list means no mutable sites found.
    """
    full_code = prompt + canonical_solution
    try:
        tree = ast.parse(full_code)
    except SyntaxError:
        return []

    rng = random.Random(seed)
    mutants: list[Mutant] = []
    counter = 0

    if "AOR" in operators:
        sites = _find_binop_sites(tree)
        rng.shuffle(sites)
        for node, site_idx in sites[:max_per_operator]:
            replacements = _ARITH_REPLACEMENTS[type(node.op)]
            new_op_type = rng.choice(replacements)
            mutated_tree = _apply_aor(tree, site_idx, new_op_type)
            try:
                code = ast.unparse(mutated_tree)
            except Exception:
                continue
            orig_op = type(node.op).__name__.lower()
            new_op = new_op_type.__name__.lower()
            mutants.append(Mutant(
                mutant_id=f"AOR_{counter}",
                operator="AOR",
                description=f"Replace {orig_op} with {new_op}",
                code=code,
            ))
            counter += 1

    if "ROR" in operators:
        sites = _find_cmp_sites(tree)
        rng.shuffle(sites)
        for cmp_node, op_idx, _ in sites[:max_per_operator]:
            replacements = _CMP_REPLACEMENTS[type(cmp_node.ops[op_idx])]
            new_op_type = rng.choice(replacements)
            mutated_tree = copy.deepcopy(tree)
            cmp_nodes = [n for n in ast.walk(mutated_tree) if isinstance(n, ast.Compare)]
            # Match by operator type at same position
            applied = False
            for cn in cmp_nodes:
                if op_idx < len(cn.ops) and type(cn.ops[op_idx]) == type(cmp_node.ops[op_idx]):
                    cn.ops[op_idx] = new_op_type()
                    applied = True
                    break
            if not applied:
                continue
            try:
                code = ast.unparse(mutated_tree)
            except Exception:
                continue
            orig_op = type(cmp_node.ops[op_idx]).__name__
            mutants.append(Mutant(
                mutant_id=f"ROR_{counter}",
                operator="ROR",
                description=f"Replace {orig_op} with {new_op_type.__name__}",
                code=code,
            ))
            counter += 1

    if "SDL" in operators:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == entry_point:
                for stmt_idx in range(min(max_per_operator, len(node.body))):
                    mutated_tree = _apply_sdl(tree, entry_point, stmt_idx)
                    if mutated_tree is None:
                        continue
                    try:
                        code = ast.unparse(mutated_tree)
                    except Exception:
                        continue
                    mutants.append(Mutant(
                        mutant_id=f"SDL_{counter}",
                        operator="SDL",
                        description=f"Delete statement {stmt_idx} in {entry_point}",
                        code=code,
                    ))
                    counter += 1
                break

    return mutants
