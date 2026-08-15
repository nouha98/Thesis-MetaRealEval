#!/usr/bin/env python
"""Aggregate the full 164-task cluster run (Stage 0, RQ1, RQ2) into summary stats.

Reads directly from results/{stage0,rq1,rq2}/... and reuses the statistical
tests in meta_real_eval.analysis.statistics. Prints a report to stdout and
writes results/analysis_summary.json for downstream plotting/reporting.

Usage:
    .venv/bin/python scripts/analyze_results.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.analysis.statistics import wilcoxon_test, bootstrap_ci, cliffs_delta  # noqa: E402

RESULTS = REPO_ROOT / "results"
TRADITIONAL_OPS = {"AOR", "ROR", "SDL"}

# Statement deletions whose kill outcome is predetermined: removing a return or
# a definition makes the function yield None or raise NameError, so *any* test
# suite kills it. They inflate the traditional kill rate without saying anything
# about whether the benchmark detects subtly wrong logic — which is exactly what
# RQ1a's traditional-vs-LLM comparison is about. Reported both ways: headline
# numbers keep them (deleting a return is standard SDL), and a restricted
# population excludes them so the gap can be shown not to depend on them.
TRIVIALLY_KILLED_SDL_KINDS = {"Return", "Import", "ImportFrom", "FunctionDef"}


def load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Stage 0 — equivalence filtering
# ---------------------------------------------------------------------------

def analyze_stage0() -> dict:
    task_dirs = sorted((RESULTS / "stage0").iterdir())
    per_op_total = Counter()
    per_op_equiv = Counter()
    total_mutants = 0
    total_equiv = 0
    per_task_rows = []

    for td in task_dirs:
        if not td.is_dir():
            continue
        mutants = load(td / "mutants.json")
        equiv = load(td / "equiv_filter.json")
        equiv_ids = {r["mutant_id"]: r["is_equivalent"] for r in equiv}
        op_of = {m["mutant_id"]: m["operator"] for m in mutants}

        n_equiv_task = sum(1 for v in equiv_ids.values() if v)
        total_mutants += len(mutants)
        total_equiv += n_equiv_task
        per_task_rows.append({
            "task": td.name,
            "mutants": len(mutants),
            "non_equivalent": len(mutants) - n_equiv_task,
            "equivalent": n_equiv_task,
        })
        for mid, is_eq in equiv_ids.items():
            op = op_of.get(mid, "?")
            per_op_total[op] += 1
            if is_eq:
                per_op_equiv[op] += 1

    return {
        "n_tasks": len(per_task_rows),
        "total_mutants": total_mutants,
        "total_equivalent": total_equiv,
        "total_non_equivalent": total_mutants - total_equiv,
        "pct_equivalent": total_equiv / total_mutants if total_mutants else 0.0,
        "by_operator": {
            op: {
                "total": per_op_total[op],
                "equivalent": per_op_equiv[op],
                "pct_equivalent": per_op_equiv[op] / per_op_total[op] if per_op_total[op] else 0.0,
            }
            for op in sorted(per_op_total)
        },
        "per_task_rows": per_task_rows,
    }


# ---------------------------------------------------------------------------
# RQ1 — kill rates, traditional vs LLM-specific
# ---------------------------------------------------------------------------

def _sdl_stmt_kind(description: str) -> str | None:
    """Extract the deleted statement kind from an SDL mutant's description.

    Descriptions read "Delete Return statement 3 in f". Corpora generated
    before the kind was recorded read "Delete statement 3 in f" and yield
    None, so the stratified numbers are reported as unavailable rather than
    silently computed over a mislabelled population.
    """
    if not description.startswith("Delete "):
        return None
    kind, sep, _ = description[len("Delete "):].partition(" statement ")
    return kind if (sep and kind) else None


def _rate(killed: int, total: int) -> float:
    return killed / total if total else 0.0


def analyze_rq1() -> dict:
    task_dirs = sorted((RESULTS / "rq1" / "evaluate").iterdir())
    trad_total = trad_killed = 0
    llm_total = llm_killed = 0
    # Restricted population: traditional mutants minus predetermined-outcome
    # statement deletions (see TRIVIALLY_KILLED_SDL_KINDS).
    nontrivial_total = nontrivial_killed = 0
    per_op_totals = defaultdict(lambda: {"total": 0, "killed": 0})
    sdl_by_kind = defaultdict(lambda: {"total": 0, "killed": 0})
    paired_trad_rate = []
    paired_llm_rate = []
    paired_nontrivial_rate = []
    paired_llm_rate_for_nontrivial = []
    tasks_with_survivors = []
    n_tasks_both = 0
    n_trivial_excluded = 0
    n_trivial_survived = 0
    n_sdl_unlabelled = 0

    for td in task_dirs:
        if not td.is_dir():
            continue
        summary_path = td / "kill_rate_summary.json"
        if not summary_path.exists():
            continue
        summary = load(summary_path)

        t_total = t_killed = 0
        l_total = l_killed = 0
        for op, stats in summary.items():
            per_op_totals[op]["total"] += stats["total"]
            per_op_totals[op]["killed"] += stats["killed"]
            if op in TRADITIONAL_OPS:
                t_total += stats["total"]
                t_killed += stats["killed"]
            elif op == "LLM":
                l_total += stats["total"]
                l_killed += stats["killed"]

        trad_total += t_total
        trad_killed += t_killed
        llm_total += l_total
        llm_killed += l_killed

        if t_total > 0 and l_total > 0:
            n_tasks_both += 1
            paired_trad_rate.append(t_killed / t_total)
            paired_llm_rate.append(l_killed / l_total)

        # --- join kill outcomes back to the corpus to recover SDL statement kinds ---
        kill_matrix = load(td / "kill_matrix.json") if (td / "kill_matrix.json").exists() else []
        s0_mutants_path = RESULTS / "stage0" / td.name / "mutants.json"
        desc_of = {}
        if s0_mutants_path.exists():
            desc_of = {m["mutant_id"]: m.get("description", "") for m in load(s0_mutants_path)}

        nt_total = nt_killed = 0
        for row in kill_matrix:
            if row["operator"] not in TRADITIONAL_OPS:
                continue
            is_trivial = False
            if row["operator"] == "SDL":
                kind = _sdl_stmt_kind(desc_of.get(row["mutant_id"], ""))
                if kind is None:
                    n_sdl_unlabelled += 1
                else:
                    sdl_by_kind[kind]["total"] += 1
                    sdl_by_kind[kind]["killed"] += int(row["is_killed"])
                    is_trivial = kind in TRIVIALLY_KILLED_SDL_KINDS
            if is_trivial:
                n_trivial_excluded += 1
                if not row["is_killed"]:
                    # A predetermined-kill mutant that survived means the suite
                    # accepts a function that returns None / raises NameError.
                    n_trivial_survived += 1
                continue
            nt_total += 1
            nt_killed += int(row["is_killed"])

        nontrivial_total += nt_total
        nontrivial_killed += nt_killed
        if nt_total > 0 and l_total > 0:
            paired_nontrivial_rate.append(nt_killed / nt_total)
            paired_llm_rate_for_nontrivial.append(l_killed / l_total)

        survivors = l_total - l_killed
        if survivors > 0:
            survivor_ids = [r["mutant_id"] for r in kill_matrix
                             if r["operator"] == "LLM" and not r["is_killed"]]
            tasks_with_survivors.append({"task": td.name, "n_survived": survivors,
                                          "mutant_ids": survivor_ids})

    wilcoxon = wilcoxon_test(paired_trad_rate, paired_llm_rate) if paired_trad_rate else None
    wilcoxon_nt = (wilcoxon_test(paired_nontrivial_rate, paired_llm_rate_for_nontrivial)
                   if paired_nontrivial_rate else None)

    # Complementary pooled-proportion test (independent of the per-task pairing
    # above): are the two overall kill rates different if we just pool all
    # mutants regardless of which task they came from?
    from scipy.stats import chi2_contingency

    def _chi2(a_killed, a_total, b_killed, b_total):
        table = [[a_killed, a_total - a_killed], [b_killed, b_total - b_killed]]
        if min(a_total, b_total) == 0 or any(v < 0 for row in table for v in row):
            return None
        chi2, p, _, _ = chi2_contingency(table)
        return {"chi2": float(chi2), "p_value": float(p)}

    # Stratification is only meaningful if the corpus actually recorded kinds.
    stratified = bool(sdl_by_kind) and n_sdl_unlabelled == 0

    return {
        "pooled_chi2_kill_rate_trad_vs_llm": _chi2(trad_killed, trad_total, llm_killed, llm_total),
        "n_tasks_with_both_categories": n_tasks_both,
        "traditional": {
            "total": trad_total, "killed": trad_killed,
            "survived": trad_total - trad_killed,
            "kill_rate": _rate(trad_killed, trad_total),
        },
        "llm_specific": {
            "total": llm_total, "killed": llm_killed,
            "survived": llm_total - llm_killed,
            "kill_rate": _rate(llm_killed, llm_total),
        },
        "by_operator": {
            op: {**v, "kill_rate": _rate(v["killed"], v["total"])}
            for op, v in per_op_totals.items()
        },
        "wilcoxon_paired_kill_rate_trad_vs_llm": wilcoxon,
        "n_tasks_with_surviving_llm_mutants": len(tasks_with_survivors),
        "surviving_llm_mutant_tasks": sorted(
            tasks_with_survivors, key=lambda r: -r["n_survived"]
        )[:15],
        # --- restricted-population (stratified) view ---
        "stratification_available": stratified,
        "n_sdl_mutants_without_recorded_kind": n_sdl_unlabelled,
        "sdl_by_statement_kind": {
            k: {**v, "kill_rate": _rate(v["killed"], v["total"]),
                "trivially_killed_by_construction": k in TRIVIALLY_KILLED_SDL_KINDS}
            for k, v in sorted(sdl_by_kind.items(), key=lambda kv: -kv[1]["total"])
        },
        "traditional_excl_trivial_sdl": {
            "total": nontrivial_total, "killed": nontrivial_killed,
            "survived": nontrivial_total - nontrivial_killed,
            "kill_rate": _rate(nontrivial_killed, nontrivial_total),
            "n_excluded": n_trivial_excluded,
            "n_excluded_that_survived": n_trivial_survived,
        },
        "wilcoxon_paired_kill_rate_trad_excl_trivial_vs_llm": wilcoxon_nt,
        "pooled_chi2_kill_rate_trad_excl_trivial_vs_llm": _chi2(
            nontrivial_killed, nontrivial_total, llm_killed, llm_total),
        "gap_points_all": (_rate(trad_killed, trad_total) - _rate(llm_killed, llm_total)) * 100,
        "gap_points_excl_trivial_sdl": (
            _rate(nontrivial_killed, nontrivial_total) - _rate(llm_killed, llm_total)) * 100,
    }


# ---------------------------------------------------------------------------
# RQ2 — ranking stability
# ---------------------------------------------------------------------------

def _sign(a: float, b: float) -> int:
    """+1 if a>b, -1 if a<b, 0 if tied."""
    return (a > b) - (a < b)


def analyze_rq2() -> dict:
    """Aggregate RQ2 across tasks.

    Four metrics, matching rq2/ranking.py plus the pairwise reversal rate
    computed here (it needs the whole corpus to be meaningful, unlike the
    other three which are already summarised per task):

    - Ranking stability (tau_b): belongs to a (task, relation) pair, so the
      independent sample is the task. Every mean/CI below — the grand mean,
      and each per-relation mean — bootstraps task-level values, never the
      handful of relations *within* one task (too small a sample to mean
      anything, and would ignore that a task's own relations aren't
      independent of each other).
    - Per-model sensitivity (delta pass@1) and per-model rank movement
      (rank_change): genuinely per-model, one task-level sample per model.
    - Pairwise reversal rate: for each model pair and relation, how often
      their *relative* order (not the whole ranking) flips vs. baseline.
      Ties within a pair (score_i == score_j) are excluded rather than
      counted either way — 22% of pair-comparisons are tied at this model
      count, so this is not a rare edge case. The "pooled across relations"
      row is task-clustered the same way as tau_b's grand mean: each task
      first contributes one mean-across-its-own-relations value, and *that*
      list is what gets bootstrapped — never the raw (task, relation) pairs
      flattened together, which would repeat the exact bug this whole file
      exists to avoid.
    """
    task_dirs = sorted((RESULTS / "rq2" / "evaluate").iterdir())
    per_task = []                       # one task-level mean tau_b each
    per_relation_tau = defaultdict(list)
    per_model_abs_delta = defaultdict(list)
    per_model_signed_delta = defaultdict(lambda: defaultdict(list))
    per_model_abs_rank_change = defaultdict(list)
    per_model_signed_rank_change = defaultdict(lambda: defaultdict(list))
    # pair_key -> relation -> [one 0/1 per task with a valid (non-tied) comparison]
    pairwise_by_relation = defaultdict(lambda: defaultdict(list))
    # pair_key -> [one mean-across-that-task's-valid-relations value, per task]
    pairwise_pooled = defaultdict(list)
    model_correct = Counter()
    model_n = Counter()
    n_tasks = 0
    n_degenerate_pairs = 0
    n_pairs = 0

    for td in task_dirs:
        if not td.is_dir():
            continue
        rankings_path = td / "rankings.json"
        pass_rates_path = td / "pass_rates.json"
        if not rankings_path.exists():
            continue
        n_tasks += 1
        r = load(rankings_path)

        if r.get("mean_tau_b") is not None:
            per_task.append({"task": td.name, "mean_tau_b": r["mean_tau_b"]})
        for relation, tau in r.get("tau_b_per_relation", {}).items():
            n_pairs += 1
            if tau is None:
                n_degenerate_pairs += 1
            else:
                per_relation_tau[relation].append(tau)

        for model, v in r.get("mean_abs_delta_pass_at_1", {}).items():
            per_model_abs_delta[model].append(v)
        for model, deltas in r.get("delta_pass_at_1", {}).items():
            for relation, d in deltas.items():
                per_model_signed_delta[model][relation].append(d)

        for model, v in r.get("mean_abs_rank_change", {}).items():
            per_model_abs_rank_change[model].append(v)
        for model, changes in r.get("rank_change", {}).items():
            for relation, c in changes.items():
                per_model_signed_rank_change[model][relation].append(c)

        if not pass_rates_path.exists():
            continue
        pr = load(pass_rates_path)
        for relation, models in pr.items():
            for model, stats in models.items():
                model_correct[model] += stats["correct"]
                model_n[model] += stats["n"]

        model_ids = r.get("model_ids") or list(pr.get("original", {}).keys())
        baseline = {m: pr["original"][m]["pass@1"] for m in model_ids if m in pr.get("original", {})}
        this_task_pair_values = defaultdict(list)  # pair_key -> [0/1 across this task's relations]
        for relation in pr:
            if relation == "original":
                continue
            variant = {m: pr[relation][m]["pass@1"] for m in model_ids if m in pr[relation]}
            for i, j in combinations(model_ids, 2):
                if i not in baseline or j not in baseline or i not in variant or j not in variant:
                    continue
                base_sign = _sign(baseline[i], baseline[j])
                var_sign = _sign(variant[i], variant[j])
                if base_sign == 0 or var_sign == 0:
                    continue  # tied in either condition: no order to reverse
                pair_key = f"{i} vs {j}"
                reversed_ = int(base_sign != var_sign)
                pairwise_by_relation[pair_key][relation].append(reversed_)
                this_task_pair_values[pair_key].append(reversed_)

        for pair_key, vals in this_task_pair_values.items():
            pairwise_pooled[pair_key].append(sum(vals) / len(vals))

    task_tau = [r["mean_tau_b"] for r in per_task]
    grand_mean = sum(task_tau) / len(task_tau) if task_tau else float("nan")
    ci_lo, ci_hi = bootstrap_ci(task_tau) if task_tau else (float("nan"), float("nan"))

    def interpret(tau):
        if tau >= 0.85:
            return "stable"
        if tau >= 0.5:
            return "moderate instability"
        if tau >= 0:
            return "weak / near-random"
        return "unstable (worse than random)"

    def _mean_ci(values: list[float]) -> dict:
        if not values:
            return {"mean": float("nan"), "ci_lower": float("nan"), "ci_upper": float("nan"), "n": 0}
        lo, hi = bootstrap_ci(values)
        return {"mean": sum(values) / len(values), "ci_lower": lo, "ci_upper": hi, "n": len(values)}

    return {
        "n_tasks": n_tasks,
        "ranking_stability": {
            "n_task_level_samples": len(task_tau),
            "grand_mean_tau_b": grand_mean,
            "ci_lower": ci_lo,
            "ci_upper": ci_hi,
            "interpretation": interpret(grand_mean),
            "by_relation": {
                rel: _mean_ci(vals) for rel, vals in per_relation_tau.items()
            },
            "n_degenerate_pairs": n_degenerate_pairs,
            "n_task_relation_pairs": n_pairs,
            "note": (
                "tau_b compares the ordering of all models, so one value per "
                "(task, relation); degenerate pairs (all models tied, tau_b "
                "undefined) are excluded rather than scored 1.0 or 0.0. Every "
                "mean/CI here — grand and per-relation — bootstraps task-level "
                "values."
            ),
        },
        "model_sensitivity": {
            model: {
                "delta_pass@1": _mean_ci(per_model_abs_delta[model]),
                "rank_change": _mean_ci(per_model_abs_rank_change[model]),
                "overall_pass@1": (
                    model_correct[model] / model_n[model] if model_n[model] else float("nan")
                ),
                "mean_delta_pass@1_by_relation": {
                    rel: sum(d) / len(d)
                    for rel, d in per_model_signed_delta[model].items()
                },
                "mean_rank_change_by_relation": {
                    rel: sum(c) / len(c)
                    for rel, c in per_model_signed_rank_change[model].items()
                },
            }
            for model in per_model_abs_delta
        },
        "pairwise_reversal_rate": {
            "note": (
                "Fraction of tasks where a model pair's relative order flips "
                "between 'original' and the variant. Ties within a pair "
                "(score_i == score_j) are excluded from that comparison "
                "rather than counted as reversed or not. 'pooled' rows "
                "bootstrap one mean-per-task value (task-clustered, same "
                "discipline as tau_b), not the raw per-relation observations."
            ),
            "pooled_by_pair": {
                pair: _mean_ci(vals) for pair, vals in pairwise_pooled.items()
            },
            "by_pair_and_relation": {
                pair: {rel: _mean_ci(vals) for rel, vals in by_rel.items()}
                for pair, by_rel in pairwise_by_relation.items()
            },
        },
        "most_unstable_tasks": sorted(per_task, key=lambda r: r["mean_tau_b"])[:15],
        "most_stable_tasks": sorted(per_task, key=lambda r: -r["mean_tau_b"])[:10],
    }


# ---------------------------------------------------------------------------

def main() -> None:
    stage0 = analyze_stage0()
    rq1 = analyze_rq1()
    rq2 = analyze_rq2()

    out = {"stage0": stage0, "rq1": rq1, "rq2": rq2}
    out_path = RESULTS / "analysis_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print("=" * 70)
    print("STAGE 0 — Equivalence filtering  (%d tasks)" % stage0["n_tasks"])
    print("=" * 70)
    print(f"Total mutants generated : {stage0['total_mutants']}")
    print(f"Non-equivalent (kept)   : {stage0['total_non_equivalent']}")
    print(f"Equivalent (filtered)   : {stage0['total_equivalent']} "
          f"({stage0['pct_equivalent']*100:.1f}%)")
    print("By operator:")
    for op, v in stage0["by_operator"].items():
        print(f"  {op:5s} total={v['total']:5d}  equivalent={v['equivalent']:5d} "
              f"({v['pct_equivalent']*100:5.1f}%)")

    print()
    print("=" * 70)
    print("RQ1 — Fault characterisation (kill rates)")
    print("=" * 70)
    t = rq1["traditional"]
    l = rq1["llm_specific"]
    print(f"Traditional mutants : total={t['total']:5d} killed={t['killed']:5d} "
          f"survived={t['survived']:5d}  kill_rate={t['kill_rate']*100:.1f}%")
    print(f"LLM-specific mutants: total={l['total']:5d} killed={l['killed']:5d} "
          f"survived={l['survived']:5d}  kill_rate={l['kill_rate']*100:.1f}%")
    print("By operator:")
    for op, v in rq1["by_operator"].items():
        print(f"  {op:5s} total={v['total']:5d} killed={v['killed']:5d} kill_rate={v['kill_rate']*100:5.1f}%")
    w = rq1["wilcoxon_paired_kill_rate_trad_vs_llm"]
    if w:
        print(f"\nPaired Wilcoxon (n={rq1['n_tasks_with_both_categories']} tasks, "
              f"per-task kill-rate trad vs LLM):")
        print(f"  statistic={w['statistic']:.3f}  p={w['p_value']:.4g}  "
              f"cliffs_delta={w.get('cliffs_delta', 'n/a')}")
    c = rq1["pooled_chi2_kill_rate_trad_vs_llm"]
    if c:
        print(f"Pooled chi-square (ignores task pairing): chi2={c['chi2']:.3f}  p={c['p_value']:.4g}")
    print(f"\nTasks with >=1 surviving LLM mutant: {rq1['n_tasks_with_surviving_llm_mutants']} / "
          f"{rq1['n_tasks_with_both_categories']}")

    # --- robustness: does the gap survive dropping predetermined-kill SDL? ---
    print()
    print("-" * 70)
    print("RQ1 robustness — excluding trivially-killed statement deletions")
    print("-" * 70)
    if not rq1["stratification_available"]:
        n_missing = rq1["n_sdl_mutants_without_recorded_kind"]
        print(f"  UNAVAILABLE: {n_missing} SDL mutant(s) carry no recorded statement")
        print("  kind. Re-run stage0 with --force to rebuild the corpus, then re-analyse.")
    else:
        print("  SDL kill rate by deleted statement kind:")
        for kind, v in rq1["sdl_by_statement_kind"].items():
            flag = "  <- predetermined kill" if v["trivially_killed_by_construction"] else ""
            print(f"    {kind:14s} total={v['total']:4d} killed={v['killed']:4d} "
                  f"kill_rate={v['kill_rate']*100:5.1f}%{flag}")
        nt = rq1["traditional_excl_trivial_sdl"]
        print(f"\n  Excluded {nt['n_excluded']} predetermined-kill deletion(s); "
              f"{nt['n_excluded_that_survived']} of them SURVIVED")
        if nt["n_excluded_that_survived"]:
            print("    (a mutant returning None / raising NameError passed the suite —"
                  " worth reporting on its own)")
        print(f"  Traditional (restricted): total={nt['total']:5d} killed={nt['killed']:5d} "
              f"kill_rate={nt['kill_rate']*100:.1f}%")
        print(f"  trad - LLM gap: {rq1['gap_points_all']:+.1f} pts (all)  ->  "
              f"{rq1['gap_points_excl_trivial_sdl']:+.1f} pts (excl. trivial)")
        wn = rq1["wilcoxon_paired_kill_rate_trad_excl_trivial_vs_llm"]
        if wn:
            print(f"  Paired Wilcoxon (restricted): statistic={wn['statistic']:.3f}  "
                  f"p={wn['p_value']:.4g}  cliffs_delta={wn.get('cliffs_delta', 'n/a')}")
        cn = rq1["pooled_chi2_kill_rate_trad_excl_trivial_vs_llm"]
        if cn:
            print(f"  Pooled chi-square (restricted): chi2={cn['chi2']:.3f}  p={cn['p_value']:.4g}")

    print()
    print("=" * 70)
    print("RQ2 — Ranking stability")
    print("=" * 70)
    rs = rq2["ranking_stability"]
    print(f"Tasks analysed   : {rq2['n_tasks']}  (task-level tau_b samples: {rs['n_task_level_samples']})")
    print(f"Grand mean tau_b : {rs['grand_mean_tau_b']:.3f}  "
          f"95% CI [{rs['ci_lower']:.3f}, {rs['ci_upper']:.3f}]   (bootstrap over tasks)")
    print(f"Interpretation   : {rs['interpretation']}")
    print(f"Degenerate (task, relation) pairs excluded: "
          f"{rs['n_degenerate_pairs']}/{rs['n_task_relation_pairs']}")
    print("By paraphrase relation (mean tau_b vs original, 95% CI bootstrapped over tasks):")
    for relation, s in rs["by_relation"].items():
        print(f"  {relation:10s} mean={s['mean']:.3f}  CI=[{s['ci_lower']:.3f}, {s['ci_upper']:.3f}]  n={s['n']}")

    print()
    print("Per-model sensitivity (vs original prompt; both are mean-of-|change| per task, 95% CI over tasks):")
    for m, v in sorted(rq2["model_sensitivity"].items(),
                       key=lambda kv: -kv[1]["delta_pass@1"]["mean"]):
        dp, rc = v["delta_pass@1"], v["rank_change"]
        print(f"  {m:30s} overall_pass@1={v['overall_pass@1']*100:5.1f}%")
        print(f"      mean|delta pass@1| = {dp['mean']:.4f}  CI=[{dp['ci_lower']:.4f}, {dp['ci_upper']:.4f}]")
        print(f"      mean|rank change|  = {rc['mean']:.4f}  CI=[{rc['ci_lower']:.4f}, {rc['ci_upper']:.4f}]  "
              f"(0=never moves, 1=avg. one position)")
        for rel, d in v["mean_delta_pass@1_by_relation"].items():
            c = v["mean_rank_change_by_relation"].get(rel, float("nan"))
            print(f"      {rel:10s} delta pass@1 = {d:+.4f}   rank change = {c:+.4f}")

    print()
    print("Pairwise reversal rate (how often a model pair's relative order flips vs. original,")
    print("ties within the pair excluded; pooled = task-clustered bootstrap over all relations):")
    for pair, s in sorted(rq2["pairwise_reversal_rate"]["pooled_by_pair"].items(),
                          key=lambda kv: -kv[1]["mean"]):
        print(f"  {pair:55s} {s['mean']*100:5.1f}%  CI=[{s['ci_lower']*100:.1f}%, {s['ci_upper']*100:.1f}%]  n={s['n']}")
        by_rel = rq2["pairwise_reversal_rate"]["by_pair_and_relation"].get(pair, {})
        for rel, rs2 in by_rel.items():
            print(f"      {rel:10s} {rs2['mean']*100:5.1f}%  n={rs2['n']}")

    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
