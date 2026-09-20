#!/usr/bin/env python
"""Measure whether the extraction repair actually changed what is being measured.

Three checks, each answering a question the pass rates alone cannot:

1. FAILURE MODE   What do failing completions fail *with*? A benchmark is only
                  measuring coding ability if its failures are AssertionErrors.
                  Before the repair: gemma 94% crashes, qwen36 83%, qwen3-next
                  5%. Two of three models were scored on formatting compliance.

2. DEGRADATION    How many tasks change their pass@1 when half the assertions
                  are removed? This is RQ4's whole premise. Before: 2 of 164 --
                  because you cannot rescue a SyntaxError by deleting asserts.
                  Read at the 50% level: the old int() truncation confounded the
                  20% level but touched only 1 task at 50%.

3. DIVERGENCE     How many tasks have a pairwise rate exactly equal to
                  g(n-g)/C(n,2)? That is the algebraic signature of "g crashing
                  solutions against the rest" -- divergence measuring breakage
                  rather than disagreement. Before: 72 of 164.

Check 2 needs results/rq4, check 3 needs results/rq3; each is skipped with a
note if its stage has not been re-run yet, so this is useful after every phase.

Usage:
    .venv/Scripts/python.exe scripts/verify_repair_effect.py
    .venv/Scripts/python.exe scripts/verify_repair_effect.py --baseline results_pre_repair
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.data_loader import load_humaneval, task_label  # noqa: E402
from meta_real_eval.core.sandbox import execute                          # noqa: E402
from meta_real_eval.rq2.evaluator import build_solution_code             # noqa: E402

SEMANTIC = "AssertionError"


def _load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _is_stale(results: Path, stage: Path) -> bool:
    """True if `stage` was produced before the current rq2/evaluate output.

    RQ3 and RQ4 both consume RQ2's pass rates, so re-running RQ2 alone leaves
    them holding numbers derived from the previous evaluation. Comparing those
    against a pre-repair baseline reads as "the repair changed nothing", when
    in fact nothing downstream has been recomputed yet -- the single most
    misleading way to read this report.
    """
    ref = results / "rq2" / "evaluate"
    if not ref.exists() or not stage.exists():
        return False
    newest_rq2 = max((p.stat().st_mtime for p in ref.glob("*/pass_rates.json")),
                     default=0.0)
    newest_stage = max((p.stat().st_mtime for p in stage.glob("*/*.json")), default=0.0)
    return newest_stage < newest_rq2


# --- check 1 ---------------------------------------------------------------

def failure_modes(results: Path, relation: str, per_cell: int, workers: int) -> dict:
    """Re-execute failing completions and bucket them by their last stderr line."""
    tasks = {t.task_index: t for t in load_humaneval()}
    jobs = []
    for i, task in tasks.items():
        gen = results / "rq2" / "generate" / f"HumanEval_{i}" / "completions.json"
        ev = results / "rq2" / "evaluate" / f"HumanEval_{i}" / "pass_rates.json"
        if not gen.exists() or not ev.exists():
            continue
        completions = _load(gen).get(relation, {})
        flags = _load(ev).get(relation, {})
        for model_id, comps in completions.items():
            per_completion = flags.get(model_id, {}).get("per_completion", [])
            taken = 0
            for comp, ok in zip(comps, per_completion):
                if ok or taken >= per_cell:
                    continue
                taken += 1
                jobs.append((task, model_id, comp))

    def run(job):
        task, model_id, comp = job
        code = build_solution_code(comp, task.prompt, task.entry_point)
        result = execute(code, task.test + f"\ncheck({task.entry_point})\n", 10.0)
        if result.timed_out:
            return model_id, "TIMEOUT"
        lines = [ln for ln in result.stderr.strip().splitlines() if ln.strip()]
        return model_id, (lines[-1].split(":")[0] if lines else "no-error")

    buckets: dict[str, Counter] = defaultdict(Counter)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for model_id, kind in pool.map(run, jobs):
            buckets[model_id][kind] += 1
    return buckets


# --- check 2 ---------------------------------------------------------------

def degradation_bite(results: Path, level: str) -> dict | None:
    root = results / "rq4" / "degrade"
    if not root.exists():
        return None
    changed = order_changed = total = 0
    for td in sorted(root.iterdir()):
        path = td / "degradation_analysis.json"
        if not path.exists():
            continue
        data = _load(path)
        intact = data.get("0.0", {}).get("pass_at_1", {}).get("original")
        worse = data.get(level, {}).get("pass_at_1", {}).get("original")
        if not intact or not worse:
            continue
        total += 1
        if intact != worse:
            changed += 1
        rank_a = sorted(intact, key=lambda m: -intact[m])
        rank_b = sorted(worse, key=lambda m: -worse[m])
        if rank_a != rank_b:
            order_changed += 1
    return {"level": level, "n_tasks": total,
            "pass_at_1_changed": changed, "model_order_changed": order_changed}


# --- check 3 ---------------------------------------------------------------

def crash_driven_divergence(results: Path) -> dict | None:
    root = results / "rq3" / "execute"
    if not root.exists():
        return None
    exact = total = undefined = 0
    for td in sorted(root.iterdir()):
        path = td / "divergence.json"
        if not path.exists():
            continue
        data = _load(path)
        total += 1
        rate = data.get("pairwise_disagreement_rate")
        if rate is None:
            undefined += 1
            continue
        n = data.get("n_solutions", 0)
        if n < 2:
            continue
        broken = sum(1 for s in data.get("solutions", [])
                     if s.get("consensus_disagreement_rate", 0) >= 0.9)
        if broken and data["consensus"].get("n_inputs_with_consensus", 0):
            predicted = broken * (n - broken) / math.comb(n, 2)
            if abs(rate - predicted) < 1e-9:
                exact += 1
    return {"n_tasks": total, "rate_equals_crash_signature": exact,
            "rate_undefined": undefined}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", default=str(REPO_ROOT / "results"))
    parser.add_argument("--baseline", default=str(REPO_ROOT / "results_pre_repair"),
                        help="pre-repair tree to compare against (skipped if absent)")
    parser.add_argument("--relation", default="original")
    parser.add_argument("--per-cell", type=int, default=2,
                        help="failing completions sampled per (task, model) cell")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)

    results = Path(args.results)
    baseline = Path(args.baseline)
    random.seed(0)

    print("=" * 78)
    print(f"CHECK 1 - failure modes under '{args.relation}' "
          f"(<= {args.per_cell} failing completions per cell)")
    print("=" * 78)
    after = failure_modes(results, args.relation, args.per_cell, args.workers)
    before = (failure_modes(baseline, args.relation, args.per_cell, args.workers)
              if (baseline / "rq2" / "evaluate").exists() else {})

    for model_id in sorted(set(after) | set(before)):
        print(f"\n  {model_id}")
        for tag, buckets in (("before", before.get(model_id)), ("after", after.get(model_id))):
            if not buckets:
                continue
            total = sum(buckets.values())
            crashes = total - buckets.get(SEMANTIC, 0)
            share = crashes / total * 100 if total else 0.0
            top = ", ".join(f"{k}={v}" for k, v in buckets.most_common(4))
            print(f"    {tag:6s} n={total:5d}  crashes {share:5.1f}%   {top}")
    print("\n  Success = crash share falls sharply; failures become AssertionError,")
    print("  i.e. the model is being scored on its logic rather than its formatting.")

    print()
    print("=" * 78)
    print("CHECK 2 - does removing half the assertions move anything?")
    print("=" * 78)
    bite = degradation_bite(results, "0.5")
    if bite is None:
        print("  results/rq4/degrade not present - re-run RQ4, then check again.")
    elif _is_stale(results, results / "rq4" / "degrade"):
        print("  STALE: results/rq4/degrade predates the current rq2/evaluate output.")
        print("  It still holds numbers derived from the previous pass rates, so any")
        print("  comparison here would read as 'the repair changed nothing'.")
        print("  Re-run rq4 degrade/augment before trusting this check.")
    else:
        old = degradation_bite(baseline, "0.5")
        if old:
            print(f"  before: {old['pass_at_1_changed']}/{old['n_tasks']} tasks changed pass@1, "
                  f"{old['model_order_changed']} changed model order")
        print(f"  after : {bite['pass_at_1_changed']}/{bite['n_tasks']} tasks changed pass@1, "
              f"{bite['model_order_changed']} changed model order")
        print("\n  If this stays near zero, RQ4's null is a real finding about")
        print("  HumanEval's redundant assertions - reportable, but only once the")
        print("  extraction artifact is ruled out.")

    print()
    print("=" * 78)
    print("CHECK 3 - is divergence still just counting crashes?")
    print("=" * 78)
    crash = crash_driven_divergence(results)
    if crash is None:
        print("  results/rq3/execute not present - re-run RQ3, then check again.")
    elif _is_stale(results, results / "rq3" / "execute"):
        print("  STALE: results/rq3/execute predates the current rq2/evaluate output.")
        print("  Its divergence rates were computed from the previous pass rates.")
        print("  Re-run rq3 execute before trusting this check.")
    else:
        old = crash_driven_divergence(baseline)
        if old:
            print(f"  before: {old['rate_equals_crash_signature']}/{old['n_tasks']} tasks "
                  f"match g(n-g)/C(n,2)")
        print(f"  after : {crash['rate_equals_crash_signature']}/{crash['n_tasks']} tasks "
              f"match g(n-g)/C(n,2)   ({crash['rate_undefined']} undefined)")
        print("\n  Success = near zero: the rate reflects disagreement between working")
        print("  solutions, not how many of them were broken.")


if __name__ == "__main__":
    main()
