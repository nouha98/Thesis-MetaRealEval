#!/usr/bin/env python
"""Profile all 164 HumanEval tasks and pick a stratified subset for ablation.

Why profile before ablating: whether Stage 0's equivalence filter matters is
not uniform across the benchmark. It depends on whether the generated fuzz
inputs are meaningful for a task at all (a task whose inputs all crash the
canonical solution yields no divergence signal, so *every* mutant looks
"equivalent"), on how complex the signature is (which drives input-generation
quality), and -- most directly -- on how much the filter actually *does* on
that task. Sampling 30 tasks at random would over-represent the easy majority
and could produce a subset with too little filter activity to expose any
effect at all.

Equivalence activity is measured fresh, not read from results/stage0
-------------------------------------------------------------------
The obvious source for "how equivalence-heavy is this task" is the previous
Stage 0 run. We deliberately do not use it for selection: the corpus builder
changed (ROR site targeting, docstring deletion), so those verdicts describe a
different mutant population. Instead a low-fidelity equivalence probe runs
here against today's corpus -- fewer fuzz inputs than the real filter, enough
to rank tasks for sampling, never used as a result. Prior Stage 0 numbers are
still recorded in the profile for reference and flagged stale.

Features collected per task
---------------------------
signature      n params, how many carry annotations, inferred parameter type
               tags (from real test-derived inputs where available, which is
               what the equivalence checker itself uses)
examples       how many concrete input tuples can be recovered from the
               benchmark's own test suite
input health   fraction of generated inputs on which the *canonical* solution
               errors or times out -- the "prior bad inputs" signal, and the
               strongest predictor of a meaningless equivalence verdict
sites          AOR / ROR / SDL mutable-site counts (operator density)
mutants        mutant counts per operator from the current corpus builder
equiv activity low-fidelity equivalence rate over today's corpus (selection only)

Outputs
-------
    results/ablation/task_profiles.json   every task, every feature
    results/ablation/subset.json          the selected stratified subset

Usage
-----
    .venv/Scripts/python.exe scripts/profile_tasks.py
    .venv/Scripts/python.exe scripts/profile_tasks.py --n-select 30 --n-probe 25
    .venv/Scripts/python.exe scripts/profile_tasks.py --no-probe   # fast, loses both probes
"""
from __future__ import annotations

import argparse
import ast
import json
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.config import Config  # noqa: E402
from meta_real_eval.core.data_loader import load_humaneval, task_label  # noqa: E402
from meta_real_eval.stage0.corpus_builder import (  # noqa: E402
    _binop_slots, _cmp_slots, _deletable_stmt_indices, generate_mutants,
)
from meta_real_eval.stage0.equivalence import (  # noqa: E402
    TIMEOUT, _extract_param_annotations, _extract_test_inputs, _infer_tags,
    check_equivalence, compute_canonical_outputs,
)

OUT_DIR = REPO_ROOT / "results" / "ablation"
# Strata with at most this many tasks are selected in full rather than sampled
# (see select_stratified).
SMALL_STRATUM = 3


def _equiv_job(args):
    """Module-level so ProcessPoolExecutor can pickle it on Windows."""
    task, mutant, n_fuzz, timeout_s, seed, canon_outs = args
    return check_equivalence(task, mutant, n_fuzz, timeout_s, seed, canon_outs).is_equivalent


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _entry_func(task) -> ast.FunctionDef | None:
    tree = ast.parse(task.prompt + task.canonical_solution)
    return next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == task.entry_point), None)


def _classify_signature(tags: list[str]) -> str:
    """nested / container / string / scalar, from inferred parameter type tags.

    Strings are split out from the other scalars deliberately: they are the
    scalar type whose random generation is most likely to violate an unstated
    precondition (digit-strings, balanced brackets, non-empty), so they fail
    differently from ints and floats and deserve their own stratum.
    """
    if not tags:
        return "unknown"
    depth = max(t.count("[") for t in tags)
    if depth >= 2:
        return "nested"
    if depth == 1:
        return "container"
    return "string" if any(t == "str" for t in tags) else "scalar"


def _classify_input_health(error_rate: float | None) -> str:
    """How usable the generated fuzz inputs are for this task.

    A high canonical error rate means the differential fuzzer compares two
    crashes and concludes "equivalent" -- the exact false-positive mode the
    input-generator fix targeted, so these tasks matter most to the ablation.
    """
    if error_rate is None:
        return "unprobed"
    return "broken" if error_rate >= 0.5 else "noisy" if error_rate > 0.1 else "clean"


