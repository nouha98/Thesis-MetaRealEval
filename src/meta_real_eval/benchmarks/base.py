"""The benchmark adapter contract.

Architectural principle (non-negotiable, enforced by tests/test_architecture.py):

    Benchmark-specific code may know whether a task is a function or a
    class. RQ, statistics and analysis code must not.

Everything that differs between Tier 1 (HumanEval, one function, a
``check(candidate)`` assert block) and Tier 2 (RealClassEval, one class, a
Pynguin pytest suite) lives behind the protocols below. RQ code calls these
methods and may branch on *declared capabilities* -- e.g. whether a
:class:`DegradedSuite` carries a ``subset`` (rescore stored outcomes) or a
rewritten ``test_code`` (re-execute) -- never on a benchmark name.

The protocol is split into small capabilities rather than one large
interface; :class:`Benchmark` composes them. Each method is an operation that
is genuinely different per benchmark -- anything that is not belongs in the
shared RQ code, not here.

Observations are deliberately opaque to callers: a Tier 1 observation is a
``repr`` string, a Tier 2 observation is a trace dict. Callers compare them
only through :meth:`ScenarioProvider.observations_agree` and classify them
only through :meth:`ScenarioProvider.is_timeout` / ``is_error``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Protocol, runtime_checkable

from .outcomes import TestOutcome

Observation = Any
SDLScope = Callable[[ast.Module], list[ast.FunctionDef]]


@dataclass(frozen=True)
class Task:
    """One benchmark task, benchmark-agnostic.

    ``prompt`` is what the model sees (Tier 1: signature + docstring; Tier 2:
    the class skeleton). ``reference_code`` is the full executable reference.
    ``target`` is the entry-point function (Tier 1) or the class name
    (Tier 2). ``module_name`` is the import name the tests use for the code
    under test (Tier 2: ``snippet_N``; Tier 1: None, the code is inlined).
    ``meta`` carries benchmark-specific extras (complexity metrics, the M0
    gate's verdicts); ``raw`` the underlying legacy record, for adapters that
    delegate to existing functions.
    """

    task_id: str
    task_index: int
    label: str
    prompt: str
    reference_code: str
    test_code: str
    target: str
    split: Optional[str] = None
    module_name: Optional[str] = None
    meta: Mapping[str, Any] = field(default_factory=dict)
    raw: Any = field(default=None, compare=False, repr=False)


@dataclass
class SuiteResult:
    """The outcome of running a test suite against one implementation.

    ``outcomes`` is per test (Tier 1 has exactly one, ``"check"``).
    ``scores`` always holds ``primary`` and ``passed_all`` (as 1.0 / 0.0),
    plus whatever sensitivity metrics the benchmark defines; downstream code
    reads ``scores[cfg.rq2.primary_metric]`` and never asks which benchmark
    produced it.
    """

    outcomes: dict[str, TestOutcome]
    scores: dict[str, Optional[float]]

    @property
    def passed_all(self) -> bool:
        return bool(self.scores.get("passed_all"))

    @property
    def primary(self) -> Optional[float]:
        return self.scores.get("primary")


@dataclass(frozen=True)
class DegradedSuite:
    """A weakened -- or augmented -- test suite for RQ4.

    For plain degradation, exactly one of ``subset`` / ``test_code`` is set:

    ``subset``    whole tests removed. Scores can be recomputed from stored
                  per-test outcomes restricted to the subset, with no
                  re-execution (valid because the M0 gate guarantees every
                  valid test is order-independent).
    ``test_code`` the suite was rewritten in place (Tier 1 removes asserts
                  inside ``check``), so it must be re-executed.

    :meth:`SuiteDegrader.augmented_suite` (consistency assertions appended)
    may set BOTH at once for a class-level benchmark: ``test_code`` carries
    the extended source and ``subset`` the exact names to run from it (the
    surviving degraded names plus the new ones) -- see ``extra_valid``.

    ``extra_valid`` names tests outside the M0 gate's own valid-test list
    that should nonetheless count toward the primary score (the consistency
    assertions a benchmark's own ``consistency_suite`` adds). None for plain
    degradation; Tier 1 has no per-named-test scoring concept and ignores it.
    """

    level: float
    subset: Optional[frozenset[str]] = None
    test_code: Optional[str] = None
    extra_valid: Optional[frozenset[str]] = None


@dataclass
class InputPool:
    """Shared inputs for differential execution (Stage 0, RQ3, RQ4).

    ``items`` are argument tuples (Tier 1) or scenarios (Tier 2); ``header``
    is the import prelude a scenario runs under (Tier 2 only).
    """

    items: list[Any]
    header: str = ""
    composition: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Capability protocols
# ---------------------------------------------------------------------------

@runtime_checkable
class TaskSource(Protocol):
    name: str

    def load_tasks(self, indices: Optional[list[int]] = None) -> list[Task]: ...

    def generation_messages(self, task: Task, prompt_variant: str) -> list[dict]: ...


@runtime_checkable
class Executor(Protocol):
    def build_solution(self, task: Task, completion: str) -> str: ...

    def run_suite(
        self,
        task: Task,
        code: str,
        timeout_s: float,
        suite: Optional[DegradedSuite] = None,
    ) -> SuiteResult: ...

    def score_outcomes(
        self,
        task: Task,
        outcomes: dict[str, TestOutcome],
        subset: Optional[frozenset[str]] = None,
    ) -> dict[str, Optional[float]]: ...

    def suite_timed_out(self, result: SuiteResult) -> bool:
        """True if any part of ``result`` hit the execution timeout.

        A timeout means "we don't know what this would have done", which is
        different from "it ran and failed" -- Stage 0's suite veto
        (``stage0.equivalence._suite_kills`` and its generic counterpart)
        must never count a timeout as a kill. ``SuiteResult.passed_all``
        alone cannot answer this: a timed-out test and a failed test both
        score ``passed_all=False``.
        """
        ...


@runtime_checkable
class ScenarioProvider(Protocol):
    def input_pool(self, task: Task, n: int, seed: int) -> InputPool: ...

    def observe(self, task: Task, code: str, pool: InputPool, timeout_s: float) -> list[Observation]: ...

    def observe_one(self, task: Task, code: str, pool: InputPool, index: int, timeout_s: float) -> Observation:
        """Observation for a single pool item, ``pool.items[index]``.

        Exists so a per-mutant differential-fuzzing loop (Stage 0's
        ``check_equivalence``) can stop at the first divergence without
        paying for the rest of the pool -- calling :meth:`observe` for every
        candidate input would run the whole pool even for a mutant that
        diverges on the first one. :meth:`observe` is for the one case that
        truly needs every item regardless (the reference's own canonical
        observations, computed once and reused across every mutant).
        """
        ...

    def reference_observations(
        self, task: Task, pool: InputPool, timeout_s: float
    ) -> tuple[list[Observation], list[frozenset[str]]]: ...

    def observations_agree(self, a: Observation, b: Observation, mask: frozenset[str] = frozenset()) -> bool: ...

    def is_timeout(self, obs: Observation) -> bool: ...

    def is_error(self, obs: Observation) -> bool: ...


@runtime_checkable
class MutationScope(Protocol):
    def mutation_source(self, task: Task) -> str: ...

    def sdl_scope(self, task: Task) -> Optional[SDLScope]: ...

    def llm_mutation_messages(self, task: Task, fault_hint: str) -> list[dict]:
        """Chat messages asking an LLM to seed one semantic fault (RQ1).

        For HumanEval this must reproduce the existing
        ``rq1.llm_mutator._SYSTEM_PROMPT`` / ``_build_user_message`` call
        byte-for-byte -- it is part of the cache key
        (``core.cache.ResponseCache``), so any difference turns every cached
        Tier 1 RQ1-generate response into a miss.
        """
        ...

    def repair_mutant(self, task: Task, code: str) -> Optional[str]:
        """Make an LLM-returned mutant runnable, or None if it cannot be.

        For HumanEval this must reproduce
        ``rq1.llm_mutator.repair_mutant_code`` exactly (re-attach the
        prompt's imports/helpers, require the entry point to be defined).
        For a class-level benchmark the equivalent requirement is a
        top-level class definition with the right name.
        """
        ...


@runtime_checkable
class SuiteDegrader(Protocol):
    def degrade(self, task: Task, level: float, seed: int) -> DegradedSuite: ...

    def consistency_suite(
        self, task: Task, divergence_data: dict, threshold: Optional[float], max_assertions: int = 20
    ) -> tuple[str, int]:
        """Return ``(code, n_cases)``: source defining ``n_cases`` consistency
        checks built from RQ3's consensus, or ``("", 0)`` if none apply.

        For a named-test benchmark, each case is a test function named
        ``test_ca_<i>`` for ``i`` in ``range(n_cases)`` -- :meth:`augmented_suite`
        derives the names from ``n_cases`` by this convention rather than this
        method returning them separately.
        """
        ...

    def augmented_suite(
        self, task: Task, degraded: DegradedSuite, ca_code: str, ca_count: int
    ) -> DegradedSuite:
        """Combine a degraded suite with ``consistency_suite``'s output into
        the one suite ``Executor.run_suite`` should run. ``ca_code``/``ca_count``
        may be ``""``/``0`` (no assertions applied -- below threshold, say),
        in which case this should just return ``degraded`` unchanged.
        """
        ...


@runtime_checkable
class Benchmark(TaskSource, Executor, ScenarioProvider, MutationScope, SuiteDegrader, Protocol):
    """Everything an RQ runner needs from a benchmark."""
