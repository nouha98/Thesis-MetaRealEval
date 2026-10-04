"""Tier 1 adapter: HumanEval behind the :mod:`.base` contract.

Every method here *delegates* to the pre-existing Tier 1 function and adds
no logic of its own -- that is what makes "Tier 1 results are unchanged by
the adapter" a checkable claim rather than a hope. The delegation targets:

    load_tasks             core.data_loader.load_humaneval
    generation_messages    rq2.generator._build_messages
    build_solution         rq2.evaluator.build_solution_code
    run_suite              core.sandbox.execute(... check(entry_point))
    input_pool             stage0.equivalence._generate_inputs
    observe / observe_one  stage0.equivalence._run_one
    degrade                rq4.degradation.degrade
    consistency_suite      rq4.consistency.build_consistency_assertions
    llm_mutation_messages  rq1.llm_mutator._SYSTEM_PROMPT / _build_user_message
    repair_mutant          rq1.llm_mutator.repair_mutant_code

``tests/test_benchmarks/test_humaneval_adapter.py`` checks each delegation
against the legacy call on real tasks, and
``scripts/verify_tier1_unchanged.py`` re-scores stored Tier 1 completions
through the adapter and diffs them against ``results/``.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from typing import Optional

from ..core.data_loader import HumanEvalTask, load_humaneval, task_label
from ..core.sandbox import execute
from ..rq1.llm_mutator import _SYSTEM_PROMPT as _MUTATOR_SYSTEM_PROMPT
from ..rq1.llm_mutator import _build_user_message, repair_mutant_code
from ..rq2.evaluator import build_solution_code
from ..rq2.generator import _build_messages
from ..rq4.consistency import build_consistency_assertions
from ..rq4.degradation import degrade as degrade_check_block
from ..stage0.equivalence import TIMEOUT, _generate_inputs, _run_one
from .base import DegradedSuite, InputPool, Observation, SDLScope, SuiteResult, Task
from .outcomes import ORDINARY_FAIL, ORDINARY_PASS, TestOutcome
from .outcomes import TIMEOUT as OUTCOME_TIMEOUT

CHECK = "check"  # the one "test" a HumanEval suite has


def _to_task(t: HumanEvalTask) -> Task:
    return Task(
        task_id=t.task_id,
        task_index=t.task_index,
        label=task_label(t),
        prompt=t.prompt,
        reference_code=t.prompt + t.canonical_solution,
        test_code=t.test,
        target=t.entry_point,
        raw=t,
    )


class HumanEvalBenchmark:
    name = "humaneval"

    def __init__(self, cfg=None) -> None:
        self.cfg = cfg

    # --- TaskSource ----------------------------------------------------------

    def load_tasks(self, indices: Optional[list[int]] = None) -> list[Task]:
        return [_to_task(t) for t in load_humaneval(tasks=indices)]

    def generation_messages(self, task: Task, prompt_variant: str) -> list[dict]:
        return _build_messages(prompt_variant)

    # --- Executor ------------------------------------------------------------

    def build_solution(self, task: Task, completion: str) -> str:
        return build_solution_code(completion, task.prompt, task.target)

    def run_suite(
        self,
        task: Task,
        code: str,
        timeout_s: float,
        suite: Optional[DegradedSuite] = None,
    ) -> SuiteResult:
        test_block = suite.test_code if suite is not None and suite.test_code is not None else task.test_code
        result = execute(code, test_block + f"\ncheck({task.target})\n", timeout_s=timeout_s)
        if result.timed_out:
            outcome = TestOutcome(CHECK, OUTCOME_TIMEOUT)
        elif result.passed:
            outcome = TestOutcome(CHECK, ORDINARY_PASS)
        else:
            outcome = TestOutcome(CHECK, ORDINARY_FAIL)
        outcomes = {CHECK: outcome}
        return SuiteResult(outcomes=outcomes, scores=self.score_outcomes(task, outcomes))

    def score_outcomes(self, task, outcomes, subset=None, extra_valid=None) -> dict[str, Optional[float]]:
        # extra_valid: unused. HumanEval's single check() block has no
        # per-named-test concept to extend -- Tier 1's augmented_suite folds
        # consistency assertions straight into the one test_code string
        # instead, so they are already covered by this same pass/fail.
        passed = 1.0 if outcomes[CHECK].outcome == ORDINARY_PASS else 0.0
        return {"primary": passed, "passed_all": passed}

    def suite_timed_out(self, result: SuiteResult) -> bool:
        return result.outcomes[CHECK].outcome == OUTCOME_TIMEOUT

    # --- ScenarioProvider ----------------------------------------------------

    def input_pool(self, task: Task, n: int, seed: int) -> InputPool:
        return InputPool(items=_generate_inputs(task.raw, n, seed))

    def observe(self, task: Task, code: str, pool: InputPool, timeout_s: float) -> list[Observation]:
        """Every item, batched. Parallelised across ``cfg.execution.cpu_workers``
        when available: this is what ``compute_canonical_observations`` calls
        for the reference, which (unlike a per-mutant check) always needs
        every input and has no early exit to lose -- exactly mirroring
        ``stage0.equivalence.compute_canonical_outputs``'s own pooling, so
        routing it through the adapter does not regress Stage 0's wall time.
        """
        workers = getattr(getattr(self.cfg, "execution", None), "cpu_workers", 1) or 1
        items = pool.items
        if workers <= 1 or len(items) <= 1:
            return [_run_one(code, task.target, args, timeout_s) for args in items]
        with ProcessPoolExecutor(max_workers=workers) as pool_exec:
            return list(pool_exec.map(
                _run_one, [code] * len(items), [task.target] * len(items), items, [timeout_s] * len(items),
            ))

    def observe_one(self, task: Task, code: str, pool: InputPool, index: int, timeout_s: float) -> Observation:
        return _run_one(code, task.target, pool.items[index], timeout_s)

    def reference_observations(self, task, pool, timeout_s):
        # One run, no masking: exactly stage0.equivalence.compute_canonical_outputs.
        obs = self.observe(task, task.reference_code, pool, timeout_s)
        return obs, [frozenset()] * len(obs)

    def observations_agree(self, a, b, mask=frozenset()) -> bool:
        # A timeout never compares equal, not even to another timeout.
        return a != TIMEOUT and b != TIMEOUT and a == b

    def is_timeout(self, obs) -> bool:
        return obs == TIMEOUT

    def is_error(self, obs) -> bool:
        return isinstance(obs, str) and obs.startswith("__error__")

    # --- MutationScope -------------------------------------------------------

    def mutation_source(self, task: Task) -> str:
        return task.reference_code

    def sdl_scope(self, task: Task) -> Optional[SDLScope]:
        return None  # stage0.corpus_builder's legacy path: the entry point only

    def llm_mutation_messages(self, task: Task, fault_hint: str) -> list[dict]:
        # Byte-identical to generate_llm_mutants' own message construction --
        # see the ResponseCache warning on the protocol method.
        return [
            {"role": "system", "content": _MUTATOR_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(task.raw, fault_hint)},
        ]

    def repair_mutant(self, task: Task, code: str) -> Optional[str]:
        return repair_mutant_code(code, task.prompt, task.target)

    # --- SuiteDegrader -------------------------------------------------------

    def degrade(self, task: Task, level: float, seed: int) -> DegradedSuite:
        return DegradedSuite(level=level, test_code=degrade_check_block(task.test_code, level, seed=seed))

    def consistency_suite(self, task, divergence_data, threshold, max_assertions=20):
        return build_consistency_assertions(task.raw, divergence_data, threshold, max_assertions)

    def augmented_suite(self, task: Task, degraded: DegradedSuite, ca_code: str, ca_count: int) -> DegradedSuite:
        test_code = degraded.test_code + (f"\n{ca_code}" if ca_code else "")
        return DegradedSuite(level=degraded.level, test_code=test_code)
