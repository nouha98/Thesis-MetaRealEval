#!/usr/bin/env python
"""Ablate Stage 0's equivalence filter: does it change the RQ1 conclusion?

Two conditions over the *same* mutant population, so the only thing that
differs is whether equivalent mutants are excluded before kill-rate scoring:

    WITHOUT   every generated mutant is scored, including ones that are
              behaviourally identical to the canonical solution and therefore
              can never be killed -- they deflate the kill rate
    WITH      equivalent mutants are excluded first, as the pipeline does

Identical population is enforced, not assumed: one corpus is built, one
equivalence verdict and one kill outcome computed per mutant, and the two
conditions are two different *views* over those same tables. The kill outcome
of a given mutant is by construction the same number in both conditions.

What is recomputed vs. reused
-----------------------------
Traditional mutants are regenerated with the current corpus builder, and every
equivalence verdict is recomputed with the current checker; nothing is read
from results/stage0 or results/rq1/evaluate, which predate those fixes. LLM
mutants are the one reuse: they cannot be regenerated without live API calls,
so they come from results/rq1/generate/<task>/llm_mutants.json and the report
states how many and from how many tasks. This is an ablation of the *filter*,
deliberately not a new LLM-generation experiment.

The statistic that actually answers the question
------------------------------------------------
Comparing traditional vs. LLM *within* each condition tests RQ1a, not Stage 0.
To test Stage 0 you need the paired per-task quantity that Stage 0 is supposed
to move: the trad-minus-LLM gap. So the headline test is a paired Wilcoxon over
per-task gaps, WITH vs WITHOUT, on the tasks where both conditions define a gap
(filtering can strip every LLM mutant from a task, which would otherwise leave
the two conditions with non-comparable task sets). The within-condition tests
are still reported, labelled as what they are.

Per-task artefacts are written for manual inspection:

    results/ablation/<task_label>/mutants.json      the corpus scored
    results/ablation/<task_label>/equivalence.json  per-mutant verdict + reason
    results/ablation/<task_label>/kill.json         per-mutant kill outcome
    results/ablation/<task_label>/comparison.json   this task's WITH/WITHOUT gaps

Usage
-----
    .venv/Scripts/python.exe scripts/stage0_ablation.py
    .venv/Scripts/python.exe scripts/stage0_ablation.py --tasks 0 1 40   # inspect a few
    .venv/Scripts/python.exe scripts/stage0_ablation.py --n-fuzz 100     # faster, lower fidelity
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.analysis.statistics import wilcoxon_test  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402
from meta_real_eval.core.data_loader import load_humaneval, task_label  # noqa: E402
from meta_real_eval.rq1.kill_rate import _run_one as run_tests  # noqa: E402
from meta_real_eval.stage0.corpus_builder import Mutant, generate_mutants  # noqa: E402
from meta_real_eval.stage0.equivalence import check_equivalence, compute_canonical_outputs  # noqa: E402

OUT_DIR = REPO_ROOT / "results" / "ablation"
TRADITIONAL_OPS = {"AOR", "ROR", "SDL"}
# Kept identical to scripts/analyze_results.py so both reports mean the same
# thing by "trivially killed".
TRIVIALLY_KILLED_SDL_KINDS = {"Return", "Import", "ImportFrom", "FunctionDef"}
CONDITIONS = ("without", "with")


# --- workers (module level so ProcessPoolExecutor can pickle them on Windows) ---
# Every result is keyed by (task_id, mutant_id): ids like AOR_0 repeat in every
# task, so a dict keyed on mutant_id alone silently lets later tasks overwrite
# earlier ones and produces plausible-looking nonsense.

def _equiv_job(args):
    task, mutant, n_fuzz, timeout_s, seed, canon_outs = args
    r = check_equivalence(task, mutant, n_fuzz, timeout_s, seed, canon_outs)
    return (task.task_id, mutant.mutant_id), {"is_equivalent": r.is_equivalent,
                                               "reason": r.reason,
                                               "n_inputs_tested": r.n_inputs_tested}


def _kill_job(args):
    task_id, mutant_code, test_code, entry_point, timeout_s, mutant_id = args
    return (task_id, mutant_id), run_tests(mutant_code, test_code, entry_point, timeout_s)


def _sdl_kind(description: str) -> str | None:
    if not description.startswith("Delete "):
        return None
    kind, sep, _ = description[len("Delete "):].partition(" statement ")
    return kind if (sep and kind) else None


def _is_trivial(m: Mutant) -> bool:
    return m.operator == "SDL" and _sdl_kind(m.description) in TRIVIALLY_KILLED_SDL_KINDS


def _rate(k: int, n: int) -> float | None:
    return k / n if n else None


def _pct(x: float | None) -> str:
    return "  n/a" if x is None else f"{x*100:5.1f}%"


def _pts(x: float | None) -> str:
    return "n/a" if x is None else f"{x:+.1f} pts"


def load_subset(args) -> list[int]:
    if args.tasks:
        return args.tasks
    path = OUT_DIR / "subset.json"
    if not path.exists():
        raise SystemExit(f"No subset at {path}.\n"
                         "Run scripts/profile_tasks.py first, or pass --tasks explicitly.")
    return json.loads(path.read_text())["task_indices"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(REPO_ROOT / "config" / "default.yaml"))
    parser.add_argument("--tasks", type=int, nargs="+", default=None,
                        help="explicit task indices (default: results/ablation/subset.json)")
    parser.add_argument("--n-fuzz", type=int, default=None,
                        help="fuzz inputs per mutant (default: config stage0.n_fuzz_inputs)")
    args = parser.parse_args()

    cfg = Config.from_yaml(args.config)
    n_fuzz = args.n_fuzz or cfg.stage0.n_fuzz_inputs
    indices = set(load_subset(args))
    tasks = [t for t in load_humaneval() if t.task_index in indices]
    prof_path = OUT_DIR / "task_profiles.json"
    profiles = ({p["task_id"]: p for p in json.loads(prof_path.read_text())}
                if prof_path.exists() else {})

    print(f"Ablation over {len(tasks)} task(s), {n_fuzz} fuzz inputs/mutant")
    print(f"  {[t.task_id for t in tasks]}\n")

    # ---- 1. corpus: traditional regenerated, LLM reused ----
    per_task: dict[str, list[Mutant]] = {}
    n_llm = n_tasks_llm = 0
    for task in tasks:
        trad = generate_mutants(
            prompt=task.prompt, canonical_solution=task.canonical_solution,
            entry_point=task.entry_point, operators=cfg.rq1.operators, seed=cfg.project.seed,
        )
        llm_path = REPO_ROOT / "results" / "rq1" / "generate" / task_label(task) / "llm_mutants.json"
        llm = []
        if llm_path.exists():
            llm = [Mutant(mutant_id=m["mutant_id"], operator=m["operator"],
                          description=m["description"], code=m["code"])
                   for m in json.loads(llm_path.read_text())]
            if llm:
                n_tasks_llm += 1
                n_llm += len(llm)
        per_task[task.task_id] = trad + llm

    n_trad = sum(1 for ms in per_task.values() for m in ms if m.operator in TRADITIONAL_OPS)
    print(f"Corpus: {n_trad} traditional (REGENERATED with the current builder), "
          f"{n_llm} LLM (REUSED from disk, {n_tasks_llm}/{len(tasks)} tasks)")
    if n_llm == 0:
        print("  NOTE: no LLM mutants on disk -- traditional-only run, no gap can be computed.")

    # ---- 2. equivalence (recomputed for every mutant) ----
    print("\nEquivalence checking (current checker, nothing reused)...")
    jobs = []
    for task in tasks:
        canon = compute_canonical_outputs(
            task=task, n_fuzz_inputs=n_fuzz, timeout_s=cfg.execution.timeout_s,
            seed=cfg.project.seed, cpu_workers=cfg.execution.cpu_workers,
        )
        jobs += [(task, m, n_fuzz, cfg.execution.timeout_s, cfg.project.seed, canon)
                 for m in per_task[task.task_id]]
    with ProcessPoolExecutor(max_workers=cfg.execution.cpu_workers) as pool:
        equiv = dict(pool.map(_equiv_job, jobs))

    # ---- 3. kill outcomes (computed ONCE; both conditions read this table) ----
    print("Kill-rate scoring against the real test suite...")
    kill_jobs = [(t.task_id, m.code, t.test, t.entry_point, cfg.execution.timeout_s, m.mutant_id)
                 for t in tasks for m in per_task[t.task_id]]
    with ProcessPoolExecutor(max_workers=cfg.execution.cpu_workers) as pool:
        killed = dict(pool.map(_kill_job, kill_jobs))

    # ---- 4. per-task tallies ----
    agg = {c: Counter() for c in CONDITIONS}
    within = {c: {"trad": [], "llm": [], "tasks": []} for c in CONDITIONS}
    gap_rows = []               # tasks where BOTH conditions define a gap
    by_health = defaultdict(lambda: Counter())
    n_equiv_op, n_total_op = Counter(), Counter()
    n_mutants_total = n_equiv_total = 0

    for task in tasks:
        label = task_label(task)
        tdir = OUT_DIR / label
        tdir.mkdir(parents=True, exist_ok=True)
        mutants = per_task[task.task_id]
        n_mutants_total += len(mutants)

        tdir.joinpath("mutants.json").write_text(json.dumps(
            [{"mutant_id": m.mutant_id, "operator": m.operator,
              "description": m.description, "code": m.code} for m in mutants], indent=2))
        tdir.joinpath("equivalence.json").write_text(json.dumps(
            {m.mutant_id: equiv[(task.task_id, m.mutant_id)] for m in mutants}, indent=2))
        tdir.joinpath("kill.json").write_text(json.dumps(
            {m.mutant_id: killed[(task.task_id, m.mutant_id)] for m in mutants}, indent=2))

        n_eq = sum(1 for m in mutants if equiv[(task.task_id, m.mutant_id)]["is_equivalent"])
        n_equiv_total += n_eq
        health = profiles.get(task.task_id, {}).get("input_health", "unprofiled")
        by_health[health]["n_equiv"] += n_eq
        by_health[health]["n_total"] += len(mutants)
        for m in mutants:
            n_total_op[m.operator] += 1
            if equiv[(task.task_id, m.mutant_id)]["is_equivalent"]:
                n_equiv_op[m.operator] += 1

        task_view = {}
        for cond in CONDITIONS:
            c = Counter()
            for m in mutants:
                key = (task.task_id, m.mutant_id)
                if cond == "with" and equiv[key]["is_equivalent"]:
                    continue
                cat = "llm" if m.operator == "LLM" else "trad"
                c[f"{cat}_total"] += 1
                c[f"{cat}_killed"] += int(killed[key])
                if not _is_trivial(m):                      # sensitivity view
                    c[f"{cat}_nt_total"] += 1
                    c[f"{cat}_nt_killed"] += int(killed[key])
            agg[cond].update(c)

            tr = _rate(c["trad_killed"], c["trad_total"])
            lr = _rate(c["llm_killed"], c["llm_total"])
            if tr is not None and lr is not None:
                within[cond]["trad"].append(tr)
                within[cond]["llm"].append(lr)
                within[cond]["tasks"].append(task.task_id)
            task_view[cond] = {
                "trad_killed": c["trad_killed"], "trad_total": c["trad_total"],
                "llm_killed": c["llm_killed"], "llm_total": c["llm_total"],
                "trad_kill_rate": tr, "llm_kill_rate": lr,
                "gap_points": None if tr is None or lr is None else (tr - lr) * 100,
            }

        g_wo, g_w = task_view["without"]["gap_points"], task_view["with"]["gap_points"]
        if g_wo is not None and g_w is not None:
            gap_rows.append({"task_id": task.task_id, "input_health": health,
                             "gap_without": g_wo, "gap_with": g_w, "delta": g_w - g_wo})

        tdir.joinpath("comparison.json").write_text(json.dumps({
            "task_id": task.task_id, "input_health": health,
            "n_mutants": len(mutants), "n_equivalent": n_eq,
            "n_retained_with_stage0": len(mutants) - n_eq,
            "conditions": task_view,
            "gap_change_points": None if g_wo is None or g_w is None else g_w - g_wo,
        }, indent=2))

    # ---- 5. report ----
    print("\n" + "=" * 78)
    print("CORPUS")
    print("=" * 78)
    print(f"  mutants total     : {n_mutants_total}")
    print(f"  equivalent        : {n_equiv_total} ({_pct(_rate(n_equiv_total, n_mutants_total))})")
    print(f"  retained WITH     : {n_mutants_total - n_equiv_total}")
    print(f"  retained WITHOUT  : {n_mutants_total}  (no filtering)")

    results = {}
    for cond, title in (("without", "WITHOUT Stage 0 (all mutants scored)"),
                        ("with", "WITH Stage 0 (equivalent mutants excluded)")):
        a = agg[cond]
        tr, lr = _rate(a["trad_killed"], a["trad_total"]), _rate(a["llm_killed"], a["llm_total"])
        trnt = _rate(a["trad_nt_killed"], a["trad_nt_total"])
        lrnt = _rate(a["llm_nt_killed"], a["llm_nt_total"])
        results[cond] = {
            "retained": a["trad_total"] + a["llm_total"],
            "trad_killed": a["trad_killed"], "trad_total": a["trad_total"], "trad_kill_rate": tr,
            "llm_killed": a["llm_killed"], "llm_total": a["llm_total"], "llm_kill_rate": lr,
            "gap_points": None if tr is None or lr is None else (tr - lr) * 100,
            "trad_kill_rate_excl_trivial_sdl": trnt,
            "gap_points_excl_trivial_sdl": None if trnt is None or lrnt is None else (trnt - lrnt) * 100,
            "n_paired_tasks": len(within[cond]["tasks"]),
        }
        r = results[cond]
        print(f"\n--- {title} ---")
        print(f"  mutants scored       : {r['retained']}  "
              f"(traditional={a['trad_total']}, LLM={a['llm_total']})")
        print(f"  traditional kill rate: {a['trad_killed']}/{a['trad_total']} = {_pct(tr)}")
        print(f"  LLM kill rate        : {a['llm_killed']}/{a['llm_total']} = {_pct(lr)}")
        print(f"  trad - LLM gap       : {_pts(r['gap_points'])}")
        print(f"  tasks with BOTH categories: {r['n_paired_tasks']}/{len(tasks)}")

    # ---- 6. the test that actually addresses the question ----
    print("\n" + "=" * 78)
    print("DOES STAGE 0 CHANGE THE CONCLUSION?")
    print("=" * 78)
    gap_change = None
    gap_test = None
    if not gap_rows:
        print("  Cannot test: no task defines a gap in both conditions"
              " (needs traditional AND LLM mutants surviving in both).")
    else:
        gw = [r["gap_with"] for r in gap_rows]
        gwo = [r["gap_without"] for r in gap_rows]
        mean_wo, mean_w = sum(gwo) / len(gwo), sum(gw) / len(gw)
        gap_change = mean_w - mean_wo
        print(f"  Paired over {len(gap_rows)} task(s) defining a gap in BOTH conditions"
              f" (of {len(tasks)} run).")
        print(f"  mean per-task gap WITHOUT : {mean_wo:+.1f} pts")
        print(f"  mean per-task gap WITH    : {mean_w:+.1f} pts")
        print(f"  mean change (WITH-WITHOUT): {gap_change:+.1f} pts")
        gap_test = wilcoxon_test(gw, gwo)
        print(f"  paired Wilcoxon on the per-task GAP: "
              f"p={gap_test['p_value']:.4g}  cliffs_delta={gap_test.get('cliffs_delta', 'n/a')}")
        print("    ^ this is the Stage 0 effect: it tests the quantity the filter moves.")
        n_flip = sum(1 for r in gap_rows if (r["gap_with"] > 0) != (r["gap_without"] > 0))
        print(f"  tasks whose gap changes SIGN: {n_flip}/{len(gap_rows)}")

        pooled = {c: results[c]["gap_points"] for c in CONDITIONS}
        if pooled["with"] is not None and pooled["without"] is not None:
            print(f"\n  pooled gap {_pts(pooled['without'])} -> {_pts(pooled['with'])}"
                  f"  (change {pooled['with'] - pooled['without']:+.1f} pts)")
            if (pooled["with"] > 0) != (pooled["without"] > 0):
                print("  ** POOLED DIRECTION FLIPS -- filtering changes the qualitative claim.")
            else:
                print("  pooled direction unchanged: the filter rescales the gap, not its sign.")

    print("\n  Within-condition trad-vs-LLM (tests RQ1a, NOT the Stage 0 effect):")
    for cond in CONDITIONS:
        if within[cond]["trad"]:
            w = wilcoxon_test(within[cond]["trad"], within[cond]["llm"])
            print(f"    {cond:8s} n={len(within[cond]['trad']):3d}  p={w['p_value']:.4g}  "
                  f"cliffs_delta={w.get('cliffs_delta', 'n/a')}")

    print("\n  Sensitivity — excluding trivially-killed SDL (kept in the main analysis above):")
    for cond in CONDITIONS:
        print(f"    {cond:8s} trad {_pct(results[cond]['trad_kill_rate_excl_trivial_sdl'])}"
              f"   gap {_pts(results[cond]['gap_points_excl_trivial_sdl'])}")

    print("\nEquivalent mutants by operator:")
    for op in sorted(n_total_op):
        print(f"  {op:6s} {n_equiv_op[op]:4d}/{n_total_op[op]:4d} = "
              f"{_pct(_rate(n_equiv_op[op], n_total_op[op]))}")

    if len(by_health) > 1:
        print("\nEquivalence rate by input-health profile:")
        for h, v in sorted(by_health.items()):
            print(f"  {h:12s} {v['n_equiv']:4d}/{v['n_total']:4d} = "
                  f"{_pct(_rate(v['n_equiv'], v['n_total']))}")
        broken = {h: v for h, v in by_health.items() if h in ("broken", "noisy")}
        clean = by_health.get("clean")
        if broken and clean and clean["n_total"]:
            b_rate = _rate(sum(v["n_equiv"] for v in broken.values()),
                           sum(v["n_total"] for v in broken.values()))
            c_rate = _rate(clean["n_equiv"], clean["n_total"])
            if b_rate is not None and c_rate is not None and b_rate > c_rate * 1.5:
                print(f"  ** equivalence fires far more on broken/noisy tasks "
                      f"({_pct(b_rate)}) than clean ones ({_pct(c_rate)}):")
                print("     suspect residual input-generation weakness, not genuine equivalence.")

    summary = {
        "n_tasks": len(tasks), "task_ids": [t.task_id for t in tasks],
        "n_fuzz_inputs": n_fuzz,
        "corpus": {"total": n_mutants_total, "equivalent": n_equiv_total,
                    "retained_with": n_mutants_total - n_equiv_total,
                    "traditional_regenerated": n_trad,
                    "llm_reused_from_disk": n_llm, "llm_source_tasks": n_tasks_llm},
        "conditions": results,
        "gap_change_points_mean_paired": gap_change,
        "gap_change_wilcoxon": gap_test,
        "per_task_gaps": gap_rows,
        "equivalence_by_operator": {op: {"equivalent": n_equiv_op[op], "total": n_total_op[op]}
                                     for op in sorted(n_total_op)},
        "equivalence_by_input_health": {h: dict(v) for h, v in sorted(by_health.items())},
    }
    (OUT_DIR / "ablation_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {OUT_DIR / 'ablation_summary.json'}")
    print(f"Per-task artefacts under {OUT_DIR}/<task_label>/")


if __name__ == "__main__":
    main()
