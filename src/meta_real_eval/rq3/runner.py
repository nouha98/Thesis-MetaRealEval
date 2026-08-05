"""RQ3 runner: metamorphic validation via divergence + SBC scoring.

Phases
------
execute
    Run solutions from RQ2 on shared random inputs; compute pairwise divergence.
    CPU-bound → SLURM job array.

score
    Run SBC reverse generation via Innkube for each unique solution.
    LLM-bound → single SLURM job, async.

Usage
-----
    python -m meta_real_eval.rq3.runner --config config/default.yaml --phase execute --task-index 42
    python -m meta_real_eval.rq3.runner --config config/default.yaml --phase score
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from ..core.cache import ResponseCache
from ..core.checkpoint import is_done, mark_done, task_dir, write_json, read_json
from ..core.config import Config
from ..core.data_loader import load_humaneval, task_label
from ..core.llm_client import InnkubeClient
from ..core.logging_setup import setup as setup_logging
from ..core.task_selection import add_task_selection_args, resolve_task_filter
from ..rq2.evaluator import _extract_function_body
from .divergence import compute_divergence
from .sbc_scorer import compute_sbc_score

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Execute phase
# ---------------------------------------------------------------------------

def run_execute_one(task, cfg: Config) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq3", label, phase="execute")

    if is_done(out):
        logger.info("SKIP execute %s", label)
        return

    gen_out = task_dir(cfg, "rq2", label, phase="generate")
    try:
        completions_data: dict = read_json(gen_out, "completions.json")
    except FileNotFoundError:
        logger.error("RQ2 completions missing for %s — run rq2 generate first", label)
        return

    result = compute_divergence(
        task=task,
        completions_data=completions_data,
        n_shared_inputs=cfg.rq3.n_shared_inputs,
        timeout_s=cfg.execution.timeout_s,
        seed=cfg.project.seed,
    )

    write_json(out, "divergence.json", result)
    mark_done(out)
    logger.info(
        "Divergence %s: %.3f (%d solutions, %d inputs)",
        label, result["pairwise_disagreement_rate"],
        result["n_solutions"], result["n_inputs"],
    )


# ---------------------------------------------------------------------------
# Score phase
# ---------------------------------------------------------------------------

async def _score_one(task, cfg: Config, client: InnkubeClient) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq3", label, phase="score")

    if is_done(out):
        logger.info("SKIP score %s", label)
        return

    gen_out = task_dir(cfg, "rq2", label, phase="generate")
    try:
        completions_data: dict = read_json(gen_out, "completions.json")
    except FileNotFoundError:
        logger.warning("Missing RQ2 completions for %s", label)
        return

    model_id = cfg.model_ids()[0]
    sbc_results: dict[str, dict] = {}

    import re
    for relation, model_completions in completions_data.items():
        for mid, completions in model_completions.items():
            if not completions:
                continue
            best = completions[0]
            body = _extract_function_body(best, task.entry_point)
            code = task.prompt + body if not re.match(r"\s*def\s+", body) else body
            key = f"{relation}/{mid}"
            try:
                sbc_results[key] = await compute_sbc_score(task, code, model_id, client)
            except Exception as exc:
                logger.warning("SBC failed for %s/%s: %s", label, key, exc)

    write_json(out, "sbc_scores.json", sbc_results)
    mark_done(out)
    logger.info("SBC scored %s: %d solutions", label, len(sbc_results))


async def run_score(cfg: Config, tasks) -> None:
    cache = ResponseCache(cfg.llm.cache_dir)
    client = InnkubeClient(cfg.llm, cache, mock=cfg.project.mock)
    coros = [_score_one(t, cfg, client) for t in tasks]
    await asyncio.gather(*coros)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="RQ3: metamorphic validation")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--phase", choices=["execute", "score"], required=True)
    add_task_selection_args(parser)
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    setup_logging("rq3", args.phase, log_dir=Path("logs"))

    tasks = load_humaneval(tasks=resolve_task_filter(args, cfg))
    logger.info("RQ3 phase=%s, %d task(s)", args.phase, len(tasks))

    if args.phase == "execute":
        for task in tasks:
            run_execute_one(task, cfg)
    else:
        asyncio.run(run_score(cfg, tasks))

    logger.info("RQ3 phase=%s complete.", args.phase)


if __name__ == "__main__":
    main()