def _classify_equiv_activity(rate: float | None) -> str:
    if rate is None:
        return "unprobed"
    return "none" if rate == 0 else "low" if rate < 0.25 else "high"


def profile_task(task, cfg: Config, n_probe: int, probe: bool) -> dict:
    label = task_label(task)
    test_inputs = _extract_test_inputs(task.test, task.entry_point)
    if test_inputs:
        tags, tag_source = _infer_tags(test_inputs), "test_derived"
    else:
        tags = _extract_param_annotations(task.prompt + task.canonical_solution, task.entry_point)
        tag_source = "annotations_fallback"

    mutants = generate_mutants(
        prompt=task.prompt, canonical_solution=task.canonical_solution,
        entry_point=task.entry_point, operators=cfg.rq1.operators,
        seed=cfg.project.seed,
    )
    by_op = Counter(m.operator for m in mutants)
    fn = _entry_func(task)
    tree = ast.parse(task.prompt + task.canonical_solution)
    args_list = list(fn.args.args) if fn else []

    error_rate = equiv_rate = None
    if probe:
        canon_outs = compute_canonical_outputs(
            task=task, n_fuzz_inputs=n_probe, timeout_s=cfg.execution.timeout_s,
            seed=cfg.project.seed, cpu_workers=cfg.execution.cpu_workers,
        )
        bad = sum(1 for o in canon_outs
                  if o == TIMEOUT or (isinstance(o, str) and o.startswith("__error__")))
        error_rate = bad / len(canon_outs) if canon_outs else None

        if mutants:
            jobs = [(task, m, n_probe, cfg.execution.timeout_s, cfg.project.seed, canon_outs)
                    for m in mutants]
            with ProcessPoolExecutor(max_workers=cfg.execution.cpu_workers) as pool:
                verdicts = list(pool.map(_equiv_job, jobs))
            equiv_rate = sum(verdicts) / len(verdicts)
        else:
            equiv_rate = 0.0

    prof = {
        "task_id": task.task_id,
        "task_index": task.task_index,
        "task_label": label,
        "entry_point": task.entry_point,
        "n_params": len(args_list),
        "n_annotated": sum(1 for a in args_list if a.annotation is not None),
        "n_aor_sites": len(_binop_slots(tree)),
        "n_ror_sites": len(_cmp_slots(tree)),
        "n_sdl_sites": len(_deletable_stmt_indices(fn)) if fn else 0,
        "param_tags": tags,
        "tag_source": tag_source,
        "n_test_derived_inputs": len(test_inputs),
        "canonical_error_rate": error_rate,
        "probe_equiv_rate": equiv_rate,
        "n_mutants": len(mutants),
        "n_aor": by_op["AOR"], "n_ror": by_op["ROR"], "n_sdl": by_op["SDL"],
    }
    prof["n_total_sites"] = prof["n_aor_sites"] + prof["n_ror_sites"] + prof["n_sdl_sites"]
    # Tasks whose own tests yield no example inputs are their own stratum: the
    # generator has no ground truth to infer parameter types from, which is the
    # exact condition that produced false "equivalent" verdicts before the
    # input-generator fix. They are too diagnostic to risk sampling away.
    prof["signature_class"] = ("no_examples" if tag_source == "annotations_fallback"
                               else _classify_signature(tags))
    prof["input_health"] = _classify_input_health(error_rate)
    prof["equiv_activity"] = _classify_equiv_activity(equiv_rate)

    # Reference only -- never used for selection (see module docstring).
    s0 = REPO_ROOT / "results" / "stage0" / label / "equiv_filter.json"
    if s0.exists():
        rows = json.loads(s0.read_text())
        n_eq = sum(1 for r in rows if r["is_equivalent"])
        prof["prior_stage0"] = {
            "n_mutants": len(rows), "n_equivalent": n_eq,
            "equiv_rate": n_eq / len(rows) if rows else 0.0,
            "stale": len(rows) != len(mutants),
            "used_for_selection": False,
        }
    else:
        prof["prior_stage0"] = None
    return prof


# ---------------------------------------------------------------------------
# Stratified selection
# ---------------------------------------------------------------------------

def _tercile(value: float, lo: float, hi: float) -> str:
    return "low" if value <= lo else "high" if value > hi else "medium"


