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


def _generic_arg(ann: str) -> str:
    """Text inside the outermost [...] of a generic annotation, or ''."""
    start = ann.find("[")
    if start == -1 or not ann.endswith("]"):
        return ""
    return ann[start + 1:-1].strip()


def _random_value(annotation: str, rng: random.Random) -> Any:
    """Random value matching a type annotation or an inferred type tag.

    Recurses into generic containers instead of collapsing every list-ish
    annotation to list[int]: feeding ints to a function expecting list[str]
    makes canonical and mutant raise the same TypeError, which the caller
    would then misread as "no divergence" and flag the mutant equivalent.
    """
    ann = annotation.lower().strip()
    inner = _generic_arg(ann)

    if ann.startswith(("optional[", "union[")):
        first = inner.split(",")[0].strip() if inner else ""
        return _random_value(first, rng) if first else _random_int(rng)
    if ann.startswith(("list[", "sequence[")):
        return [_random_value(inner, rng) for _ in range(rng.randint(0, 6))]
    if ann.startswith("tuple["):
        parts = [p.strip() for p in inner.split(",") if p.strip() and p.strip() != "..."]
        return tuple(_random_value(p, rng) for p in parts) if parts else (_random_int(rng),)
    if ann.startswith("dict["):
        parts = [p.strip() for p in inner.split(",")]
        key_t = parts[0] if parts else "str"
        val_t = parts[1] if len(parts) > 1 else "int"
        return {_random_value(key_t, rng): _random_value(val_t, rng)
                for _ in range(rng.randint(0, 4))}

    if ann == "bool":
        return rng.choice([True, False])
    if ann == "int":
        return _random_int(rng)
    if ann == "float":
        return _random_float(rng)
    if ann == "str":
        return _random_str(rng)
    if ann in ("list", "sequence"):
        return _random_list_int(rng)
    if ann == "tuple":
        return tuple(_random_int(rng) for _ in range(rng.randint(1, 3)))
    if ann == "dict":
        return {_random_str(rng): _random_int(rng) for _ in range(rng.randint(0, 4))}
    return _random_int(rng)


def _infer_tags(inputs: list[tuple]) -> list[str]:
    """Per-parameter type tags inferred from example inputs.

    Prefers an example that actually carries type information: the first test
    input is often an empty-container edge case (``([],)``), and an empty list
    says nothing about its element type.
    """
    arity = max(len(args) for args in inputs)
    tags: list[str] = []
    for pos in range(arity):
        values = [args[pos] for args in inputs if pos < len(args)]
        informative = next(
            (v for v in values if not (hasattr(v, "__len__") and len(v) == 0)),
            values[0] if values else None,
        )
        tags.append(_type_tag(informative) if informative is not None else "int")
    return tags


def _type_tag(value: Any) -> str:
    """Describe a concrete example value as an annotation-like tag.

    Most HumanEval signatures are unannotated, so the reliable way to learn a
    parameter's type is to look at the arguments the benchmark's own tests
    pass in, rather than guessing from a missing annotation.
    """
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, tuple):
        return f"tuple[{', '.join(_type_tag(v) for v in value)}]" if value else "tuple[int]"
    if isinstance(value, list):
        return f"list[{_type_tag(value[0])}]" if value else "list[int]"
    if isinstance(value, dict):
        if not value:
            return "dict[str, int]"
        k = next(iter(value))
        return f"dict[{_type_tag(k)}, {_type_tag(value[k])}]"
    return "int"


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


def _balanced_slice(text: str, open_idx: int) -> Optional[str]:
    """Return the text between the '(' at open_idx and its matching ')'."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i]
    return None


def _extract_test_inputs(test_code: str, entry_point: str) -> list[tuple]:
    """Pull literal argument tuples from the benchmark's own assert statements.

    These are the highest-quality inputs available: hand-written by the
    benchmark authors and type-correct by construction.

    Two things this has to get right.  HumanEval's test block is
    ``def check(candidate): assert candidate(...)`` — the calls are on the
    *parameter* name, so matching only ``entry_point(`` finds nothing on 163
    of 164 tasks.  And arguments must be scanned with balanced parentheses,
    since ``[^)]*`` truncates ``candidate([(1, 2)])`` at the first ')'.
    """
    inputs: list[tuple] = []
    seen: set[str] = set()

    for name in {"candidate", entry_point}:
        for match in re.finditer(rf"\b{re.escape(name)}\s*\(", test_code):
            arg_str = _balanced_slice(test_code, match.end() - 1)
            if arg_str is None or not arg_str.strip():
                continue
            try:
                # Benchmark-authored literals only; a non-literal (e.g. a call
                # to a helper) simply fails to eval and is skipped.
                args = eval(f"({arg_str},)")  # noqa: S307
            except Exception:
                continue
            key = repr(args)
            if key not in seen:
                seen.add(key)
                inputs.append(args)

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

    # Fill the rest randomly.  Prefer types inferred from the real test inputs
    # above — most HumanEval signatures carry no annotations, so falling back
    # to _extract_param_annotations would default every parameter to int.
    if inputs:
        tags = _infer_tags(inputs)
    else:
        full_source = task.prompt + task.canonical_solution
        tags = _extract_param_annotations(full_source, task.entry_point)

    while len(inputs) < n:
        inputs.append(tuple(_random_value(tag, rng) for tag in tags))

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
