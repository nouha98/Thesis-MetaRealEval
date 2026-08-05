"""Equivalence filtering via differential execution.

A mutant is flagged as *likely-equivalent* when it produces identical outputs
to the canonical solution on all N sampled inputs.  Two passes are made:

1. Fast AST check  — if the unparses are identical the mutant is trivially
                     equivalent (no code changed) and skipped early.
2. Execution check — run both on N random inputs; any output divergence
                     means the mutant is non-equivalent.

Limitations
-----------
- We only sample N inputs, so we can miss divergence on rare edge cases.
  The larger N, the more confidence (default 500 as per the thesis plan).
- Input generation is best-effort: we infer types from the function signature
  and generate plausible random values.  Complex types fall back to the
  task's own test-case inputs extracted from the ``test`` block.
"""

from __future__ import annotations

import ast
import inspect
import random
import re
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any, Optional

from ..core.sandbox import execute
from ..core.data_loader import HumanEvalTask
from .corpus_builder import Mutant


@dataclass
class EquivResult:
    mutant_id: str
    is_equivalent: bool
    reason: str          # "ast_identical" | "no_divergence" | "diverged"
    n_inputs_tested: int


# ---------------------------------------------------------------------------
# Random input generation
# ---------------------------------------------------------------------------

def _random_int(rng: random.Random) -> int:
    return rng.randint(-100, 100)


def _random_float(rng: random.Random) -> float:
    return rng.uniform(-100.0, 100.0)


def _random_str(rng: random.Random) -> str:
    length = rng.randint(0, 10)
    chars = "abcdefghijklmnopqrstuvwxyz 0123456789"
    return "".join(rng.choice(chars) for _ in range(length))


def _random_list_int(rng: random.Random) -> list[int]:
    length = rng.randint(0, 8)
    return [_random_int(rng) for _ in range(length)]


def _random_value(annotation: str, rng: random.Random) -> Any:
    ann = annotation.lower().strip()
    if ann in ("int",):
        return _random_int(rng)
    if ann in ("float",):
        return _random_float(rng)
    if ann in ("str",):
        return _random_str(rng)
    if "list" in ann:
        return _random_list_int(rng)
    if ann in ("bool",):
        return rng.choice([True, False])
    # Default: try int
    return _random_int(rng)


