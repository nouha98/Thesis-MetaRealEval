#!/usr/bin/env python
"""Pre-register Tier 2 RQ4 eligibility (plan rev. 6, 8.2), before any RQ4 run.

Reads only the gate, the test files and RQ2 v3's pass_rates.json; executes
nothing. Writes <output_dir>/rq4/eligibility_tier2.json (per task: oracle units,
valid tests, eligibility per design and score, with reasons) and prints the
counts, the whole-test sensitivity subset, the expected number of completion
runs, and a representative sample to try `rq4 degrade` on first:

    .venv/bin/python scripts/rq4_tier2_eligibility.py --config config/tier2_runs/full_combined.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.checkpoint import read_json, task_dir  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402
from meta_real_eval.rq4 import tier2  # noqa: E402

# Known edge cases from the S8 audit: spaCy import near the 30 s limit; torch
# (cold-start timeouts in RQ2 v2); torch plus completions that hang on some tests;
# real hangs and no paraphrase variants; qwen36 refusals (no class); many
# exception oracles and no-class credit; a cold-start re-run in RQ2 v3.
EDGE_CASES = ["RCE_csn_snippet_36", "RCE_post_snippet_88", "RCE_post_snippet_4", "RCE_csn_snippet_62",
              "RCE_post_snippet_141", "RCE_csn_snippet_250", "RCE_post_snippet_292"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = Config.from_yaml(args.config)
    bench = get_benchmark(cfg)
    if getattr(bench, "rq4_design", None) != "oracle_units":
        print("not a Tier 2 config (benchmark has no oracle-unit RQ4)", file=sys.stderr)
        return 2
    tasks = bench.load_tasks()
    levels = list(cfg.rq4.degradation_levels)
    per_task, missing = {}, []
    for t in tasks:
        try:
            pr = read_json(task_dir(cfg, "rq2", t.label, phase="evaluate"), "pass_rates.json")
            comp = read_json(task_dir(cfg, "rq2", t.label, phase="generate"), "completions.json")
        except FileNotFoundError:
            missing.append(t.label)
            continue
        e = tier2.eligibility(t, bench, cfg, pr)
        n_completions = sum(len(c) for by_model in comp.values() for c in by_model.values())
        n_levels = 0
        if any(tier2._runs(e, d) for d in (tier2.UNITS, tier2.TESTS)):
            n_levels = 1 + sum(len(levels) - 1 for d in (tier2.UNITS, tier2.TESTS) if tier2._runs(e, d))
        per_task[t.label] = {"task_index": t.task_index, **e, "n_completions": n_completions,
                             "expected_completion_runs": n_completions * n_levels}
    if missing:
        print(f"ERROR: RQ2 outputs missing for {len(missing)} task(s): {missing[:5]}", file=sys.stderr)
        return 1

    need = tier2.min_units_for_levels(levels)
    subset = sorted(l for l, r in per_task.items() if r["n_valid_tests"] >= need)
    record = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "design_version": tier2.DESIGN_VERSION, "config": args.config, "levels": levels,
              "min_required": need, "n_tasks": len(per_task), "tests_design_subset": subset,
              "per_task": per_task}
    out = cfg.project.output_dir / "rq4"
    out.mkdir(parents=True, exist_ok=True)
    (out / "eligibility_tier2.json").write_text(json.dumps(record, indent=1), encoding="utf-8")

    units = [r["n_units"] for r in per_task.values()]
    print(f"{len(per_task)} tasks; levels {levels}; a task needs >= {need} units (design 'tests': valid tests)")
    print(f"oracle units per task: median {sorted(units)[len(units) // 2]}, total {sum(units)} "
          f"(assert {sum(r['n_assert_units'] for r in per_task.values())}, "
          f"exception {sum(r['n_exception_units'] for r in per_task.values())}); "
          f">= {need}: {sum(u >= need for u in units)}")
    print(f"whole-test sensitivity subset (>= {need} valid tests): {len(subset)} tasks")
    for d in (tier2.UNITS, tier2.TESTS):
        for k in tier2.SCORES:
            ok = sum(r["designs"][d][k]["eligible"] for r in per_task.values())
            # A reason carries the task's own count ("fewer than 5 oracle units (3)"):
            # strip it BEFORE counting, or each distinct count is its own key.
            why = Counter(x.split(" (")[0] for r in per_task.values()
                          for x in r["designs"][d][k]["reasons"] if not r["designs"][d][k]["eligible"])
            print(f"  design={d:5s} score={k:12s} eligible={ok:4d}  ineligible because: {dict(why)}")
    runs = sum(r["expected_completion_runs"] for r in per_task.values())
    print(f"expected completion runs for rq4 degrade: {runs} "
          f"(RQ2 evaluate was {sum(r['n_completions'] for r in per_task.values())})")

    executed = [l for l, r in per_task.items() if r["expected_completion_runs"]]
    largest = sorted(executed, key=lambda l: -per_task[l]["n_units"])[:2]
    ineligible = sorted((l for l in per_task if l not in executed), key=lambda l: per_task[l]["n_units"])[:1]
    sample = [l for l in EDGE_CASES if l in per_task] + [l for l in largest + ineligible if l not in EDGE_CASES]
    print("\nrepresentative sample for a first rq4 degrade run:")
    for l in sample:
        r = per_task[l]
        flags = {f"{d}/{k}": r["designs"][d][k]["eligible"] for d in (tier2.UNITS, tier2.TESTS) for k in tier2.SCORES}
        print(f"  {r['task_index']:4d} {l:24s} units={r['n_units']:3d} valid_tests={r['n_valid_tests']:2d} "
              f"runs={r['expected_completion_runs']:5d} eligible={[k for k, v in flags.items() if v] or 'none'}")
    print("--array=" + ",".join(str(per_task[l]["task_index"]) for l in sample))
    print(f"written -> {out / 'eligibility_tier2.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
