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

from ..core.checkpoint import is_done, mark_done, task_dir, write_json, read_json
from ..core.config import Config
from ..core.data_loader import load_humaneval, task_label
from ..core.logging_setup import setup as setup_logging
from ..core.task_selection import add_task_selection_args, resolve_task_filter
from .corpus_builder import generate_mutants, Mutant
from .equivalence import check_equivalence, compute_canonical_outputs, EquivResult

logger = logging.getLogger(__name__)


def process_task(task, cfg: Config) -> None:
    label = task_label(task)
    out = task_dir(cfg, "stage0", label)

    if is_done(out):
        logger.info("SKIP %s (already done)", label)
        return

    logger.info("Processing %s", label)

    # --- 1. Generate mutants ---
    mutants: list[Mutant] = generate_mutants(
        prompt=task.prompt,
        canonical_solution=task.canonical_solution,
        entry_point=task.entry_point,
        operators=cfg.rq1.operators,
        seed=cfg.project.seed,
    )
    logger.info("  Generated %d mutants", len(mutants))

    mutants_data = [
        {"mutant_id": m.mutant_id, "operator": m.operator,
         "description": m.description, "code": m.code}
        for m in mutants
    ]
    write_json(out, "mutants.json", mutants_data)

    # --- 2. Equivalence filtering ---
    # Canonical outputs are identical for every mutant of this task, so compute
    # them once and reuse rather than re-running the canonical solution per mutant.
    cpu_workers = cfg.execution.cpu_workers
    canon_outs = compute_canonical_outputs(
        task=task,
        n_fuzz_inputs=cfg.stage0.n_fuzz_inputs,
        timeout_s=cfg.execution.timeout_s,
        seed=cfg.project.seed,
        cpu_workers=cpu_workers,
    ) if mutants else []

    # Each mutant's own equivalence check (up to n_fuzz_inputs subprocess spawns,
    # early-exiting on first divergence) is independent of every other mutant's,
    # so spread them across cpu_workers processes instead of running one at a time.
    results_by_id: dict[str, EquivResult] = {}
    if mutants:
        with ProcessPoolExecutor(max_workers=cpu_workers) as pool:
            future_to_mutant = {
                pool.submit(
                    check_equivalence,
                    task,
                    mutant,
                    cfg.stage0.n_fuzz_inputs,
                    cfg.execution.timeout_s,
                    cfg.project.seed,
                    canon_outs,
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
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    setup_logging("stage0", log_dir=Path("logs"))

    tasks = load_humaneval(tasks=resolve_task_filter(args, cfg))

    logger.info("Stage 0: %d task(s) to process", len(tasks))
    for task in tasks:
        process_task(task, cfg)

    logger.info("Stage 0 complete.")


if __name__ == "__main__":
    main()