def _extract_param_annotations(func_source: str, entry_point: str) -> list[str]:
    """Return a list of annotation strings for each parameter (excluding self)."""
    try:
        tree = ast.parse(func_source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == entry_point:
                annotations = []
                for arg in node.args.args:
                    if arg.annotation:
                        annotations.append(ast.unparse(arg.annotation))
                    else:
                        annotations.append("int")  # fallback
                return annotations
    except Exception:
        pass
    return ["int"]  # single param fallback


def _extract_test_inputs(test_code: str, entry_point: str) -> list[tuple]:
    """Pull literal argument tuples from assert calls in the test block.

    Matches patterns like: assert entry_point(a, b, c) == ...
    """
    pattern = re.compile(
        rf"{re.escape(entry_point)}\(([^)]*)\)",
        re.MULTILINE,
    )
    inputs = []
    for match in pattern.finditer(test_code):
        try:
            args = eval(f"({match.group(1)},)")  # noqa: S307
            inputs.append(args)
        except Exception:
            continue
    return inputs


def _generate_inputs(
    task: HumanEvalTask,
    n: int,
    seed: int,
) -> list[tuple]:
    """Return up to n input tuples for the task's entry-point function."""
    rng = random.Random(seed)

    # Start with test-derived inputs for maximum coverage signal
    inputs = _extract_test_inputs(task.test, task.entry_point)

    # Fill remaining with random values
    full_source = task.prompt + task.canonical_solution
    annotations = _extract_param_annotations(full_source, task.entry_point)
    while len(inputs) < n:
        inputs.append(tuple(_random_value(ann, rng) for ann in annotations))

    return inputs[:n]


# ---------------------------------------------------------------------------
# Equivalence check
# ---------------------------------------------------------------------------

# Distinct from any real output or error string. A timeout means "we don't
# know what this would have produced" — it must never compare equal to
# another timeout (canonical vs. mutant timing out for unrelated reasons is
# not evidence of equivalence) or be used to confirm equivalence.
TIMEOUT = "__timeout__"


def _run_one(code: str, entry_point: str, args: tuple, timeout_s: float) -> Any:
    """Return the output for a single input, or a sentinel string on error/timeout."""
    call = f"\n__result__ = {entry_point}(*{repr(args)})\nprint(repr(__result__))"
    result = execute(code, call, timeout_s=timeout_s)
    if result.timed_out:
        return TIMEOUT
    if not result.passed:
        return f"__error__:{result.stderr[:60]}"
    return result.stdout.strip()


def compute_canonical_outputs(
    task: HumanEvalTask,
    n_fuzz_inputs: int = 500,
    timeout_s: float = 5.0,
    seed: int = 42,
    cpu_workers: int = 1,
) -> list[Any]:
    """Run the canonical solution on the fuzz inputs once, for reuse across all mutants.

    The canonical solution and the generated inputs are identical for every
    mutant of a task, so callers checking many mutants should compute this
    once per task rather than paying for it inside check_equivalence again.

    Unlike check_equivalence, this always executes every input (there is no
    divergence to short-circuit on), so it is the one place where spreading
    the n_fuzz_inputs subprocess spawns across cpu_workers processes pays off
    unconditionally.
    """
    canonical_code = task.prompt + task.canonical_solution
    inputs = _generate_inputs(task, n_fuzz_inputs, seed)
    if cpu_workers <= 1:
        return [_run_one(canonical_code, task.entry_point, args, timeout_s) for args in inputs]

    with ProcessPoolExecutor(max_workers=cpu_workers) as pool:
        return list(pool.map(
            _run_one,
            [canonical_code] * len(inputs),
            [task.entry_point] * len(inputs),
            inputs,
            [timeout_s] * len(inputs),
        ))


def check_equivalence(
    task: HumanEvalTask,
    mutant: Mutant,
    n_fuzz_inputs: int = 500,
    timeout_s: float = 5.0,
    seed: int = 42,
    canon_outs: Optional[list[Any]] = None,
) -> EquivResult:
    """Return an EquivResult classifying this mutant.

    canon_outs can be precomputed via compute_canonical_outputs() and shared
    across mutants of the same task; if omitted it is computed here.
    """
    canonical_code = task.prompt + task.canonical_solution

    # 1. Fast AST check
    try:
        canon_tree = ast.unparse(ast.parse(canonical_code))
        mut_tree = ast.unparse(ast.parse(mutant.code))
        if canon_tree == mut_tree:
            return EquivResult(mutant.mutant_id, True, "ast_identical", 0)
    except SyntaxError:
        pass

    # 2. Differential execution, one input at a time, stopping at first divergence.
    # A mutant that infinite-loops only needs to time out once to prove
    # non-equivalence rather than on every remaining fuzz input.
    inputs = _generate_inputs(task, n_fuzz_inputs, seed)
    if canon_outs is None:
        canon_outs = [_run_one(canonical_code, task.entry_point, args, timeout_s) for args in inputs]

    n_tested = 0
    for i, args in enumerate(inputs):
        if canon_outs[i] == TIMEOUT:
            # The canonical solution itself didn't finish on this input, so it
            # can't tell us anything about the mutant — skip without spending
            # a mutant-side timeout wait on it.
            continue
        n_tested += 1
        m_out = _run_one(mutant.code, task.entry_point, args, timeout_s)
        if m_out == TIMEOUT or m_out != canon_outs[i]:
            return EquivResult(mutant.mutant_id, False, "diverged", i + 1)

    if n_tested == 0:
        return EquivResult(mutant.mutant_id, True, "no_testable_inputs", 0)
    return EquivResult(mutant.mutant_id, True, "no_divergence", n_tested)
