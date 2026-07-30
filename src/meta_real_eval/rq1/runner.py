"""RQ1 runner: fault characterisation and benchmark adequacy.

Phases
------
generate
    Build the LLM (semantic) mutant corpus via Innkube.
    Traditional (AOR/ROR/SDL) mutants are already produced by Stage 0's
    corpus_builder; this phase only adds the LLM-specific ones.
    LLM-bound → run as a single SLURM job.

evaluate
    Run the benchmark test suite against all non-equivalent mutants and
    compute kill rates per operator category.
    CPU-bound → SLURM job array, one task per element.

Usage
-----
    python -m meta_real_eval.rq1.runner --config config/default.yaml --phase generate
    python -m meta_real_eval.rq1.runner --config config/default.yaml --phase evaluate --task-index 42
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from ..core.cache import ResponseCache
from ..core.checkpoint import is_done, mark_done, task_dir, write_json, read_json
from ..core.config import Config
from ..core.data_loader import load_humaneval, task_label
from ..core.llm_client import InnkubeClient
from ..core.logging_setup import setup as setup_logging
from ..stage0.corpus_builder import Mutant
from .ast_fallback import generate_ast_fallback_mutants
from .kill_rate import compute_kill_matrix, summarise
from .llm_mutator import generate_llm_mutants

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generate phase
# ---------------------------------------------------------------------------

async def _generate_one(task, cfg: Config, client: InnkubeClient) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq1", label, phase="generate")

    if is_done(out):
        logger.info("SKIP generate %s", label)
        return

    logger.info("Generating LLM mutants for %s", label)

    if cfg.project.mock:
        llm_mutants = generate_ast_fallback_mutants(
            task.prompt, task.canonical_solution, seed=cfg.project.seed
        )
    else:
        model_id = cfg.model_ids()[0]  # use first model for mutant generation
        llm_mutants = await generate_llm_mutants(
            task=task,
            model_id=model_id,
            client=client,
            n_mutants=3,
        )
        if not llm_mutants:
            logger.warning("LLM generation failed for %s, using AST fallback", label)
            llm_mutants = generate_ast_fallback_mutants(
                task.prompt, task.canonical_solution, seed=cfg.project.seed
            )

    data = [
        {"mutant_id": m.mutant_id, "operator": m.operator,
         "description": m.description, "code": m.code}
        for m in llm_mutants
    ]
    write_json(out, "llm_mutants.json", data)
    mark_done(out)
    logger.info("  Saved %d LLM mutants for %s", len(llm_mutants), label)


async def run_generate(cfg: Config, tasks) -> None:
    cache = ResponseCache(cfg.llm.cache_dir)
    client = InnkubeClient(cfg.llm, cache, mock=cfg.project.mock)
    coros = [_generate_one(t, cfg, client) for t in tasks]
    await asyncio.gather(*coros)


# ---------------------------------------------------------------------------
# Evaluate phase
# ---------------------------------------------------------------------------

def run_evaluate_one(task, cfg: Config) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq1", label, phase="evaluate")

    if is_done(out):
        logger.info("SKIP evaluate %s", label)
        return

    # Load traditional mutants from Stage 0
    s0_out = task_dir(cfg, "stage0", label)
    try:
        trad_raw = read_json(s0_out, "mutants.json")
        equiv_raw = read_json(s0_out, "equiv_filter.json")
    except FileNotFoundError:
        logger.error("Stage 0 outputs missing for %s — run stage0 first", label)
        return

    # Load LLM mutants from rq1 generate phase
    rq1_gen_out = task_dir(cfg, "rq1", label, phase="generate")
    try:
        llm_raw = read_json(rq1_gen_out, "llm_mutants.json")
    except FileNotFoundError:
        llm_raw = []
        logger.warning("No LLM mutants found for %s — using traditional only", label)

    all_mutants = [
        Mutant(
            mutant_id=m["mutant_id"], operator=m["operator"],
            description=m["description"], code=m["code"],
        )
        for m in (trad_raw + llm_raw)
    ]

    equiv_ids = {
        r["mutant_id"]
        for r in equiv_raw
        if r["is_equivalent"]
    }

    logger.info("Evaluating %s: %d mutants (%d equivalent, skipped)",
                label, len(all_mutants), len(equiv_ids))

    kill_results = compute_kill_matrix(
        task=task,
        mutants=all_mutants,
        equiv_ids=equiv_ids,
        timeout_s=cfg.execution.timeout_s,
        cpu_workers=cfg.execution.cpu_workers,
    )

    summary = summarise(kill_results)
    write_json(out, "kill_matrix.json", [
        {"mutant_id": r.mutant_id, "operator": r.operator, "is_killed": r.is_killed}
        for r in kill_results
    ])
    write_json(out, "kill_rate_summary.json", summary)
    mark_done(out)
    logger.info("  Kill rates: %s", summary)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="RQ1: fault characterisation")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--phase", choices=["generate", "evaluate"], required=True)
    parser.add_argument("--task-index", type=int, default=None)
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    setup_logging("rq1", args.phase, log_dir=Path("logs"))

    task_filter = [args.task_index] if args.task_index is not None else cfg.benchmark.tasks
    tasks = load_humaneval(tasks=task_filter)
    logger.info("RQ1 phase=%s, %d task(s)", args.phase, len(tasks))

    if args.phase == "generate":
        asyncio.run(run_generate(cfg, tasks))
    else:
        for task in tasks:
            run_evaluate_one(task, cfg)

    logger.info("RQ1 phase=%s complete.", args.phase)


if __name__ == "__main__":
    main()
