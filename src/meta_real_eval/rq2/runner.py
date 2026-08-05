"""RQ2 runner: ranking instability under semantically equivalent prompt variants.

Phases
------
generate
    For every (task, relation, model) triple, generate n completions via Innkube.
    LLM-bound → single SLURM job, async, rate-limited.

evaluate
    Execute cached completions against the test suite, compute Pass@k,
    then compute Kendall tau_b ranking stability across variants.
    CPU-bound → SLURM job array, one task per element.

Usage
-----
    python -m meta_real_eval.rq2.runner --config config/default.yaml --phase generate
    python -m meta_real_eval.rq2.runner --config config/default.yaml --phase evaluate --task-index 42
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from ..core.config import Config
from ..core.data_loader import load_humaneval
from ..core.logging_setup import setup as setup_logging
from ..core.task_selection import add_task_selection_args, resolve_task_filter
from .evaluator import evaluate_task
from .generator import run_generate
from .ranking import compute_ranking_stability

logger = logging.getLogger(__name__)


def main(argv=None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="RQ2: ranking instability")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--phase", choices=["generate", "evaluate"], required=True)
    add_task_selection_args(parser)
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    setup_logging("rq2", args.phase, log_dir=Path("logs"))

    tasks = load_humaneval(tasks=resolve_task_filter(args, cfg))
    logger.info("RQ2 phase=%s, %d task(s)", args.phase, len(tasks))

    if args.phase == "generate":
        asyncio.run(run_generate(cfg, tasks))
    else:
        for task in tasks:
            evaluate_task(task, cfg)
            compute_ranking_stability(task, cfg)

    logger.info("RQ2 phase=%s complete.", args.phase)


if __name__ == "__main__":
    main()