def select_stratified(profiles: list[dict], n_select: int, seed: int) -> tuple[list[dict], dict]:
    """Sample n_select tasks across (input_health x signature_class) strata.

    Proportional allocation with a floor of one task per non-empty stratum, so
    rare-but-important cells ('broken' input health above all) cannot vanish.
    The remainder goes by largest fractional share.

    Within a stratum, tasks are ordered by *equivalence activity* and sampled
    at evenly spaced ranks. That is the axis the ablation is actually about, so
    spreading on it inside every cell buys coverage of low/medium/high filter
    activity without adding a third stratification dimension that would shatter
    30 tasks across 27 cells. Ties break on mutant count, which spreads sparse
    and dense tasks too. Deterministic given the seed.
    """
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in profiles:
        strata[(p["input_health"], p["signature_class"])].append(p)

    # Rare strata are taken whole. A stratum this small costs almost nothing of
    # the budget, and proportional allocation would round it down to a single
    # task (or none) -- losing most of the corpus's only examples of exactly the
    # conditions the ablation is meant to stress.
    small = {k: v for k, v in strata.items() if len(v) <= SMALL_STRATUM}
    large = {k: v for k, v in strata.items() if len(v) > SMALL_STRATUM}
    alloc = {k: len(v) for k, v in small.items()}

    budget = n_select - sum(alloc.values())
    if large and budget > 0:
        base = {k: 1 for k in large}
        remaining = max(budget - len(base), 0)
        pop_large = sum(len(v) for v in large.values())
        shares = {k: (len(v) / pop_large) * remaining for k, v in large.items()}
        for k in large:
            alloc[k] = base[k] + int(shares[k])
        leftover = n_select - sum(alloc.values())
        for k in sorted(large, key=lambda k: -(shares[k] - int(shares[k])))[:max(leftover, 0)]:
            alloc[k] += 1

    rng = random.Random(seed)
    selected: list[dict] = []
    for k, n in sorted(alloc.items()):
        pool = sorted(strata[k], key=lambda p: (p["probe_equiv_rate"] if p["probe_equiv_rate"] is not None else -1,
                                                 p["n_mutants"], p["task_index"]))
        n = min(n, len(pool))
        if n == 0:
            continue
        picks = [pool[len(pool) // 2]] if n == 1 else [
            pool[round(i * (len(pool) - 1) / (n - 1))] for i in range(n)
        ]
        seen = {p["task_id"] for p in picks}
        if len(seen) < n:  # rounding collision: backfill from the same stratum
            for cand in rng.sample(pool, len(pool)):
                if len(seen) >= n:
                    break
                if cand["task_id"] not in seen:
                    picks.append(cand)
                    seen.add(cand["task_id"])
        selected.extend(picks)

    selected.sort(key=lambda p: p["task_index"])
    breakdown = {f"{h}/{s}": {"population": len(v), "selected": alloc.get((h, s), 0)}
                 for (h, s), v in sorted(strata.items())}
    return selected, breakdown


def coverage_report(profiles: list[dict], selected: list[dict]) -> tuple[list[str], list[str]]:
    """Check the subset actually covers every populated category on every axis.

    Stratifying on two axes does not guarantee coverage on the others, so this
    verifies rather than assumes -- a category present in the corpus but absent
    from the subset is reported as a WARN, not silently accepted.
    """
    lines, warnings = [], []
    n_mut = sorted(p["n_mutants"] for p in profiles)
    lo, hi = n_mut[len(n_mut) // 3], n_mut[2 * len(n_mut) // 3]
    for p in profiles + selected:
        p["_density"] = _tercile(p["n_mutants"], lo, hi)

    for axis, label in (("signature_class", "signature"), ("input_health", "input health"),
                        ("equiv_activity", "equiv activity"), ("_density", "mutant density"),
                        # annotations_fallback == no usable examples in the task's own
                        # tests: the previously-problematic input-generation cases.
                        ("tag_source", "input derivation")):
        pop = Counter(p[axis] for p in profiles)
        sel = Counter(p[axis] for p in selected)
        cells = " ".join(f"{v}={sel.get(v, 0)}/{pop[v]}" for v in sorted(pop))
        missing = [v for v in pop if pop[v] > 0 and sel.get(v, 0) == 0]
        status = "OK" if not missing else f"WARN missing {', '.join(missing)}"
        lines.append(f"  {label:16s} {cells:52s} {status}")
        if missing:
            warnings.append(f"{label}: {', '.join(missing)} present in corpus but absent from subset")
    for p in profiles + selected:
        p.pop("_density", None)
    return lines, warnings


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(REPO_ROOT / "config" / "default.yaml"))
    parser.add_argument("--n-select", type=int, default=30, help="target subset size")
    parser.add_argument("--n-probe", type=int, default=25,
                        help="fuzz inputs per task for the input-health / equivalence probes")
    parser.add_argument("--no-probe", action="store_true",
                        help="skip both probes (fast, but loses the two strongest features)")
    args = parser.parse_args()

    cfg = Config.from_yaml(args.config)
    tasks = load_humaneval()
    probe = not args.no_probe

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Profiling {len(tasks)} tasks"
          f"{f' (probes: {args.n_probe} inputs/task)' if probe else ' (probes skipped)'}...")

    profiles = []
    for i, task in enumerate(tasks, 1):
        profiles.append(profile_task(task, cfg, args.n_probe, probe))
        if i % 20 == 0 or i == len(tasks):
            print(f"  {i}/{len(tasks)}")

    (OUT_DIR / "task_profiles.json").write_text(json.dumps(profiles, indent=2))
    selected, breakdown = select_stratified(profiles, args.n_select, cfg.project.seed)
    cov_lines, cov_warnings = coverage_report(profiles, selected)

    (OUT_DIR / "subset.json").write_text(json.dumps({
        "n_selected": len(selected),
        "seed": cfg.project.seed,
        "probe_n_inputs": args.n_probe if probe else None,
        "strata_breakdown": breakdown,
        "coverage_warnings": cov_warnings,
        "task_indices": [p["task_index"] for p in selected],
        "tasks": [{k: p[k] for k in ("task_id", "task_index", "task_label", "input_health",
                                      "signature_class", "equiv_activity", "n_total_sites",
                                      "n_mutants", "canonical_error_rate", "probe_equiv_rate",
                                      "n_test_derived_inputs")}
                  for p in selected],
    }, indent=2))

    # ---- report ----
    print("\n" + "=" * 78)
    print("CORPUS PROFILE")
    print("=" * 78)
    for feat in ("input_health", "signature_class", "equiv_activity", "tag_source"):
        print(f"\n{feat}:")
        for val, n in Counter(p[feat] for p in profiles).most_common():
            print(f"    {val:22s} {n:4d} ({100*n/len(profiles):5.1f}%)")

    no_examples = [p for p in profiles if p["n_test_derived_inputs"] == 0]
    print(f"\ntasks with NO test-derived example inputs: {len(no_examples)}"
          + (f"  {[p['task_id'] for p in no_examples]}" if no_examples else ""))
    if probe:
        worst = sorted((p for p in profiles if p["canonical_error_rate"]),
                       key=lambda p: -p["canonical_error_rate"])[:8]
        print("\nhighest canonical error rate (weakest equivalence signal):")
        for p in worst:
            print(f"    {p['task_id']:16s} {p['canonical_error_rate']*100:5.1f}%  tags={p['param_tags']}")

    stale = [p for p in profiles if p["prior_stage0"] and p["prior_stage0"]["stale"]]
    if stale:
        print(f"\nprior Stage 0 verdicts stale vs. current corpus: {len(stale)}/{len(profiles)} tasks"
              "\n    (recorded for reference only; selection uses the fresh probe instead)")

    print("\n" + "=" * 78)
    print(f"STRATIFIED SUBSET  ({len(selected)} tasks)")
    print("=" * 78)
    print(f"{'stratum (input_health/signature)':38s} {'pop':>5s} {'sel':>5s}")
    for k, v in breakdown.items():
        print(f"  {k:36s} {v['population']:5d} {v['selected']:5d}")

    print("\nCOVERAGE CHECK  (selected/population per category)")
    for line in cov_lines:
        print(line)
    if cov_warnings:
        print("\n  !! subset misses categories present in the corpus:")
        for w in cov_warnings:
            print(f"     - {w}")
        print("     consider raising --n-select")

    print("\nselected task indices:")
    print("  " + " ".join(str(p["task_index"]) for p in selected))
    print(f"\nWrote {OUT_DIR / 'task_profiles.json'}")
    print(f"Wrote {OUT_DIR / 'subset.json'}")
    print("\nNext:  .venv/Scripts/python.exe scripts/stage0_ablation.py")


if __name__ == "__main__":
    main()
