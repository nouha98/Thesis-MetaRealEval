"""Stage 0 runner: build mutant corpus and filter equivalent mutants.

Usage
-----
    # Process all tasks
    python -m meta_real_eval.stage0.runner --config config/default.yaml

    # Process a single task (SLURM job array)
    python -m meta_real_eval.stage0.runner --config config/default.yaml --task-index 42
"""

from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

from ..benchmarks import get_benchmark
from ..core.checkpoint import add_force_arg, clear_done, is_done, mark_done, task_dir, write_json, read_json
from ..core.config import Config
from ..core.logging_setup import setup as setup_logging
from ..core.task_selection import add_task_selection_args, resolve_task_filter
from .corpus_builder import generate_mutants, Mutant
from .equivalence import EquivResult, check_equivalence_generic, compute_canonical_observations

logger = logging.getLogger(__name__)


def process_task(task, cfg: Config, bench, force: bool = False) -> None:
    label = task.label
    out = task_dir(cfg, "stage0", label)

    if force:
        clear_done(out)

    if is_done(out):
        logger.info("SKIP %s (already done)", label)
        return

    logger.info("Processing %s", label)

    # --- 1. Generate mutants ---
    # prompt="": the benchmark's mutation_source() already returns the FULL
    # code to mutate (Tier 1: prompt + canonical_solution; Tier 2: the whole
    # reference class), so nothing needs splitting into a separate prompt
    # half here -- see tests/test_benchmarks/test_humaneval_adapter.py's
    # delegation test for why this reproduces the old call byte-for-byte.
    mutants: list[Mutant] = generate_mutants(
        prompt="",
        canonical_solution=bench.mutation_source(task),
        entry_point=task.target,
        operators=cfg.rq1.operators,
        max_per_operator=cfg.stage0.max_mutants_per_operator,
        seed=cfg.project.seed,
        sdl_scope=bench.sdl_scope(task),
    )
    logger.info("  Generated %d mutants", len(mutants))

    mutants_data = [
        {"mutant_id": m.mutant_id, "operator": m.operator,
         "description": m.description, "code": m.code, "method": m.method}
        for m in mutants
    ]
    write_json(out, "mutants.json", mutants_data)

    # --- 2. Equivalence filtering ---
    # Canonical observations are identical for every mutant of this task, so
    # compute them once and reuse rather than re-running the reference per
    # mutant. bench.observe() parallelises across cpu_workers for a benchmark
    # that needs it (HumanEvalBenchmark); Tier 2's scenario runner already
    # batches internally (see compute_canonical_observations's docstring).
    cpu_workers = cfg.execution.cpu_workers
    input_pool, canon_obs = compute_canonical_observations(
        bench, task,
        n_fuzz_inputs=cfg.stage0.n_fuzz_inputs,
        timeout_s=cfg.execution.timeout_s,
        seed=cfg.project.seed,
    ) if mutants else (None, [])

    # Each mutant's own equivalence check (up to n_fuzz_inputs subprocess spawns,
    # early-exiting on first divergence) is independent of every other mutant's,
    # so spread them across cpu_workers processes instead of running one at a time.
    results_by_id: dict[str, EquivResult] = {}
    if mutants:
        with ProcessPoolExecutor(max_workers=cpu_workers) as pool:
            future_to_mutant = {
                pool.submit(
                    check_equivalence_generic,
                    cfg,
                    task,
                    mutant,
                    cfg.stage0.n_fuzz_inputs,
                    cfg.execution.timeout_s,
                    cfg.project.seed,
                    input_pool,
                    canon_obs,
                ): mutant
                for mutant in mutants
            }
            for future in as_completed(future_to_mutant):
                mutant = future_to_mutant[future]
                results_by_id[mutant.mutant_id] = future.result()

    equiv_results: list[dict] = []
    n_equiv = 0
    for mutant in mutants:
        result: EquivResult = results_by_id[mutant.mutant_id]
        equiv_results.append({
            "mutant_id": result.mutant_id,
            "is_equivalent": result.is_equivalent,
            "reason": result.reason,
            "n_inputs_tested": result.n_inputs_tested,
            "diverging_input": result.diverging_input,
        })
        if result.is_equivalent:
            n_equiv += 1

    logger.info("  Equivalence: %d/%d flagged as equivalent", n_equiv, len(mutants))
    write_json(out, "equiv_filter.json", equiv_results)

    mark_done(out)
        
def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Stage 0: equivalence filtering")
    parser.add_argument("--config", default="config/default.yaml")
    add_task_selection_args(parser)
    add_force_arg(parser)
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    setup_logging("stage0", log_dir=Path("logs"))

    bench = get_benchmark(cfg)
    tasks = bench.load_tasks(resolve_task_filter(args, cfg))

    logger.info("Stage 0: %d task(s) to process%s", len(tasks), " (forced)" if args.force else "")
    for task in tasks:
        process_task(task, cfg, bench, force=args.force)

    logger.info("Stage 0 complete.")


if __name__ == "__main__":
    main()
