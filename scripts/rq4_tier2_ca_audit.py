#!/usr/bin/env python
"""Audit Tier 2 RQ4's consistency assertions against the reference implementation.

For every task that received assertions (rq4/augment/*/augment_tier2.json) rebuilds
them from RQ3's consensus and runs the task's REFERENCE solution under the intact suite
plus those assertions. Read-only apart from the JSON it writes
(<output_dir>/rq4/ca_audit_tier2.json):

    .venv/bin/python scripts/rq4_tier2_ca_audit.py --config config/tier2_runs/full_combined.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.checkpoint import read_json, task_dir  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402
from meta_real_eval.rq4 import tier2  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = Config.from_yaml(args.config)
    bench = get_benchmark(cfg)
    threshold = cfg.rq3.divergence_threshold
    if threshold is None:
        print("rq3.divergence_threshold is not calibrated", file=sys.stderr)
        return 2
    rows = {}
    for task in bench.load_tasks():
        try:
            aug = read_json(task_dir(cfg, "rq4", task.label, phase="augment"), tier2.AUGMENT_FILE)
        except FileNotFoundError:
            continue
        if not aug.get("has_consistency_assertions"):
            continue
        divergence = read_json(task_dir(cfg, "rq3", task.label, phase="execute"), "divergence.json")
        ca_code, n_ca = bench.consistency_suite(task, divergence, threshold)
        rows[task.label] = tier2.reference_on_assertions(task, cfg, bench, ca_code, n_ca)
        r = rows[task.label]
        print(f"{task.label:24s} assertions={r['n_assertions']:3d} reference passes {r['reference_passes']:3d} "
              f"fails {r['reference_fails']:3d} | reference score on intact suite + assertions "
              f"{r['reference_primary']}")
    n = sum(r["n_assertions"] for r in rows.values())
    bad = sum(r["reference_fails"] for r in rows.values())
    print(f"\n{len(rows)} task(s), {n} assertions; the reference fails {bad} ({bad / n:.0%})" if n else "no assertions")
    print(f"tasks where the reference fails >= 1 assertion: "
          f"{sum(r['reference_fails'] > 0 for r in rows.values())} of {len(rows)}")
    out = cfg.project.output_dir / "rq4"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ca_audit_tier2.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
