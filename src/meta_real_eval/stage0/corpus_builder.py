"""Generate a corpus of traditional (AOR, ROR, SDL) mutants for one task.

Each mutant is produced by applying exactly one syntactic change to the
canonical solution (first-order mutation).  The resulting code is stored as a
full executable string (prompt + mutated body) so it can be run directly in
the sandbox.

Selection strategy
------------------
A task usually offers more mutable sites than `max_per_operator` allows, so
some sampling is unavoidable.  We sample *breadth-first*: every site gets one
replacement before any site gets a second.  This keeps the corpus spread
across distinct program locations rather than piling several variants onto one
comparison, while still using the leftover budget to explore alternative
replacements when a task has few sites.  Sampling is seeded, so the corpus is
reproducible.

Mutants are deduplicated by generated source, and mutants identical to the
original are dropped, so the corpus contains no redundant entries by
construction rather than by luck.

Scope: SDL deletes top-level statements of the entry-point function only, and
never the docstring — removing a docstring cannot change behaviour, so such a
"mutant" is equivalent by construction and would only waste a differential
fuzzing run in the equivalence stage.
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
#
# Both helpers return a *flat, positionally stable* list of mutable slots.
# ast.walk is deterministic and copy.deepcopy preserves node order, so slot i
# of a tree and slot i of its deepcopy are the same program location.  That
# invariant is what lets a site be chosen on the original tree and applied to
# a fresh copy — see _apply_aor / _apply_ror.
# ---------------------------------------------------------------------------

def _binop_slots(tree: ast.AST) -> list[ast.BinOp]:
    """Every BinOp node whose operator has a replacement, in walk order."""
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.BinOp) and type(n.op) in _ARITH_REPLACEMENTS]


def _cmp_slots(tree: ast.AST) -> list[tuple[ast.Compare, int]]:
    """Every (Compare node, operator position) with a replacement, in walk order.

    A chained comparison like `a < b < c` contributes one slot per operator,
    which is why a slot is a (node, op position) pair rather than just a node.
    """
    slots: list[tuple[ast.Compare, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for op_idx, op in enumerate(node.ops):
                if type(op) in _CMP_REPLACEMENTS:
                    slots.append((node, op_idx))
    return slots


def _is_docstring(stmt: ast.stmt) -> bool:
    return (isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str))


def _deletable_stmt_indices(func: ast.FunctionDef) -> list[int]:
    """Indices of top-level statements in `func` that SDL may delete.

    Excludes the docstring (deleting it is behaviour-preserving by
    construction) and refuses to empty the body entirely.
    """
    if len(func.body) <= 1:
        return []
    return [i for i, stmt in enumerate(func.body) if not _is_docstring(stmt)]


# ---------------------------------------------------------------------------
# Mutation application
# ---------------------------------------------------------------------------

def _apply_aor(tree: ast.AST, slot_idx: int, replacement_op_type: type) -> ast.AST:
    mutated = copy.deepcopy(tree)
    _binop_slots(mutated)[slot_idx].op = replacement_op_type()
    return mutated


def _apply_ror(tree: ast.AST, slot_idx: int, replacement_op_type: type) -> ast.AST:
    mutated = copy.deepcopy(tree)
    node, op_idx = _cmp_slots(mutated)[slot_idx]
    node.ops[op_idx] = replacement_op_type()
    return mutated


def _apply_sdl(tree: ast.AST, func_name: str, stmt_idx_in_body: int) -> ast.AST | None:
    """Delete statement at stmt_idx_in_body from the named function's body."""
    mutated = copy.deepcopy(tree)
    for node in ast.walk(mutated):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            if len(node.body) > 1 and stmt_idx_in_body < len(node.body):
                del node.body[stmt_idx_in_body]
                return mutated
            return None
    return None


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def _plan_mutations(
    replacements_per_slot: list[list[type]],
    max_n: int,
    rng: random.Random,
) -> list[tuple[int, type]]:
    """Choose (slot index, replacement) pairs, breadth across slots first.

    Round 0 gives every slot one replacement; round 1 gives every slot a
    second, and so on until the budget runs out.  Slot order and each slot's
    replacement order are shuffled with the seeded rng, so which replacement a
    slot receives is reproducible but not biased toward whichever operator
    happens to be listed first in the replacement table.
    """
    order = list(range(len(replacements_per_slot)))
    rng.shuffle(order)
    shuffled: dict[int, list[type]] = {}
    for slot in order:
        reps = list(replacements_per_slot[slot])
        rng.shuffle(reps)
        shuffled[slot] = reps

    plans: list[tuple[int, type]] = []
    depth = 0
    max_depth = max((len(r) for r in replacements_per_slot), default=0)
    while len(plans) < max_n and depth < max_depth:
        for slot in order:
            if depth < len(shuffled[slot]):
                plans.append((slot, shuffled[slot][depth]))
                if len(plans) >= max_n:
                    break
        depth += 1
    return plans


# ---------------------------------------------------------------------------
# Mutant generation
# ---------------------------------------------------------------------------

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
    # Guard against redundant corpus entries: two different mutations can
    # unparse to the same source, and a mutation can be a no-op.
    original_code = ast.unparse(tree)
    seen_code: set[str] = {original_code}

    def _emit(operator: str, description: str, code: str) -> bool:
        nonlocal counter
        if code in seen_code:
            return False
        seen_code.add(code)
        mutants.append(Mutant(
            mutant_id=f"{operator}_{counter}",
            operator=operator,
            description=description,
            code=code,
        ))
        counter += 1
        return True

    if "AOR" in operators:
        slots = _binop_slots(tree)
        plans = _plan_mutations(
            [_ARITH_REPLACEMENTS[type(n.op)] for n in slots], max_per_operator, rng
        )
        for slot_idx, new_op_type in plans:
            try:
                code = ast.unparse(_apply_aor(tree, slot_idx, new_op_type))
            except Exception:
                continue
            orig_op = type(slots[slot_idx].op).__name__
            _emit("AOR", f"Replace {orig_op} with {new_op_type.__name__} "
                         f"at arithmetic site {slot_idx}", code)

    if "ROR" in operators:
        slots = _cmp_slots(tree)
        plans = _plan_mutations(
            [_CMP_REPLACEMENTS[type(node.ops[op_idx])] for node, op_idx in slots],
            max_per_operator, rng,
        )
        for slot_idx, new_op_type in plans:
            try:
                code = ast.unparse(_apply_ror(tree, slot_idx, new_op_type))
            except Exception:
                continue
            node, op_idx = slots[slot_idx]
            orig_op = type(node.ops[op_idx]).__name__
            _emit("ROR", f"Replace {orig_op} with {new_op_type.__name__} "
                         f"at comparison site {slot_idx}", code)

    if "SDL" in operators:
        func = next((n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == entry_point), None)
        if func is not None:
            indices = _deletable_stmt_indices(func)
            rng.shuffle(indices)
            for stmt_idx in indices[:max_per_operator]:
                mutated_tree = _apply_sdl(tree, entry_point, stmt_idx)
                if mutated_tree is None:
                    continue
                try:
                    code = ast.unparse(mutated_tree)
                except Exception:
                    continue
                # Record the statement kind: a deleted `return` is trivially
                # killed, so analysis needs to be able to stratify by it.
                kind = type(func.body[stmt_idx]).__name__
                _emit("SDL", f"Delete {kind} statement {stmt_idx} in {entry_point}", code)

    return mutants
