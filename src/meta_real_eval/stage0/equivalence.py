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
import hashlib
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
    # repr() of the input that settled a "diverged" verdict, so a verdict can be
    # re-examined later without re-deriving the seeded input stream.
    diverging_input: Optional[str] = None


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


def _mutate_str(s: str, rng: random.Random) -> str:
    """Perturb a real example string, keeping it in the task's own domain.

    Sampling strings from a fixed alphabet never produces a bracket for a
    bracket-matching task or a well-formed "mm-dd-yyyy" for a date parser, so
    the padding inputs for such tasks all take the same early-exit path and
    cannot distinguish a mutant from the canonical solution.  Perturbing an
    input the benchmark itself uses keeps the structure and varies the detail,
    which is where the interesting divergences live (a trailing zero after a
    decimal point, one bracket too many).
    """
    if not s:
        return _random_str(rng)
    i = rng.randrange(len(s))
    op = rng.randrange(5)
    if op == 0:                                   # delete a character
        return s[:i] + s[i + 1:]
    if op == 1:                                   # duplicate a character
        return s[:i] + s[i] + s[i:]
    if op == 2 and len(s) > 1:                    # swap two adjacent characters
        j = min(i + 1, len(s) - 1)
        return s[:i] + s[j] + s[i] + s[j + 1:]
    if op == 3:                                   # replace, from this string's own alphabet
        return s[:i] + rng.choice(s) + s[i + 1:]
    return s + rng.choice(s)                      # extend (e.g. "14.5" -> "14.50")


def _string_pool(inputs: list[tuple]) -> list[str]:
    """Every string appearing anywhere in the captured example inputs.

    Flattened through containers so a ``list[str]`` parameter contributes its
    elements too -- HumanEval/119 passes ``['()(' , ')']``, and the brackets
    are only reachable from inside the list.
    """
    pool: list[str] = []

    def walk(v: Any) -> None:
        if isinstance(v, str):
            pool.append(v)
        elif isinstance(v, (list, tuple, set)):
            for item in v:
                walk(item)
        elif isinstance(v, dict):
            for k, item in v.items():
                walk(k)
                walk(item)

    walk(inputs)
    return pool


def _random_list_int(rng: random.Random) -> list[int]:
    length = rng.randint(0, 8)
    return [_random_int(rng) for _ in range(length)]


def _generic_arg(ann: str) -> str:
    """Text inside the outermost [...] of a generic annotation, or ''."""
    start = ann.find("[")
    if start == -1 or not ann.endswith("]"):
        return ""
    return ann[start + 1:-1].strip()


def _random_value(annotation: str, rng: random.Random,
                  str_pool: Optional[list[str]] = None) -> Any:
    """Random value matching a type annotation or an inferred type tag.

    Recurses into generic containers instead of collapsing every list-ish
    annotation to list[int]: feeding ints to a function expecting list[str]
    makes canonical and mutant raise the same TypeError, which the caller
    would then misread as "no divergence" and flag the mutant equivalent.

    ``str_pool`` carries the strings the benchmark's own tests use, so string
    values are produced by perturbing a real example rather than by sampling a
    fixed alphabet; see _mutate_str for why that matters.
    """
    ann = annotation.lower().strip()
    inner = _generic_arg(ann)

    if ann.startswith(("optional[", "union[")):
        first = inner.split(",")[0].strip() if inner else ""
        return _random_value(first, rng, str_pool) if first else _random_int(rng)
    if ann.startswith(("list[", "sequence[")):
        return [_random_value(inner, rng, str_pool) for _ in range(rng.randint(0, 6))]
    if ann.startswith("tuple["):
        parts = [p.strip() for p in inner.split(",") if p.strip() and p.strip() != "..."]
        return tuple(_random_value(p, rng, str_pool) for p in parts) if parts else (_random_int(rng),)
    if ann.startswith("dict["):
        parts = [p.strip() for p in inner.split(",")]
        key_t = parts[0] if parts else "str"
        val_t = parts[1] if len(parts) > 1 else "int"
        return {_random_value(key_t, rng, str_pool): _random_value(val_t, rng, str_pool)
                for _ in range(rng.randint(0, 4))}

    if ann == "bool":
        return rng.choice([True, False])
    if ann == "int":
        return _random_int(rng)
    if ann == "float":
        return _random_float(rng)
    if ann == "str":
        return _random_text(rng, str_pool)
    if ann in ("list", "sequence"):
        return _random_list_int(rng)
    if ann == "tuple":
        return tuple(_random_int(rng) for _ in range(rng.randint(1, 3)))
    if ann == "dict":
        return {_random_text(rng, str_pool): _random_int(rng) for _ in range(rng.randint(0, 4))}
    return _random_int(rng)


