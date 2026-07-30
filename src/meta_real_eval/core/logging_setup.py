"""Logging initialisation shared by all runner entry points."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup(stage: str, phase: str | None = None, log_dir: Path = Path("logs")) -> None:
    """Configure root logger to write to stdout and to a per-stage file.

    Call once at the top of each runner's main().
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    label = f"{stage}_{phase}" if phase else stage
    log_file = log_dir / f"{label}.log"

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers, force=True)
