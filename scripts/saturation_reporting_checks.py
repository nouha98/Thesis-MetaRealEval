"""Reporting checks on the finished saturation simulation (extensions plan rev. 8, Stage 1a).

    python scripts/saturation_reporting_checks.py

Read-only on the simulation: it reads ``results_saturation/<run>/task_table.csv``,
``results_saturation/<run>/simulation.json`` and ``results_saturation/cross_tier.json`` and writes
only ``results_saturation/reporting_checks.json`` and ``doc/saturation/reporting_checks.md``.
Nothing is re-simulated with new draws and no stored output is modified.

Three checks:

1. Paired versus marginal populations. The simulation reports the mean tau_b of each arm over the
   tasks where THAT arm is defined (marginal, ``mean_tau_c`` / ``mean_tau_p``) next to the gap over
   the tasks where BOTH arms are defined (``gap_paired``). The columns then do not subtract to the
   gap. This script recomputes both views from the stored per-task table, verifies the
   reconstruction against every stored point value, and gives the paired means that do subtract to
   the gap.
2. Leaderboard margins. The tables' "margin" column is the bootstrap MEAN of the per-replicate
   smallest adjacent margin, not the point margin; the minimum of noisy differences is biased
   upward when two models are close. This script reports the point margin, the pair it belongs to,
   the bootstrap interval, the number of tasks the leaderboard actually uses (``lb_ok``), and
   verifies the identity that makes margin compression mechanical: a task whose original-prompt
   scores are equal across models adds zero to every pairwise difference, so
   (pair difference x n) is the same on the full benchmark and on the discriminating tasks.
3. Cross-tier paired means. The information- and saturation-matched resamples of
   ``cross_tier.json`` are replayed with the simulation's own seed and weight generators
   (verified equal to the stored summaries) to add the paired means.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saturation_common as sc  # noqa: E402
import saturation_simulation as ss  # noqa: E402

RUNS = ("tier1_pass1", "tier2_graded", "tier2_pass1")
# subsets whose rows the report quotes (tables in doc/saturation/report.md)
REPORTED = ("S0_full", "S1b_baseline_discriminating", "S4_spread_T1", "S4_spread_T2", "S4_spread_T3",
            "S4_difficulty_T1", "S4_difficulty_T2", "S4_difficulty_T3")
# subsets that contain every baseline-discriminating task (margin identity applies)
SUPERSETS = ("S0_full", "S1a_non_extreme", "S2_drop_ceiling", "S2_drop_floor")
TOL = 1e-12
FLOAT_COLS = ("difficulty", "spread", "tau_c", "tau_p", "tau_t", "rev_c", "rev_p", "n_cmp", "n_tied")
BOOL_COLS = ("has_base", "floor", "ceiling", "non_extreme", "base_disc", "covered", "lb_ok")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_arrays(csv_path: Path) -> tuple[list[str], dict]:
    """The per-task table as the arrays ``saturation_simulation.point`` reads. ``rel_total`` /
    ``rel_undef`` are not in the table, so ``undef_share`` is not checked."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    labels = [r["label"] for r in rows]
    A = {k: np.array([float(r[k]) for r in rows], dtype=float) for k in FLOAT_COLS}
    for k in BOOL_COLS:
        A[k] = np.array([r[k] == "True" for r in rows])
    A["rel_total"] = np.zeros(len(rows))
    A["rel_undef"] = np.zeros(len(rows))
    return labels, A