def _random_text(rng: random.Random, str_pool: Optional[list[str]]) -> str:
    """A string input: a perturbed real example when we have one, else random."""
    if str_pool:
        return _mutate_str(rng.choice(str_pool), rng)
    return _random_str(rng)


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


_CAPTURE_LIMIT = 200          # more than any HumanEval check() needs
_CAPTURE_TIMEOUT_S = 10.0
_CAPTURE_CACHE: dict[str, list[tuple]] = {}

# Run the benchmark's own check() with `candidate` bound to a proxy that records
# what it is called with.  Scraping the source for literal argument tuples
# instead (see _extract_test_inputs) misses every call whose argument is an
# expression rather than a literal -- HumanEval/32, /38 and /50 pass the result
# of a helper defined in the prompt, so scraping recovers zero inputs for them
# and the equivalence verdict falls back entirely on random padding.  Arguments
# are deep-copied at call time because some check() bodies mutate them
# afterwards, which would otherwise corrupt the record.
_CAPTURE_HARNESS = '''
import copy as _copy, sys as _sys, random as _random
# Some check() bodies build their inputs with the random module (HumanEval/38
# draws 100 fresh strings per run), so the captured set -- and with it RQ3's
# shared input space -- would differ on every run unless the draw is pinned.
_random.seed({seed})
_captured = []
_real_candidate = {entry}
def _recording_candidate(*args, **kwargs):
    if not kwargs and len(_captured) < {limit}:
        try:
            _captured.append(_copy.deepcopy(args))
        except Exception:
            pass
    return _real_candidate(*args, **kwargs)
try:
    check(_recording_candidate)
except BaseException:
    pass
for _a in _captured:
    try:
        _line = repr(_a)
    except Exception:
        continue
    if len(_line) <= 5000:
        _sys.stdout.write("__ARG__" + _line + "\\n")
'''


def _capture_test_inputs(task: HumanEvalTask, seed: int = 42,
                         timeout_s: float = _CAPTURE_TIMEOUT_S) -> list[tuple]:
    """Argument tuples the task's own check() actually calls the entry point with.

    Only tuples that round-trip through ast.literal_eval are kept: _run_one
    replays an input by interpolating repr(args) into generated source, so an
    argument that cannot be read back from its repr is not replayable.
    """
    # Keyed by content, not task_id: two different tasks sharing an id (as test
    # fixtures do) must never be served each other's inputs. For the real
    # corpus an id maps to exactly one content, so results are unchanged.
    cache_key = hashlib.sha256("\x00".join(
        (task.prompt, task.canonical_solution, task.test, task.entry_point, str(seed))
    ).encode("utf-8")).hexdigest()
    cached = _CAPTURE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    harness = _CAPTURE_HARNESS.format(entry=task.entry_point, limit=_CAPTURE_LIMIT, seed=seed)
    result = execute(task.prompt + task.canonical_solution, task.test + harness, timeout_s)

    inputs: list[tuple] = []
    seen: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.startswith("__ARG__"):
            continue
        payload = line[len("__ARG__"):]
        try:
            args = ast.literal_eval(payload)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            continue
        if isinstance(args, tuple) and payload not in seen:
            seen.add(payload)
            inputs.append(args)

    _CAPTURE_CACHE[cache_key] = inputs
    return inputs


