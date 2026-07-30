#!/usr/bin/env python
"""Report experiment progress by counting done-marker files.

Usage
-----
    python scripts/progress.py --config config/default.yaml
    python scripts/progress.py --config config/default.yaml --verbose
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meta_real_eval.core.config import Config
from meta_real_eval.core.data_loader import load_humaneval


STAGES = [
    ("stage0",  None,       "Stage 0   equiv filter"),
    ("rq1",     "generate", "RQ1       llm generate"),
    ("rq1",     "evaluate", "RQ1       kill rate    "),
    ("rq2",     "generate", "RQ2       completions  "),
    ("rq2",     "evaluate", "RQ2       pass@k / τ_b "),
    ("rq3",     "execute",  "RQ3       divergence   "),
    ("rq3",     "score",    "RQ3       SBC score    "),
    ("rq4",     "degrade",  "RQ4       degrade      "),
    ("rq4",     "augment",  "RQ4       augment      "),
]


def count_done(base: Path, stage: str, phase: str | None, task_labels: list[str]) -> int:
    done = 0
    for label in task_labels:
        parts = [base, stage]
        if phase:
            parts.append(phase)
        parts.append(label)
        marker = Path(*parts) / "_done.marker"
        if marker.exists():
            done += 1
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment progress report")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cfg = Config.from_yaml(args.config)
    tasks = load_humaneval(tasks=cfg.benchmark.tasks)
    labels = [t.task_id.replace("/", "_") for t in tasks]
    n = len(labels)
    base = cfg.project.output_dir

    print(f"\nMeta-Real-Eval progress  ({n} tasks)\n{'─'*48}")
    for stage, phase, label in STAGES:
        done = count_done(base, stage, phase, labels)
        pct = done / n * 100
        bar_filled = int(pct / 5)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        print(f"{label}  [{bar}] {done:>3}/{n}  ({pct:.0f}%)")

    print("─" * 48)


if __name__ == "__main__":
    main()
