"""D4: scenarios -- the class-level replacement for Tier 1's argument tuples.

A function under test can be fed an argument tuple; a class cannot. Stage 0
(equivalence fuzzing), RQ3 (divergence) and RQ4 (consistency assertions) all
need "the same input, given to several implementations", so for Tier 2 an
input is a **scenario**: a deterministic, straight-line sequence of
statements derived from one Pynguin test (see the Tier 2 plan, "D4").

Measured over all 1,736 tests in the corpus, every Pynguin test body is
straight-line and built from exactly four statement shapes -- ``Assign``,
``Expr``, ``Assert`` (always a ``Compare``) and ``With pytest.raises(E):``
wrapping one ``Expr`` -- with no ``if``/``for``/``while``/``try`` anywhere.
Anything else raises :class:`UnsupportedScenario` rather than being guessed
at.

Extraction keeps the *behaviour* and drops the *oracle*:

* ``var = expr`` / ``expr``           -> an ``exec`` step; its value (or the
                                         exception it raises) is observed.
* ``assert <left> <op> <right>``      -> an ``observe`` step on ``<left>``
                                         only; ``<right>`` is the reference's
                                         expected value, i.e. the oracle.
* ``with pytest.raises(E): expr``     -> a ``raises`` step; ``E`` is kept as
                                         ``expected_exc`` metadata.

An ``observe`` step whose expression does not depend on the class under test
(e.g. ``assert module_1.CO_NESTED == 16`` on the ``inspect`` module) is an
*environment observation*: it measures the interpreter, not the
implementation. It is dropped from the scenario and counted, never silently.

A scenario is an oracle-free behavioural proxy, not a semantic-equivalence
relation: two implementations "agree" on it when their observation traces
(return values / exceptions per step, plus a bounded end-of-scenario state
snapshot; see ``observe.py``) are equal outside the nondeterminism mask.
"""

from __future__ import annotations

import ast
import json
import math
import random
from dataclasses import asdict, dataclass, field, replace
from typing import Optional

from ..stage0.equivalence import _mutate_str, _random_float, _random_int

EXEC = "exec"
OBSERVE = "observe"
RAISES = "raises"


class UnsupportedScenario(ValueError):
    """The test uses a statement shape the extractor does not model."""


@dataclass(frozen=True)
class Step:
    kind: str                        # EXEC | OBSERVE | RAISES
    src: str                         # an expression, evaluated in the scenario namespace
    target: Optional[str] = None     # variable bound by an `x = expr` exec step
    expected_exc: Optional[str] = None  # RAISES only: the `E` in pytest.raises(E)


@dataclass(frozen=True)
class Scenario:
    scenario_id: str                 # "<test_name>" or "<test_name>~p<k>"
    origin_test: str
    steps: tuple[Step, ...]
    xfail: bool = False              # the origin test is expected to end in an exception
    perturbed: bool = False
    env_observations_dropped: int = 0

    def canonical(self) -> str:
        """Identity for de-duplication: the step sequence only, not the id."""
        return json.dumps([asdict(s) for s in self.steps], sort_keys=True)


@dataclass
class ScenarioPool:
    header: str                      # the test file's imports (binds module_0, ...)
    scenarios: list[Scenario] = field(default_factory=list)
    n_original: int = 0
    n_perturbed: int = 0
    perturbations_per_original_cap: int = 0
    target_size: int = 0

    @property
    def n_unique(self) -> int:
        return len(self.scenarios)

    def composition(self) -> dict:
        return {
            "target_size": self.target_size,
            "n_original": self.n_original,
            "n_perturbed": self.n_perturbed,
            "n_unique": self.n_unique,
            "perturbations_per_original_cap": self.perturbations_per_original_cap,
            "low_scenario_diversity": self.n_original < 3,
        }


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _sut_alias(tree: ast.Module, module_name: str) -> str:
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name:
                    return alias.asname or alias.name
    raise UnsupportedScenario(f"test file never imports the module under test {module_name!r}")


def _header(tree: ast.Module) -> str:
    """Top-level imports, minus pytest (the scenario runner never needs it)."""
    kept = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [a for a in node.names if a.name != "pytest"]
            if names:
                kept.append(ast.unparse(ast.Import(names=names)))
        elif isinstance(node, ast.ImportFrom) and node.module != "pytest":
            kept.append(ast.unparse(node))
    return "\n".join(kept) + ("\n" if kept else "")


def _is_raises_with(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.With)
        and len(node.items) == 1
        and isinstance(node.items[0].context_expr, ast.Call)
        and ast.unparse(node.items[0].context_expr.func) in ("pytest.raises", "raises")
    )


def _is_xfail(fn: ast.FunctionDef) -> bool:
    return any("xfail" in ast.unparse(d) for d in fn.decorator_list)