def load_sim(run: str) -> dict:
    return json.loads((sc.OUT / run / "simulation.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Paired versus marginal
# ---------------------------------------------------------------------------

def paired_vs_marginal(A: dict, mask: np.ndarray) -> dict:
    """Marginal means (each arm over its own defined tasks) and paired means (both arms defined)."""
    dc = mask & ~np.isnan(A["tau_c"])
    dp = mask & ~np.isnan(A["tau_p"])
    both = dc & dp

    def mean(v, m):
        return float(v[m].mean()) if m.any() else None
    pc, pp = mean(A["tau_c"], both), mean(A["tau_p"], both)
    mc, mp = mean(A["tau_c"], dc), mean(A["tau_p"], dp)
    gap = mean(A["tau_c"] - A["tau_p"], both)
    return {
        "n_tau_c": int(dc.sum()), "marginal_tau_c": mc,
        "n_tau_p": int(dp.sum()), "marginal_tau_p": mp,
        "marginal_difference": None if mc is None or mp is None else mc - mp,
        "n_both": int(both.sum()), "paired_tau_c": pc, "paired_tau_p": pp, "gap_paired": gap,
        "paired_means_subtract_to_gap": (gap is None) or abs((pc - pp) - gap) <= TOL,
    }


def verify_reconstruction(A: dict, sim: dict) -> dict:
    """Rebuild every subset from the task table and compare ss.point with the stored point values."""
    subsets = ss.define_subsets(A)
    worst, mismatches = 0.0, []
    for name, blk in sim["subsets"].items():
        mine = ss.point(A, subsets[name])
        for k, stored in blk["point"].items():
            if k == "undef_share":
                continue
            got = mine[k]
            if (stored is None) != (got is None):
                mismatches.append(f"{name}/{k}: stored {stored} vs {got}")
            elif stored is not None:
                d = abs(stored - got)
                worst = max(worst, d)
                if d > TOL:
                    mismatches.append(f"{name}/{k}: {stored} vs {got}")
    return {"max_abs_diff": worst, "mismatches": mismatches, "ok": not mismatches}


# ---------------------------------------------------------------------------
# 2. Leaderboard margins
# ---------------------------------------------------------------------------

def margin_record(models: list[str], lb_point: dict, lb_boot: dict) -> dict:
    """Point margin between adjacent models in the original-prompt leaderboard, with its pair."""
    scores = dict(zip(models, lb_point["scores_original"]))
    order = sorted(models, key=lambda m: -scores[m])
    adjacent = [{"pair": [a, b], "difference": scores[a] - scores[b]} for a, b in zip(order, order[1:])]
    smallest = min(adjacent, key=lambda r: r["difference"]) if adjacent else None
    return {
        "n_tasks_leaderboard": lb_point["n_tasks"], "order": order, "scores_original": scores,
        "adjacent": adjacent,
        "point_margin": smallest["difference"] if smallest else None,
        "point_margin_pair": smallest["pair"] if smallest else None,
        "stored_point_margin": lb_point["margin_original"],
        "bootstrap_mean_of_min_margin": lb_boot["margin_o"]["mean"],
        "bootstrap_2.5": lb_boot["margin_o"]["lo"], "bootstrap_97.5": lb_boot["margin_o"]["hi"],
    }


def margin_identity(models: list[str], sim: dict, superset: str, disc: str = "S1b_baseline_discriminating") -> dict:
    """(pair difference x n_leaderboard) must be equal on a superset of the discriminating tasks and
    on the discriminating tasks alone: tasks with equal original scores add zero to every pair."""
    a, b = sim["subsets"][superset]["leaderboard_point"], sim["subsets"][disc]["leaderboard_point"]
    worst = 0.0
    for i, j in combinations(range(len(models)), 2):
        sa = (a["scores_original"][i] - a["scores_original"][j]) * a["n_tasks"]
        sb = (b["scores_original"][i] - b["scores_original"][j]) * b["n_tasks"]
        worst = max(worst, abs(sa - sb))
    # aggregate scores are stored rounded to 12 decimals; times n (<= 375) the rounding is < 1e-9
    return {"superset": superset, "n_superset": a["n_tasks"], "n_discriminating": b["n_tasks"],
            "max_abs_diff_of_n_weighted_pair_differences": worst, "ok": worst <= 1e-8,
            "compression_factor": b["n_tasks"] / a["n_tasks"] if a["n_tasks"] else None}


def leaderboard_population(run: str, A: dict, labels: list[str]) -> dict:
    """Why the leaderboard has fewer tasks than the subset (e.g. Tier 1: 157 vs 164, 27 vs 34).

    The leaderboard compares original, control and paraphrase aggregate scores on the SAME tasks,
    so a task needs complete original and control cells and a usable paraphrase score under the
    RQ2 family-coverage rule (``lb_ok``). Original-prompt margins on every task with a complete
    original cell are given next to it, read from the stored per-task scores (views)."""
    dropped = [{"task": lab, "base_discriminating": bool(A["base_disc"][i]),
                "paraphrase_coverage_ok": bool(A["covered"][i]),
                "reason": ("paraphrase family coverage rule not met" if not A["covered"][i]
                           else "no complete paraphrase or control cell")}
               for i, lab in enumerate(labels) if A["has_base"][i] and not A["lb_ok"][i]]
    tier, key, ranking = ss.RUNS[run]
    loaded = ss.load_run(sc.VIEWS / tier, ranking, key)
    rows = [ss.build_row(t.scores, t.universe, loaded.models, loaded.min_cov) for t in loaded.tasks]
    margins = {}
    for name, sel in (("all_tasks", lambda r: r["has_base"]), ("discriminating", lambda r: r["base_disc"]),
                      ("leaderboard_tasks", lambda r: r["lb_ok"]),
                      ("leaderboard_discriminating", lambda r: r["base_disc"] and r["lb_ok"])):
        S = np.array([r["S_o"] for r in rows if sel(r)])
        if not len(S):
            continue
        means = dict(zip(loaded.models, S.mean(0).tolist()))
        order = sorted(loaded.models, key=lambda m: -means[m])
        adj = [(a, b, means[a] - means[b]) for a, b in zip(order, order[1:])]
        a, b, d = min(adj, key=lambda x: x[2])
        margins[name] = {"n_tasks": int(len(S)), "scores_original": means,
                         "point_margin": d, "pair": [a, b]}
    return {"dropped_from_leaderboard": dropped, "original_prompt_margins": margins}


# ---------------------------------------------------------------------------
# 3. Cross-tier paired means (replay of the stored resamples)
# ---------------------------------------------------------------------------

def _paired_means(A: dict, W: np.ndarray) -> dict:
    both = ~np.isnan(A["tau_c"]) & ~np.isnan(A["tau_p"])
    n = W @ both
    pc = ss._div(W @ np.where(both, np.nan_to_num(A["tau_c"]), 0.0), n)
    pp = ss._div(W @ np.where(both, np.nan_to_num(A["tau_p"]), 0.0), n)
    return {"paired_tau_c": ss.summ(pc), "paired_tau_p": ss.summ(pp)}


def replay_cross_tier(A1: dict, A2: dict, stored: dict, R: int) -> dict:
    """Same rng, same calls, same order as ``saturation_simulation.cross_tier``."""
    rng = np.random.default_rng([ss.SEED, 99])
    one2 = np.ones(len(A2["tau_c"]), bool)
    p1, p2 = ss.point(A1, np.ones(len(A1["tau_c"]), bool)), ss.point(A2, one2)
    m_size = int(round(p1["n_both"] / p2["yield_both"]))
    W_info = ss.sample_weights(one2, m_size, R, rng)
    ss.sample_weights(one2, m_size, R, rng)               # the leaderboard draw (not needed here)
    s1, s2 = float(A1["base_disc"].mean()), float(A2["base_disc"].mean())
    W2 = ss.dial_weights(A2["base_disc"], ~A2["base_disc"], s1, R, rng)
    W1 = ss.dial_weights(A1["base_disc"], ~A1["base_disc"], s2, R, rng)
    draws = {"tier2_pass1_information_matched": (A2, W_info, stored["tier2_pass1_information_matched"]),
             "tier2_pass1_at_tier1_share": (A2, W2, stored["saturation_matched"]["tier2_pass1_at_tier1_share"]),
             "tier1_at_tier2_pass1_share": (A1, W1, stored["saturation_matched"]["tier1_at_tier2_pass1_share"])}
    out = {}
    for name, (A, W, ref) in draws.items():
        m = ss.metrics(A, W)
        worst = 0.0
        for k in ("n_both", "mean_tau_c", "mean_tau_p", "gap_paired", "rev_diff"):
            got = ss.summ(m[k])
            for q in ("mean", "lo", "hi"):
                worst = max(worst, abs(got[q] - ref[k][q]))
        out[name] = {"replay_matches_stored": worst <= TOL, "replay_max_abs_diff": worst,
                     "marginal_tau_c": ref["mean_tau_c"], "marginal_tau_p": ref["mean_tau_p"],
                     "gap_paired": ref["gap_paired"], "n_both": ref["n_both"], **_paired_means(A, W)}
    for name, A in (("tier1_observed", A1), ("tier2_pass1_observed", A2)):
        out[name] = paired_vs_marginal(A, np.ones(len(A["tau_c"]), bool))
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def f(v, d=3) -> str:
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{d}f}"


def write_markdown(res: dict, path: Path) -> None:
    L = ["# Saturation report: reporting checks", "",
         "*Generated by `scripts/saturation_reporting_checks.py` (read-only on the simulation). "
         "The simulation outputs are unchanged; this file documents what the report's tables show and the "
         "corrected quantities.*", ""]
    L += ["## 1. Paired versus marginal populations", "",
          "`tau_b control` / `tau_b paraphrase` in the simulation tables are **marginal** means (each arm over the "
          "tasks where that arm is defined); `gap (paired)` is over the tasks where **both** are defined. "
          "The paired means below subtract exactly to the gap.", ""]
    for run in RUNS:
        r = res["runs"][run]
        rec = r["reconstruction"]
        L += [f"### {run}", "",
              f"Reconstruction from `task_table.csv` matches every stored point value: **{rec['ok']}** "
              f"(max diff {rec['max_abs_diff']:.1e}).", "",
              "| Subset | n ctrl | marginal ctrl | n para | marginal para | marginal diff | n both | paired ctrl | paired para | gap (paired) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for name in REPORTED:
            p = r["paired_vs_marginal"].get(name)
            if p is None:
                continue
            L.append(f"| {name} | {p['n_tau_c']} | {f(p['marginal_tau_c'])} | {p['n_tau_p']} | {f(p['marginal_tau_p'])} | "
                     f"{f(p['marginal_difference'])} | {p['n_both']} | {f(p['paired_tau_c'])} | {f(p['paired_tau_p'])} | "
                     f"{f(p['gap_paired'])} |")
        L.append("")
    L += ["## 2. Leaderboard margins", "",
          "The tables' `margin` column is the bootstrap **mean of the per-replicate smallest margin**. "
          "When two models are close this is biased upward (the smallest of noisy differences is folded at 0), "
          "so it is not the observed margin. Point margins below use the tasks the leaderboard actually uses "
          "(complete original, control and paraphrase cells: `lb_ok`).", "",
          "| Run | Subset | leaderboard tasks | point margin | between | bootstrap mean of min | 95% range |",
          "|---|---|---|---|---|---|---|"]
    for run in RUNS:
        for name, m in res["runs"][run]["margins"].items():
            L.append(f"| {run} | {name} | {m['n_tasks_leaderboard']} | {f(m['point_margin'], 4)} | "
                     f"{' vs '.join(m['point_margin_pair'] or [])} | {f(m['bootstrap_mean_of_min_margin'], 4)} | "
                     f"[{f(m['bootstrap_2.5'], 4)}, {f(m['bootstrap_97.5'], 4)}] |")
    L += ["", "**Identity (mechanical compression).** For every model pair, (difference x leaderboard tasks) is equal on "
          "each superset of the discriminating tasks and on the discriminating tasks alone:", ""]
    for run in RUNS:
        for chk in res["runs"][run]["margin_identity"]:
            L.append(f"- {run}, {chk['superset']} ({chk['n_superset']}) vs discriminating ({chk['n_discriminating']}): "
                     f"ok = {chk['ok']} (max diff {chk['max_abs_diff_of_n_weighted_pair_differences']:.1e}); "
                     f"full-benchmark margins are the discriminating margins x {f(chk['compression_factor'], 4)}")
    L += ["", "### Why the leaderboard has fewer tasks than the subsets", "",
          "The leaderboard compares the original, control and paraphrase aggregate scores on the **same** tasks, "
          "so a task enters it only with complete original and control cells and a usable paraphrase score under "
          "the RQ2 family-coverage rule. Tasks dropped for that reason:", ""]
    for run in RUNS:
        lp = res["runs"][run]["leaderboard_population"]
        d = lp["dropped_from_leaderboard"]
        n_disc = sum(x["base_discriminating"] for x in d)
        L.append(f"- {run}: {len(d)} dropped ({n_disc} of them discriminating): "
                 + ", ".join(f"{x['task']} ({x['reason']})" for x in d))
    L += ["", "Original-prompt margins (no paraphrase needed) on every task with a complete original cell:", "",
          "| Run | Population | tasks | point margin | between |", "|---|---|---|---|---|"]
    for run in RUNS:
        for name, m in res["runs"][run]["leaderboard_population"]["original_prompt_margins"].items():
            L.append(f"| {run} | {name} | {m['n_tasks']} | {f(m['point_margin'], 4)} | {' vs '.join(m['pair'])} |")
    L += ["", "## 3. Cross-tier comparison with paired means", "",
          "Replayed with the simulation's seed and weight generators; every replay matches the stored summaries.", "",
          "| Comparison | n both | marginal ctrl | marginal para | paired ctrl | paired para | gap (paired) | replay ok |",
          "|---|---|---|---|---|---|---|---|"]
    ct = res["cross_tier"]
    for name in ("tier1_observed", "tier2_pass1_observed"):
        p = ct[name]
        L.append(f"| {name} | {p['n_both']} | {f(p['marginal_tau_c'])} | {f(p['marginal_tau_p'])} | "
                 f"{f(p['paired_tau_c'])} | {f(p['paired_tau_p'])} | {f(p['gap_paired'])} | n/a |")
    for name in ("tier2_pass1_information_matched", "tier2_pass1_at_tier1_share", "tier1_at_tier2_pass1_share"):
        p = ct[name]
        L.append(f"| {name} | {f(p['n_both']['mean'], 1)} | {f(p['marginal_tau_c']['mean'])} | {f(p['marginal_tau_p']['mean'])} | "
                 f"{f(p['paired_tau_c']['mean'])} | {f(p['paired_tau_p']['mean'])} | {f(p['gap_paired']['mean'])} "
                 f"[{f(p['gap_paired']['lo'])}, {f(p['gap_paired']['hi'])}] | {p['replay_matches_stored']} |")
    L += ["", "## 4. Independent halves (as quoted in the report)", ""]
    for run in RUNS:
        cf = res["runs"][run]["crossfit_S0"]
        L.append(f"- {run}: gap (paired) {f(cf['gap_paired'])}, reversal difference {f(cf['rev_diff'])} "
                 f"(average of both directions; all-completion values {f(cf['all_completions_gap'])} / "
                 f"{f(cf['all_completions_rev_diff'])})")
    L += ["", f"**All checks pass: {res['all_ok']}**", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    res: dict = {"runs": {}}
    arrays = {}
    oks = []
    for run in RUNS:
        sim = load_sim(run)
        labels, A = load_arrays(sc.OUT / run / "task_table.csv")
        arrays[run] = A
        subsets = ss.define_subsets(A)
        rec = verify_reconstruction(A, sim)
        pvm = {name: paired_vs_marginal(A, subsets[name]) for name in sim["subsets"]}
        models = sim["meta"]["models"]
        margins = {name: margin_record(models, sim["subsets"][name]["leaderboard_point"],
                                       sim["subsets"][name]["leaderboard_bootstrap"])
                   for name in ("S0_full", "S1b_baseline_discriminating") if name in sim["subsets"]}
        ident = [margin_identity(models, sim, s) for s in SUPERSETS if s in sim["subsets"]]
        cf = sim["crossfit"]["S0_full"]["average_of_both_directions"]
        p0 = sim["subsets"]["S0_full"]["point"]
        res["runs"][run] = {
            "reconstruction": rec, "paired_vs_marginal": pvm, "margins": margins, "margin_identity": ident,
            "leaderboard_population": leaderboard_population(run, A, labels),
            "crossfit_S0": {"gap_paired": cf["gap_paired"], "rev_diff": cf["rev_diff"],
                            "all_completions_gap": p0["gap_paired"], "all_completions_rev_diff": p0["rev_diff"]}}
        oks += [rec["ok"], *(c["ok"] for c in ident), *(p["paired_means_subtract_to_gap"] for p in pvm.values()),
                *(m["point_margin"] is not None and abs(m["point_margin"] - m["stored_point_margin"]) <= 1e-9
                  for m in margins.values())]
        print(f"[{run}] reconstruction ok={rec['ok']}  margin identity ok={all(c['ok'] for c in ident)}")
    stored_ct = json.loads((sc.OUT / "cross_tier.json").read_text(encoding="utf-8"))
    R = load_sim("tier1_pass1")["meta"]["replicates"]
    res["cross_tier"] = replay_cross_tier(arrays["tier1_pass1"], arrays["tier2_pass1"], stored_ct, R)
    oks += [v["replay_matches_stored"] for v in res["cross_tier"].values() if "replay_matches_stored" in v]
    res["all_ok"] = all(oks)
    sc.dump(sc.OUT / "reporting_checks.json", res)
    write_markdown(res, sc.DOC / "reporting_checks.md")
    print(f"all checks ok: {res['all_ok']}")
    return 0 if res["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
