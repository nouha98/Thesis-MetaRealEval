#!/usr/bin/env python
"""Prove Tier 1 is unchanged by the benchmark adapter.

Re-scores the *stored* Tier 1 completions (``results/rq2/generate``) through
``HumanEvalBenchmark`` and compares every per-completion verdict with the
stored ``results/rq2/evaluate/<task>/pass_rates.json``. Any mismatch means
the adapter changed Tier 1 behaviour, and the script exits 1.

    .venv/bin/python scripts/verify_tier1_unchanged.py --tasks 0 2 10 32 38

Subprocess execution is not bit-for-bit deterministic under heavy load (a
borderline completion can time out on one run and not another), so a
mismatch is re-run once with the *legacy* path before it is reported: a
completion whose legacy re-run also disagrees with the stored verdict is
environment flakiness, not an adapter change, and is reported separately.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.benchmarks.humaneval import HumanEvalBenchmark  # noqa: E402
from meta_real_eval.rq2.evaluator import _run_completion  # noqa: E402

# Tier 1 results have lived at both locations; prefer the explicit --results.
DEFAULT_RESULTS = next((d for d in (REPO_ROOT / "results_tier1", REPO_ROOT / "results") if d.exists()),
                       REPO_ROOT / "results")


def _adapter_verdict(task_index: int, completion: str, timeout_s: float) -> bool:
    bench = HumanEvalBenchmark()
    task = bench.load_tasks([task_index])[0]
    return bench.run_suite(task, bench.build_solution(task, completion), timeout_s=timeout_s).passed_all


def _legacy_verdict(task_index: int, completion: str, timeout_s: float) -> bool:
    task = HumanEvalBenchmark().load_tasks([task_index])[0].raw
    return _run_completion(completion, task.prompt, task.test, task.entry_point, timeout_s)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", type=int, nargs="+", default=[0, 2, 10, 32, 38])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS, help="Tier 1 results directory")
    args = parser.parse_args()
    rq2 = args.results / "rq2"
    print(f"comparing against {args.results}")

    bench = HumanEvalBenchmark()
    jobs = []  # (task_index, relation, model, i, completion, stored)
    for task in bench.load_tasks(args.tasks):
        gen = rq2 / "generate" / task.label / "completions.json"
        ev = rq2 / "evaluate" / task.label / "pass_rates.json"
        if not (gen.exists() and ev.exists()):
            print(f"skip {task.label}: no stored results")
            continue
        completions = json.loads(gen.read_text(encoding="utf-8"))
        stored = json.loads(ev.read_text(encoding="utf-8"))
        for relation, by_model in completions.items():
            for model, comps in by_model.items():
                flags = stored.get(relation, {}).get(model, {}).get("per_completion")
                if flags is None or len(flags) != len(comps):
                    continue
                jobs += [(task.task_index, relation, model, i, c, f)
                         for i, (c, f) in enumerate(zip(comps, flags))]

    print(f"re-scoring {len(jobs)} stored completions through the adapter ...")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        verdicts = list(pool.map(_adapter_verdict, [j[0] for j in jobs], [j[4] for j in jobs],
                                 [args.timeout] * len(jobs), chunksize=8))

    suspects = [j for j, v in zip(jobs, verdicts) if v != j[5]]
    adapter_changes, flaky = [], []
    for j in suspects:
        (flaky if _legacy_verdict(j[0], j[4], args.timeout) != j[5] else adapter_changes).append(j)

    print(f"agree: {len(jobs) - len(suspects)}/{len(jobs)}")
    print(f"environment flakiness (legacy path also disagrees with stored): {len(flaky)}")
    for j in flaky:
        print(f"  {j[0]} {j[1]} {j[2]} #{j[3]} stored={j[5]}")
    print(f"ADAPTER CHANGES: {len(adapter_changes)}")
    for j in adapter_changes:
        print(f"  {j[0]} {j[1]} {j[2]} #{j[3]} stored={j[5]}")
    return 1 if adapter_changes else 0


if __name__ == "__main__":
    raise SystemExit(main())
