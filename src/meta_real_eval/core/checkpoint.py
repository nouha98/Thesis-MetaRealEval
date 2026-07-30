"""File-based checkpointing with done-marker files.

Layout
------
results/
  <stage>/
    [<phase>/]
      <task_id>/
        _done.marker   ← presence means this (stage, phase, task) is complete
        *.json         ← actual outputs

Usage
-----
    path = task_dir(cfg, "stage0", task_id="HumanEval_42")
    if is_done(path):
        return  # skip
    # ... do work, write output files ...
    mark_done(path)
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import Config


def task_dir(cfg: Config, stage: str, task_id: str, phase: str | None = None) -> Path:
    """Return the output directory for one (stage, [phase,] task)."""
    parts = [cfg.project.output_dir, stage]
    if phase:
        parts.append(phase)
    parts.append(task_id)
    return Path(*parts)


def is_done(path: Path) -> bool:
    return (path / "_done.marker").exists()


def mark_done(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "_done.marker").touch()


def write_json(path: Path, filename: str, data: object) -> None:
    """Atomically write JSON to path/filename."""
    path.mkdir(parents=True, exist_ok=True)
    tmp = path / (filename + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(path / filename)


def read_json(path: Path, filename: str) -> object:
    return json.loads((path / filename).read_text())