def _extract_one(fn: ast.FunctionDef, sut: str) -> Scenario:
    tainted = {sut}
    steps: list[Step] = []
    dropped = 0

    for stmt in fn.body:
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                raise UnsupportedScenario(f"{fn.name}: non-simple assignment {ast.unparse(stmt)!r}")
            target = stmt.targets[0].id
            if _names(stmt.value) & tainted:
                tainted.add(target)
            steps.append(Step(EXEC, ast.unparse(stmt.value), target=target))
        elif isinstance(stmt, ast.Expr):
            steps.append(Step(EXEC, ast.unparse(stmt.value)))
        elif isinstance(stmt, ast.Assert):
            observed = stmt.test.left if isinstance(stmt.test, ast.Compare) else stmt.test
            if _names(observed) & tainted:
                steps.append(Step(OBSERVE, ast.unparse(observed)))
            else:
                dropped += 1
        elif _is_raises_with(stmt):
            call = stmt.items[0].context_expr
            expected = ast.unparse(call.args[0]) if call.args else None
            for inner in stmt.body:
                if not isinstance(inner, ast.Expr):
                    raise UnsupportedScenario(f"{fn.name}: non-expression inside pytest.raises")
                steps.append(Step(RAISES, ast.unparse(inner.value), expected_exc=expected))
        else:
            raise UnsupportedScenario(f"{fn.name}: unsupported statement {type(stmt).__name__}")

    return Scenario(
        scenario_id=fn.name,
        origin_test=fn.name,
        steps=tuple(steps),
        xfail=_is_xfail(fn),
        env_observations_dropped=dropped,
    )


def extract_scenarios(test_source: str, module_name: str) -> tuple[str, list[Scenario]]:
    """Return ``(header, scenarios)``: one scenario per ``test*`` function, in
    source order. ``module_name`` is the module under test (``snippet_N``)."""
    tree = ast.parse(test_source)
    sut = _sut_alias(tree, module_name)
    scenarios = [
        _extract_one(node, sut)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
    ]
    return _header(tree), scenarios


# ---------------------------------------------------------------------------
# Perturbation and the pool
# ---------------------------------------------------------------------------

def _perturb_constant(value, rng: random.Random):
    """One local change to a literal, reusing Stage 0's Tier 1 generators."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return rng.choice([value + 1, value - 1, -value, _random_int(rng)])
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return _random_float(rng)
        return rng.choice([value + rng.uniform(-1.0, 1.0), -value, _random_float(rng)])
    if isinstance(value, str):
        return _mutate_str(value, rng)
    return value  # None, bytes, Ellipsis: not perturbed


class _ConstantSlots(ast.NodeVisitor):
    def __init__(self) -> None:
        self.slots: list[ast.Constant] = []

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, (bool, int, float, str)):
            self.slots.append(node)


def perturb(scenario: Scenario, rng: random.Random, k: int) -> Optional[Scenario]:
    """Perturb exactly one literal in one EXEC/RAISES step.

    Observe steps are never perturbed: their literals (e.g. format strings in
    a type check) are part of how a value is read, not part of the input.
    Returns None if the scenario has no perturbable literal or the change is
    a no-op.
    """
    candidates: list[tuple[int, int]] = []  # (step index, slot index)
    parsed: dict[int, ast.Expression] = {}
    for i, step in enumerate(scenario.steps):
        if step.kind == OBSERVE:
            continue
        tree = ast.parse(step.src, mode="eval")
        finder = _ConstantSlots()
        finder.visit(tree)
        parsed[i] = tree
        candidates.extend((i, j) for j in range(len(finder.slots)))
    if not candidates:
        return None

    step_i, slot_j = rng.choice(candidates)
    tree = parsed[step_i]
    finder = _ConstantSlots()
    finder.visit(tree)
    node = finder.slots[slot_j]
    new_value = _perturb_constant(node.value, rng)
    if new_value == node.value and type(new_value) is type(node.value):
        return None
    node.value = new_value

    steps = list(scenario.steps)
    steps[step_i] = replace(steps[step_i], src=ast.unparse(tree))
    return replace(
        scenario,
        scenario_id=f"{scenario.origin_test}~p{k}",
        steps=tuple(steps),
        perturbed=True,
    )


def build_pool(
    header: str,
    originals: list[Scenario],
    target_size: int,
    seed: int,
    max_attempts_per_slot: int = 20,
) -> ScenarioPool:
    """The D4 pool, exactly as fixed in plan rev. 2.

    1. Every original scenario first; originals are never removed.
    2. Only if the pool is below ``target_size``: seeded single-literal
       perturbations, round-robin across originals, each original contributing
       at most ``ceil((N - n_orig) / n_orig)``. A perturbation identical (by
       canonical step sequence) to anything already in the pool is discarded.

    The result can be smaller than ``target_size`` (few or literal-free
    originals); the effective size is reported via :meth:`ScenarioPool.composition`.
    """
    rng = random.Random(seed)
    pool = ScenarioPool(header=header, target_size=target_size)
    seen: set[str] = set()
    for s in originals:
        if s.canonical() not in seen:
            seen.add(s.canonical())
            pool.scenarios.append(s)
    pool.n_original = len(pool.scenarios)

    n_orig = pool.n_original
    if n_orig == 0 or n_orig >= target_size:
        return pool

    cap = math.ceil((target_size - n_orig) / n_orig)
    pool.perturbations_per_original_cap = cap
    produced = {s.origin_test: 0 for s in pool.scenarios}
    exhausted: set[str] = set()
    originals_in_pool = list(pool.scenarios)
    counter = 0

    while len(pool.scenarios) < target_size and len(exhausted) < n_orig:
        for orig in originals_in_pool:
            if len(pool.scenarios) >= target_size:
                break
            name = orig.origin_test
            if name in exhausted:
                continue
            if produced[name] >= cap:
                exhausted.add(name)
                continue
            added = False
            for _ in range(max_attempts_per_slot):
                counter += 1
                candidate = perturb(orig, rng, counter)
                if candidate is None:
                    continue
                key = candidate.canonical()
                if key in seen:
                    continue
                seen.add(key)
                pool.scenarios.append(candidate)
                produced[name] += 1
                added = True
                break
            if not added:
                exhausted.add(name)

    pool.n_perturbed = len(pool.scenarios) - n_orig
    return pool
