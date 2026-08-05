"""Shared --task-index / --task-range CLI plumbing for the stage/RQ runners.

Every runner needs to pick which HumanEval task indices to process: a single
index (SLURM array element), a contiguous range (splitting work between a
local machine and the cluster), or all of them (config's benchmark.tasks).
This was previously duplicated ad hoc across all five runner.py files.
"""

from __future__ import annotations

import argparse
from typing import Optional

from .config import Config


def add_task_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--task-index", type=int, default=None,
        help="Process only this task index (for SLURM job arrays)",
    )
    parser.add_argument(
        "--task-range", type=str, default=None, metavar="START-END",
        help="Process an inclusive task-index range, e.g. --task-range 0-49",
    )


def resolve_task_filter(args: argparse.Namespace, cfg: Config) -> Optional[list[int]]:
    """Return the task-index list implied by CLI args, falling back to config.

    Precedence: --task-index > --task-range > config's benchmark.tasks (None = all).
    """
    if args.task_index is not None:
        return [args.task_index]

    if args.task_range is not None:
        start_s, _, end_s = args.task_range.partition("-")
        try:
            start, end = int(start_s), int(end_s)
        except ValueError:
            raise SystemExit(
                f"--task-range must look like START-END (e.g. 0-49), got {args.task_range!r}"
            )
        if start > end:
            raise SystemExit(f"--task-range start ({start}) must be <= end ({end})")
        return list(range(start, end + 1))

    return cfg.benchmark.tasks