def _generate_inputs(
    task: HumanEvalTask,
    n: int,
    seed: int,
) -> list[tuple]:
    """Return up to n input tuples for the task's entry-point function."""
    rng = random.Random(seed)

    # Start with test-derived inputs for maximum coverage signal.  Capture them
    # by running check(); fall back to scraping its source if that yields
    # nothing (e.g. a check() that cannot run), so no task ends up worse off.
    captured = _capture_test_inputs(task, seed)
    if not captured:
        captured = _extract_test_inputs(task.test, task.entry_point)
    inputs = list(captured)      # copy: _capture_test_inputs hands back a cached list

    # Fill the rest randomly.  Prefer types inferred from the real test inputs
    # above — most HumanEval signatures carry no annotations, so falling back
    # to _extract_param_annotations would default every parameter to int.
    if inputs:
        tags = _infer_tags(inputs)
    else:
        full_source = task.prompt + task.canonical_solution
        tags = _extract_param_annotations(full_source, task.entry_point)

    str_pool = _string_pool(inputs)
    while len(inputs) < n:
        inputs.append(tuple(_random_value(tag, rng, str_pool) for tag in tags))

    return inputs[:n]


# ---------------------------------------------------------------------------
# Equivalence check
# ---------------------------------------------------------------------------

# Distinct from any real output or error string. A timeout means "we don't
# know what this would have produced" — it must never compare equal to
# another timeout (canonical vs. mutant timing out for unrelated reasons is
# not evidence of equivalence) or be used to confirm equivalence.
TIMEOUT = "__timeout__"


def _error_signature(stderr: str) -> str:
    """A comparably distinctive tag for a subprocess failure.

    Every Python traceback opens with the same ~60-char boilerplate
    ("Traceback (most recent call last):\n  File "<string>", line N, in ...")
    regardless of what actually went wrong, so truncating stderr from the
    *front* collapses almost any two distinct exceptions to the same string —
    a mutant raising IndexError would then compare equal to a canonical
    solution raising ZeroDivisionError on the same input and be misread as
    "no divergence". The exception type and message are on the last non-blank
    line instead, so anchor there.
    """
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    return lines[-1][:200] if lines else stderr.strip()[:200]


def _run_one(code: str, entry_point: str, args: tuple, timeout_s: float) -> Any:
    """Return the output for a single input, or a sentinel string on error/timeout."""
    call = f"\n__result__ = {entry_point}(*{repr(args)})\nprint(repr(__result__))"
    result = execute(code, call, timeout_s=timeout_s)
    if result.timed_out:
        return TIMEOUT
    if not result.passed:
        return f"__error__:{_error_signature(result.stderr)}"
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
            return EquivResult(mutant.mutant_id, False, "diverged", i + 1, repr(args))

    # 3. Before accepting "equivalent", let the benchmark's own suite veto it.
    #
    # Differential fuzzing calls the entry point only, so it cannot see a fault
    # seeded in a helper the prompt defines ahead of it -- HumanEval/38 and /50
    # mutate encode_cyclic/encode_shift, which check() calls to build its input
    # while _run_one never calls it at all. Sampling more inputs cannot fix
    # that; it is a scope mismatch, not a coverage gap.
    #
    # A mutant the suite kills is non-equivalent by definition: equivalence
    # means behaving identically to the canonical solution, and the suite has
    # just distinguished them. Applying this only on the equivalent path keeps
    # it cheap (most mutants diverge and never reach here) and keeps it
    # one-directional -- the suite can add mutants to the population but never
    # remove one, so survival is still decided by fuzzing alone and the kill
    # rate is not measured against itself.
    if _suite_kills(task, mutant, timeout_s):
        return EquivResult(mutant.mutant_id, False, "suite_kills", n_tested)

    if n_tested == 0:
        return EquivResult(mutant.mutant_id, True, "no_testable_inputs", 0)
    return EquivResult(mutant.mutant_id, True, "no_divergence", n_tested)


def _suite_kills(task: HumanEvalTask, mutant: Mutant, timeout_s: float) -> bool:
    """True if the task's own test suite fails on this mutant."""
    result = execute(mutant.code, f"{task.test}\ncheck({task.entry_point})\n", timeout_s)
    return not result.passed and not result.timed_out


