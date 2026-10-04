"""``python -m meta_real_eval.benchmarks count --config <yaml>``

Prints the number of tasks the configured benchmark exposes, so SLURM
scripts size their job arrays from the data (the M0 manifest, for Tier 2)
instead of a hard-coded count.
"""

from __future__ import annotations

import argparse

from ..core.config import Config
from . import get_benchmark


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m meta_real_eval.benchmarks")
    parser.add_argument("command", choices=["count"])
    parser.add_argument("--config", default="config/default.yaml")
    args = parser.parse_args(argv)
    print(len(get_benchmark(Config.from_yaml(args.config)).load_tasks()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
