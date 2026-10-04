"""Compute kill matrix: which mutants are killed by the benchmark test suite.

A mutant is *killed* if running the task's test suite against it raises
an exception (non-zero exit code).  A mutant *survives* if all tests pass.
Only non-equivalent mutants (from Stage 0 filtering) are evaluated.
"""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

from ..benchmarks import get_benchmark
from ..core.data_loader import HumanEvalTask
from ..core.sandbox import execute, build_test_driver
from ..stage0.corpus_builder import Mutant

logger = logging.getLogger(__name__)


@dataclass
class KillResult:
    mutant_id: str
    operator: str
    is_killed: bool
    timed_out: bool


def _run_one(mutant_code: str, test_code: str, entry_point: str, timeout_s: float) -> bool:
    """Return True if the test KILLS the mutant (test raises / non-zero exit)."""
    solution_code, full_test = build_test_driver("", mutant_code, test_code, entry_point)
    # mutant_code already includes the full function (prompt + body)
    result = execute(mutant_code, f"{test_code}\ncheck({entry_point})\n", timeout_s)
    return not result.passed  # killed = test failed


def compute_kill_matrix(
    task: HumanEvalTask,
    mutants: list[Mutant],
    equiv_ids: set[str],
    timeout_s: float = 10.0,
    cpu_workers: int = 4,
) -> list[KillResult]:
    """Run the task's test suite against each non-equivalent mutant in parallel.

    Parameters
    ----------
    equiv_ids:
        Set of mutant_ids classified as equivalent by Stage 0.
        These are skipped — not included in the returned list.
    """
    non_equiv = [m for m in mutants if m.mutant_id not in equiv_ids]
    if not non_equiv:
        logger.info("No non-equivalent mutants for %s", task.task_id)
        return []

    results: list[KillResult] = []

    with ProcessPoolExecutor(max_workers=cpu_workers) as pool:
        future_to_mutant = {
            pool.submit(
                _run_one,
                m.code,
                task.test,
                task.entry_point,
                timeout_s,
            ): m
            for m in non_equiv
        }

        for future in as_completed(future_to_mutant):
            mutant = future_to_mutant[future]
            try:
                killed = future.result()
            except Exception as exc:
                logger.warning("Error evaluating mutant %s: %s", mutant.mutant_id, exc)
                killed = False

            results.append(KillResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                is_killed=killed,
                timed_out=False,
            ))
            logger.debug("  %s: %s", mutant.mutant_id, "KILLED" if killed else "survived")

    return results


def _run_one_generic(cfg, task, mutant_code: str, timeout_s: float) -> bool:
    """Killed = the full suite did not entirely pass -- a timeout counts as
    killed here (unlike Stage 0's suite-veto, which excludes it: that check
    asks "does this prove non-equivalence", this one asks "did the suite
    distinguish the mutant", and a hang does). Matches _run_one's
    ``not result.passed`` exactly, where ``result.timed_out`` already implies
    ``not result.passed``. Takes ``cfg`` rather than a benchmark instance for
    the same reason rq2.evaluator._score_completion does: cheap to
    reconstruct per call in the worker process, no benchmark state to pickle.
    """
    bench = get_benchmark(cfg)
    result = bench.run_suite(task, mutant_code, timeout_s)
    return not result.passed_all


def compute_kill_matrix_generic(
    cfg,
    task,
    mutants: list[Mutant],
    equiv_ids: set[str],
    timeout_s: float = 10.0,
    cpu_workers: int = 4,
) -> list[KillResult]:
    """Benchmark-agnostic compute_kill_matrix -- see _run_one_generic."""
    non_equiv = [m for m in mutants if m.mutant_id not in equiv_ids]
    if not non_equiv:
        logger.info("No non-equivalent mutants for %s", task.task_id)
        return []

    results: list[KillResult] = []
    with ProcessPoolExecutor(max_workers=cpu_workers) as pool:
        future_to_mutant = {
            pool.submit(_run_one_generic, cfg, task, m.code, timeout_s): m
            for m in non_equiv
        }
        for future in as_completed(future_to_mutant):
            mutant = future_to_mutant[future]
            try:
                killed = future.result()
            except Exception as exc:
                logger.warning("Error evaluating mutant %s: %s", mutant.mutant_id, exc)
                killed = False
            results.append(KillResult(
                mutant_id=mutant.mutant_id, operator=mutant.operator,
                is_killed=killed, timed_out=False,
            ))
            logger.debug("  %s: %s", mutant.mutant_id, "KILLED" if killed else "survived")

    return results


def summarise(results: list[KillResult]) -> dict:
    """Return per-operator kill-rate summary dict."""
    by_op: dict[str, dict] = {}
    for r in results:
        op = r.operator
        if op not in by_op:
            by_op[op] = {"total": 0, "killed": 0}
        by_op[op]["total"] += 1
        if r.is_killed:
            by_op[op]["killed"] += 1

    summary = {}
    for op, counts in by_op.items():
        total = counts["total"]
        killed = counts["killed"]
        summary[op] = {
            "total": total,
            "killed": killed,
            "survived": total - killed,
            "kill_rate": killed / total if total else 0.0,
        }
    return summary