# ---------------------------------------------------------------------------
# Benchmark-agnostic equivalence check (D4/D6 scenarios instead of argument
# tuples; see the Tier 2 plan). These parallel compute_canonical_outputs /
# check_equivalence / _suite_kills above exactly, step for step, so the only
# change for HumanEval is which function computes an "output": nothing above
# this point is touched, and rq1/runner.py keeps calling the Tier 1-only
# versions unchanged. stage0/runner.py calls these.
#
# Two things the Tier 1 functions get "for free" from their shape and that
# the generic versions have to earn back explicitly, or Stage 0 would get
# slower under the abstraction without anyone deciding that on purpose:
#
#   early exit   check_equivalence calls _run_one one input at a time and
#                returns at the first divergence. bench.observe() computes a
#                whole pool at once (Tier 2's scenario runner is far cheaper
#                run as one batch than one subprocess per scenario), so the
#                per-mutant loop below uses bench.observe_one() instead --
#                see Benchmark.observe_one's docstring.
#   parallelism  compute_canonical_outputs spreads its (always-exhaustive,
#                nothing to early-exit on) run across cpu_workers. The
#                generic path keeps this by asking bench.observe() for the
#                whole pool in one call; HumanEvalBenchmark.observe()
#                reproduces the same ProcessPoolExecutor internally.
# ---------------------------------------------------------------------------

def compute_canonical_observations(
    bench,
    task,
    n_fuzz_inputs: int = 500,
    timeout_s: float = 5.0,
    seed: int = 42,
):
    """Generic compute_canonical_outputs: returns (pool, observations).

    The pool is returned alongside the observations (not just the inputs, as
    compute_canonical_outputs returns) because check_equivalence_generic
    needs it again -- a Tier 2 InputPool carries the scenario header, which a
    bare list of items does not.
    """
    pool = bench.input_pool(task, n_fuzz_inputs, seed)
    observations = bench.observe(task, task.reference_code, pool, timeout_s) if pool.items else []
    return pool, observations


def check_equivalence_generic(
    cfg,
    task,
    mutant: Mutant,
    n_fuzz_inputs: int = 500,
    timeout_s: float = 5.0,
    seed: int = 42,
    pool=None,
    canon_obs=None,
) -> EquivResult:
    """Generic check_equivalence. Reproduces it exactly via HumanEvalBenchmark
    -- see tests/test_stage0/test_equivalence_adapter.py.

    Takes ``cfg``, not a constructed benchmark: this is submitted to a
    ProcessPoolExecutor per mutant (mirroring check_equivalence's own calling
    convention), and get_benchmark(cfg) is cheap to reconstruct in the worker
    -- building it touches no I/O, since everything a benchmark's run_suite /
    build_solution / mutation_source need already travels on ``task``.
    """
    from ..benchmarks import get_benchmark  # local: avoids a module import cycle at load time
    bench = get_benchmark(cfg)

    # 1. Fast AST check.
    try:
        canon_tree = ast.unparse(ast.parse(bench.mutation_source(task)))
        mut_tree = ast.unparse(ast.parse(mutant.code))
        if canon_tree == mut_tree:
            return EquivResult(mutant.mutant_id, True, "ast_identical", 0)
    except SyntaxError:
        pass

    # 2. Differential execution, one input at a time, stopping at first divergence.
    if pool is None or canon_obs is None:
        pool, canon_obs = compute_canonical_observations(bench, task, n_fuzz_inputs, timeout_s, seed)

    n_tested = 0
    for i in range(len(pool.items)):
        if bench.is_timeout(canon_obs[i]):
            continue
        n_tested += 1
        m_obs = bench.observe_one(task, mutant.code, pool, i, timeout_s)
        if bench.is_timeout(m_obs) or not bench.observations_agree(canon_obs[i], m_obs):
            return EquivResult(mutant.mutant_id, False, "diverged", i + 1, repr(pool.items[i]))

    # 3. Suite veto.
    if _suite_kills_generic(bench, task, mutant, timeout_s):
        return EquivResult(mutant.mutant_id, False, "suite_kills", n_tested)

    if n_tested == 0:
        return EquivResult(mutant.mutant_id, True, "no_testable_inputs", 0)
    return EquivResult(mutant.mutant_id, True, "no_divergence", n_tested)


def _suite_kills_generic(bench, task, mutant: Mutant, timeout_s: float) -> bool:
    """True if the task's own test suite fails on this mutant. Mirrors
    _suite_kills: a timeout is "we don't know", never a kill."""
    result = bench.run_suite(task, mutant.code, timeout_s)
    return not result.passed_all and not bench.suite_timed_out(result)
