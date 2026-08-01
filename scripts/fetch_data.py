#!/usr/bin/env python
"""Pre-stage the HumanEval corpus for offline SLURM jobs.

Compute nodes have no outbound internet, so ``datasets.load_dataset`` fails
there instantly and every array task dies with ExitCode 1. Run this **once on
the login node** (which does have internet) to write the corpus to
``data/HumanEval.jsonl.gz``; jobs then read it straight off /shared.

    .venv/bin/python scripts/fetch_data.py

Re-running is a no-op unless ``--force`` is given.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.data_loader import (  # noqa: E402
    DEFAULT_CORPUS_PATH,
    N_HUMANEVAL_TASKS,
    fetch_corpus,
    load_humaneval,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=DEFAULT_CORPUS_PATH,
                        help=f"output path (default: {DEFAULT_CORPUS_PATH})")
    parser.add_argument("--force", action="store_true",
                        help="re-download even if the corpus is already present")
    args = parser.parse_args()

    if args.dest.exists() and not args.force:
        print(f"{args.dest} already exists — nothing to do (use --force to refresh).")
    else:
        try:
            n = fetch_corpus(args.dest)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print(f"Wrote {n} tasks to {args.dest}")

    tasks = load_humaneval()
    print(f"Verified: {len(tasks)} tasks load offline "
          f"({tasks[0].task_id} .. {tasks[-1].task_id})")
    if len(tasks) != N_HUMANEVAL_TASKS:
        print(f"WARNING: expected {N_HUMANEVAL_TASKS} tasks", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
