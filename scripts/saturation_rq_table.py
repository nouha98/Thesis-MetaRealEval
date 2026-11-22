"""Note 3: one stratified table of RQ1-RQ4 per run (plan rev. 3, Part A). Exploratory throughout.

    python scripts/saturation_rq_table.py [--permutations 10000]

Rows are RQ1-RQ4 plus, for the Tier 2 runs, Stage 2b coupling (LLM - operator lift per task, read
from the frozen endpoints' per-task rows), columns the saturation subsets:

  All                     every task with a defined per-task effect
  non-extreme             has_base & ~floor & ~ceiling   (models not all at 0, not all at 1)
  baseline-discriminating base_disc: >= 2 distinct original-prompt model scores

The two subsets differ by the tasks where every model ties at an intermediate score. Both come
from ``saturation_simulation.build_row`` on the original prompt and the intact P suite, so they are
pre-treatment covariates. Every cell is (effect, 95% CI, n) or None with a stated reason.

Read-only on every historical result; writes only results_saturation/rq_table/ and
doc/saturation/rq_table.md (+ .tex). Nothing here is confirmatory.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saturation_common as sc  # noqa: E402
import saturation_simulation as ss  # noqa: E402

from meta_real_eval.analysis.statistics import (  # noqa: E402
    bootstrap_ci, holm, roc_auc, spearman_rho_defined, wilcoxon_test)
from meta_real_eval.rq2.ranking import comparable  # noqa: E402

OUT = sc.OUT / "rq_table"
SEED = 42
COLUMNS = ("all", "non_extreme", "baseline_discriminating")
COLUMN_TITLES = {"all": "All", "non_extreme": "Non-extreme", "baseline_discriminating": "Baseline-discriminating"}
# run -> (tier, simulation run name, RQ4 source)
RUNS = {
    "tier2_graded": ("tier2", "tier2_graded", ("t2", "mean_primary")),
    "tier2_pass1": ("tier2", "tier2_pass1", ("t2", "pass@1")),
    "tier1_pass1": ("tier1", "tier1_pass1", ("t1", None)),
}
RESULTS_ROOT = {"tier1": sc.TIER1, "tier2": sc.T2_SCORES}
SUMMARY = {"tier1": sc.TIER1 / "analysis_summary.json", "tier2": sc.T2_POST / "analysis_summary.json"}
# Stage 2b endpoints (Tier 2 only; Tier 1 has no coupling run, HumanEval has a single check())
COUPLING_ENDPOINTS = sc.REPO / "results_tier2_ext" / "coupling" / "full" / "endpoints.json"


def coupling_per_task(path: Path = COUPLING_ENDPOINTS):
    """{task: (LLM lift, operator lift)} for the contributing tasks of the frozen coupling endpoints;
    None when Stage 2b has not been run here. Read-only; nothing is recomputed."""
    if not path.exists():
        return None
    rows = json.loads(path.read_text(encoding="utf-8"))["per_task"]
    return {r["task"]: (r["means"]["llm_whole"]["lift"], r["means"]["operator"]["lift"])
            for r in rows if r.get("excluded") is None}


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------

def _f(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)


def mean_cell(values: list[float]) -> dict:
    """Mean with a percentile bootstrap CI over tasks (the shared helper, seed 42)."""
    v = [float(x) for x in values if x is not None and not np.isnan(x)]
    if not v:
        return {"mean": None, "lo": None, "hi": None, "n": 0, "reason": "no task with a defined effect"}
    lo, hi = bootstrap_ci(v, seed=SEED) if len(v) > 1 else (None, None)
    return {"mean": float(np.mean(v)), "lo": lo, "hi": hi, "n": len(v)}


def paired_cell(a: list[float], b: list[float]) -> dict:
    """Mean of a - b per task, its CI, and the paired Wilcoxon of the RQ1 analysis."""
    cell = mean_cell([x - y for x, y in zip(a, b)])
    cell["wilcoxon"] = wilcoxon_test(a, b) if len(a) > 1 else None
    return cell


def auc_cell(scores: list[float], labels: list[int]) -> dict:
    r = roc_auc(scores, labels)
    out = {"auc": r["auc"], "n": len(scores), "n_positive": r["n_positive"], "n_negative": r["n_negative"]}
    if r["auc"] is None:
        out["reason"] = "one label class only: AUC undefined (the label is fixed on this subset)"
    return out


def perm_spearman(x: list[float], y: list[float], n_perm: int, seed: int = SEED) -> dict:
    """Spearman rho with a task-level permutation p-value (two-sided); None when undefined."""
    base = spearman_rho_defined(x, y)
    if base["rho"] is None:
        return {"rho": None, "p_perm": None, "n": len(x), "reason": base.get("note")}
    from scipy.stats import rankdata
    rx, ry = rankdata(x), rankdata(y)
    rng = np.random.default_rng(seed)
    obs = abs(np.corrcoef(rx, ry)[0, 1])
    hits = sum(abs(np.corrcoef(rx, rng.permutation(ry))[0, 1]) >= obs - 1e-12 for _ in range(n_perm))
    return {"rho": base["rho"], "p_perm": (hits + 1) / (n_perm + 1), "n": len(x), "n_permutations": n_perm}


# ---------------------------------------------------------------------------
# Strata (the saturation indicators, exactly as the simulation builds them)
# ---------------------------------------------------------------------------

def strata_for(run) -> dict[str, dict]:
    rows = [ss.build_row(t.scores, t.universe, run.models, run.min_cov) for t in run.tasks]
    out = {}
    for t, r in zip(run.tasks, rows):
        out[t.label] = {"non_extreme": bool(r["has_base"] and not r["floor"] and not r["ceiling"]),
                        "baseline_discriminating": bool(r["base_disc"]), "floor": bool(r["floor"]),
                        "ceiling": bool(r["ceiling"]), "spread": _f(r["spread"])}
    return out


def in_column(strata: dict, label: str, column: str) -> bool:
    if column == "all":
        return label in strata
    return bool(strata.get(label, {}).get(column))


# ---------------------------------------------------------------------------
# Per-task effects
# ---------------------------------------------------------------------------

def rq1_per_task(ar, root: Path) -> dict[str, tuple[float, float]]:
    """{task: (operator kill rate, LLM kill rate)} for tasks with both, as analyze_rq1 pairs them."""
    ar.RESULTS = root
    rq1 = ar.analyze_rq1()
    return {t: (v["traditional_kill_rate"], v["llm_kill_rate"]) for t, v in rq1["per_task_adequacy"].items()}


def rq3_per_task(root: Path) -> dict[str, tuple[float, int]]:
    """{task: (pairwise disagreement rate, label)}, the task-level rule of analyze_rq3: label 1 when
    >= 1 consensus-scored solution fails the benchmark; tasks without scored solutions or with an
    undefined rate are left out (never coerced)."""
    out = {}
    base = root / "rq3" / "execute"
    for td in sorted(p for p in base.iterdir() if p.is_dir()):
        f = td / "divergence.json"
        if not f.exists():
            continue
        dv = json.loads(f.read_text(encoding="utf-8"))
        scored = [x for x in dv.get("solutions", []) if "consensus_disagreement_rate" in x and "passes_benchmark" in x]
        rate = dv.get("pairwise_disagreement_rate")
        if scored and rate is not None:
            out[td.name] = (float(rate), int(any(not x["passes_benchmark"] for x in scored)))
    return out


def rq4_per_task(source: tuple) -> tuple[dict[str, dict], dict]:
    """{task: {"tau_drop", "collapsed"}} (tau_b level 0.0 minus level 0.8; every model tied at 0.8)
    and the population note. Tier 2 reads the pipeline's own per-task output (units design);
    Tier 1 the stored saturation re-analysis rows."""
    kind, key = source
    if kind == "t2":
        summ = json.loads((sc.T2_POST / "rq4" / "summary" / "tier2_rq4.json").read_text(encoding="utf-8"))
        block = summ["designs"]["units"][key]
        per = {t: {"tau_drop": _f(v["tau_b_drop"]), "collapsed": v["collapsed_at_top"]}
               for t, v in block["per_task"].items()}
        meta = {"design": f"units/{key}", "n_eligible": block["n_eligible"],
                "eligible": sorted(block["eligible_tasks"]),
                "population_note": "RQ4 eligibility already requires a defined (untied) intact ranking and "
                                   ">= 5 oracle units, so no floor or saturated task can enter."}
        return per, meta
    rq4 = json.loads((sc.OUT / "rq4_reanalysis.json").read_text(encoding="utf-8"))["tier1_assertions_pass1"]
    per = {r["label"]: {"tau_drop": _f(r["tau_drop"]), "collapsed": bool(r["collapsed_0.8"])} for r in rq4["rows"]}
    meta = {"design": "assertions/pass@1", "n_eligible": len(per), "eligible": sorted(per),
            "population_note": "Tier 1 RQ4 covers the discriminating tasks only (intact ranking defined)."}
    return per, meta


# ---------------------------------------------------------------------------
# RQ2: plain cells from the stored simulation; the cross-fit S1a cell computed here
# ---------------------------------------------------------------------------

SUBSET_KEY = {"all": "S0_full", "non_extreme": "S1a_non_extreme",
              "baseline_discriminating": "S1b_baseline_discriminating"}


def crossfit_masks(run) -> dict:
    """``saturation_simulation.crossfit`` with the non-extreme mask added (the stored cross-fit has
    only S0 and S1b). Same halves, same row construction, same averaging; selection indicators come
    from the other half only."""
    halves = (list(range(5)), list(range(5, 10)))
    per_dir = []
    for cls_h, ev_h in ((0, 1), (1, 0)):
        rows = []
        for t in run.tasks:
            def half_scores(rel, idx, t=t):
                return {m: comparable(float(np.mean([v[i] for i in idx]))) for m, v in t.raw.get(rel, {}).items()}
            ev = {rel: half_scores(rel, halves[ev_h]) for rel in t.raw}
            row = ss.build_row(ev, t.universe, run.models, run.min_cov)
            cls = ss.build_row({"original": half_scores("original", halves[cls_h])}, [], run.models, run.min_cov)
            for k in ("has_base", "floor", "ceiling", "base_disc", "difficulty", "spread"):
                row[k] = cls[k]
            rows.append(row)
        A = ss.to_arrays(rows)
        masks = {"S0_full": np.ones(len(rows), bool), "S1a_non_extreme": A["non_extreme"],
                 "S1b_baseline_discriminating": A["base_disc"]}
        per_dir.append({n: ss.point(A, m) for n, m in masks.items()})
    out = {}
    for name in per_dir[0]:
        avg = {}
        for k in ss.POINT_KEYS:
            vals = [d[name][k] for d in per_dir if d[name][k] is not None]
            avg[k] = float(np.mean(vals)) if vals else None
        out[name] = {"average_of_both_directions": avg, "direction_A_to_B": per_dir[0][name],
                     "direction_B_to_A": per_dir[1][name]}
    return out


def rq2_cells(sim: dict, cross: dict) -> dict:
    out = {}
    for col, key in SUBSET_KEY.items():
        s = sim["subsets"].get(key)
        if s is None:
            out[col] = {"reason": "subset empty"}
            continue
        p, boot, tests = s["point"], s.get("bootstrap_within_subset", {}), s["tests"]
        cf = cross[key]["average_of_both_directions"]
        out[col] = {
            "gap_paired": {"mean": p["gap_paired"], "lo": boot.get("gap_paired", {}).get("lo"),
                           "hi": boot.get("gap_paired", {}).get("hi"), "n": int(p["n_both"])},
            "mean_tau_control": p["mean_tau_c"], "mean_tau_paraphrase": p["mean_tau_p"],
            "rev_diff": {"mean": p["rev_diff"], "lo": boot.get("rev_diff", {}).get("lo"),
                         "hi": boot.get("rev_diff", {}).get("hi"), "n": int(p["n_rev_paired"])},
            "wilcoxon_tau_paired": tests.get("wilcoxon_tau_paired"),
            "crossfit_gap_paired": {"mean": cf["gap_paired"], "n_avg": cf["n_both"],
                                    "note": "independent halves: subset from completions 0-4 (5-9), tau from the other half; "
                                            "average of both directions; point estimate only"},
            "crossfit_rev_diff": cf["rev_diff"],
        }
    return out


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------

def build_run(name: str, ar, n_perm: int, run=None) -> dict:
    tier, sim_name, rq4_source = RUNS[name]
    if run is None:
        _, key, ranking = ss.RUNS[sim_name]
        run = ss.load_run(sc.VIEWS / tier, ranking, key)
    strata = strata_for(run)
    sim = json.loads((sc.OUT / sim_name / "simulation.json").read_text(encoding="utf-8"))
    cross = crossfit_masks(run)
    rq1 = rq1_per_task(ar, RESULTS_ROOT[tier])
    rq3 = rq3_per_task(RESULTS_ROOT[tier])
    rq4, rq4_meta = rq4_per_task(rq4_source)
    cpl = coupling_per_task() if tier == "tier2" else None

    table: dict = {"RQ1": {}, "RQ2": rq2_cells(sim, cross), "RQ3": {}, "RQ4": {}}
    for col in COLUMNS:
        labs = [t for t in sorted(rq1) if in_column(strata, t, col)]
        table["RQ1"][col] = paired_cell([rq1[t][0] for t in labs], [rq1[t][1] for t in labs])
        labs = [t for t in sorted(rq3) if in_column(strata, t, col)]
        table["RQ3"][col] = auc_cell([rq3[t][0] for t in labs], [rq3[t][1] for t in labs])
        labs = [t for t in sorted(rq4) if in_column(strata, t, col)]
        drops = [rq4[t]["tau_drop"] for t in labs]
        coll = [rq4[t]["collapsed"] for t in labs if rq4[t]["collapsed"] is not None]
        table["RQ4"][col] = {"tau_drop": mean_cell(drops),
                             "collapse_share_at_0.8": {"share": float(np.mean(coll)) if coll else None,
                                                       "n": len(coll)}}
        if cpl is not None:
            labs = [t for t in sorted(cpl) if in_column(strata, t, col)]
            table.setdefault("Coupling", {})[col] = paired_cell([cpl[t][0] for t in labs], [cpl[t][1] for t in labs])

    # moderation by continuous baseline spread (exploratory; Holm across the rows that have a test)
    def spread(t):
        return strata.get(t, {}).get("spread")
    mod = {}
    xs = [t for t in sorted(rq1) if spread(t) is not None]
    mod["RQ1"] = perm_spearman([rq1[t][0] - rq1[t][1] for t in xs], [spread(t) for t in xs], n_perm)
    xs = [t for t in sorted(rq4) if spread(t) is not None and rq4[t]["tau_drop"] is not None]
    mod["RQ4"] = perm_spearman([rq4[t]["tau_drop"] for t in xs], [spread(t) for t in xs], n_perm)
    pv = {k: v["p_perm"] for k, v in mod.items() if v.get("p_perm") is not None}
    mod["holm"] = ({k: {kk: (bool(vv) if isinstance(vv, (bool, np.bool_)) else vv) for kk, vv in v.items()}
                    for k, v in holm(pv).items()} if pv else None)
    mod["RQ2"] = {k: sim["crossfit"][k]["average_of_both_directions"]["gap_paired"]
                  for k in ("S4_spread_T1", "S4_spread_T2", "S4_spread_T3") if k in sim["crossfit"]}
    mod["RQ2_note"] = "cross-fit paraphrase-minus-control gap by baseline-spread tercile (stored; descriptive)"
    terc = defaultdict(list)
    defined = [t for t in sorted(rq3) if spread(t) is not None and strata[t]["baseline_discriminating"]]
    if defined:
        sp = np.array([spread(t) for t in defined])
        for i, g in enumerate(ss.terciles(sp, np.ones(len(defined), bool)), 1):
            terc[f"T{i}"] = [defined[j] for j in np.flatnonzero(g)]
    mod["RQ3"] = {k: auc_cell([rq3[t][0] for t in v], [rq3[t][1] for t in v]) for k, v in terc.items()}
    mod["RQ3_note"] = "AUC within baseline-spread terciles of the baseline-discriminating tasks (descriptive)"

    # RQ3: is the label fixed by construction on floor / saturated tasks?
    label_by_stratum = {}
    for s in ("floor", "ceiling"):
        labs = [t for t in rq3 if strata.get(t, {}).get(s)]
        label_by_stratum[s] = {"n": len(labs), "n_positive": sum(rq3[t][1] for t in labs)}

    rq4_not_disc = [t for t in rq4_meta["eligible"] if not strata.get(t, {}).get("baseline_discriminating")]
    counts = {k: sum(v[k] for v in strata.values()) for k in ("non_extreme", "baseline_discriminating", "floor", "ceiling")}
    return {"run": name, "tier": tier, "score": run.key, "n_tasks": len(strata), "counts": counts,
            "table": table, "moderation": mod, "rq3_label_on_extreme_strata": label_by_stratum,
            "rq4_population": {**{k: v for k, v in rq4_meta.items() if k != "eligible"},
                               "eligible_not_baseline_discriminating": rq4_not_disc},
            "coupling_population": (None if cpl is None else
                                    {"contributing": len(cpl), "with_saturation_stratum": sum(t in strata for t in cpl),
                                     "note": "exploratory; the confirmatory coupling result is the unstratified "
                                             "primary in endpoints.json"}),
            "checks": checks(name, tier, sim, cross, counts, table, rq4_meta, cpl, strata)}


# ---------------------------------------------------------------------------
# Checks against the stored results (the table must reproduce what is already reported)
# ---------------------------------------------------------------------------

def checks(name, tier, sim, cross, counts, table, rq4_meta, cpl=None, strata=None) -> list[dict]:
    out = []

    def add(check, ok, detail=""):
        out.append({"run": name, "check": check, "ok": bool(ok), "detail": detail})
    meta = sim["meta"]["counts"]
    add("subset counts equal the simulation", counts["non_extreme"] == meta["non_extreme"]
        and counts["baseline_discriminating"] == meta["baseline_discriminating"]
        and counts["floor"] == meta["floor"] and counts["ceiling"] == meta["ceiling"], f"{counts} vs {meta}")
    for k in ("S0_full", "S1b_baseline_discriminating"):
        stored = sim["crossfit"][k]["average_of_both_directions"]
        worst, other = sc.deep_diff(stored, cross[k]["average_of_both_directions"], tol=1e-12)
        add(f"cross-fit {k} recomputed equals the stored cross-fit", not other, f"max diff {worst:.1e}")
    summ = json.loads(SUMMARY[tier].read_text(encoding="utf-8"))
    w_stored = summ["rq1"]["wilcoxon_paired_kill_rate_trad_vs_llm"]
    w_new = table["RQ1"]["all"]["wilcoxon"]
    add("RQ1 All Wilcoxon equals analysis_summary", w_new is not None
        and abs(w_new["statistic"] - w_stored["statistic"]) < 1e-9 and abs(w_new["p_value"] - w_stored["p_value"]) < 1e-12
        and table["RQ1"]["all"]["n"] == summ["rq1"]["n_tasks_with_both_categories"],
        f"{w_new} vs {w_stored}")
    a_stored = summ["rq3"]["roc_auc_per_task"]
    a_new = table["RQ3"]["all"]
    add("RQ3 All AUC equals analysis_summary", a_new["auc"] is not None and abs(a_new["auc"] - a_stored["auc"]) < 1e-12
        and a_new["n_positive"] == a_stored["n_positive"] and a_new["n_negative"] == a_stored["n_negative"],
        f"{a_new['auc']} vs {a_stored['auc']}")
    add("RQ4 per-task rows cover the eligible tasks", table["RQ4"]["all"]["tau_drop"]["n"] <= rq4_meta["n_eligible"],
        f"{table['RQ4']['all']['tau_drop']['n']} defined of {rq4_meta['n_eligible']} eligible")
    if cpl is not None:   # a label mismatch would silently empty every coupling cell
        missing = sorted(t for t in cpl if t not in (strata or {}))
        add("every contributing coupling task has a saturation stratum", not missing,
            f"{len(cpl) - len(missing)}/{len(cpl)}; missing {missing[:5]}")
    return out


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def _num(x, nd=3):
    return "–" if x is None else f"{x:.{nd}f}"


def _ci(c):
    if c.get("mean") is None:
        return f"undefined ({c.get('reason', 'n = 0')})"
    ci = "" if c.get("lo") is None else f" [{_num(c['lo'])}, {_num(c['hi'])}]"
    return f"{_num(c['mean'])}{ci}, n={c['n']}"


def table_rows(res: dict) -> list[tuple[str, list[str]]]:
    T = res["table"]
    rows = [("RQ1 operator − LLM kill rate", [_ci(T["RQ1"][c]) for c in COLUMNS])]
    rows.append(("RQ2 control − paraphrase τ_b (paired)", [_ci(T["RQ2"][c]["gap_paired"]) if "gap_paired" in T["RQ2"][c]
                                                          else T["RQ2"][c]["reason"] for c in COLUMNS]))
    rows.append(("RQ2 same, cross-fit (point)", [f"{_num(T['RQ2'][c]['crossfit_gap_paired']['mean'])}, "
                                                 f"n≈{_num(T['RQ2'][c]['crossfit_gap_paired']['n_avg'], 1)}"
                                                 if "crossfit_gap_paired" in T["RQ2"][c] else "–" for c in COLUMNS]))
    rows.append(("RQ2 reversal difference", [_ci(T["RQ2"][c]["rev_diff"]) if "rev_diff" in T["RQ2"][c] else "–"
                                             for c in COLUMNS]))
    rows.append(("RQ3 task-level AUC", [f"{_num(T['RQ3'][c]['auc'])}, n={T['RQ3'][c]['n']} "
                                        f"({T['RQ3'][c]['n_positive']}+/{T['RQ3'][c]['n_negative']}−)"
                                        for c in COLUMNS]))
    rows.append(("RQ4 τ_b drop 0.0→0.8", [_ci(T["RQ4"][c]["tau_drop"]) for c in COLUMNS]))
    rows.append(("RQ4 collapse share at 0.8", [f"{_num(T['RQ4'][c]['collapse_share_at_0.8']['share'])}, "
                                               f"n={T['RQ4'][c]['collapse_share_at_0.8']['n']}" for c in COLUMNS]))
    if "Coupling" in T:
        rows.append(("Coupling LLM − operator lift", [_ci(T["Coupling"][c]) for c in COLUMNS]))
    return rows


def write_md(results: dict, path: Path) -> None:
    L = ["# Note 3: RQ1–RQ4 by saturation subset", "",
         "*Exploratory. Generated by `scripts/saturation_rq_table.py`; never part of the confirmatory hierarchy.*", "",
         "**Subsets** (original prompt, intact P suite; pre-treatment):",
         "- *Non-extreme*: the models are not all at 0 and not all at 1.",
         "- *Baseline-discriminating*: at least two distinct model scores. It excludes the tasks where every model "
         "ties at an intermediate score, which is why it is smaller.", ""]
    for name, res in results.items():
        c = res["counts"]
        L += [f"## {name} ({res['n_tasks']} tasks; score {res['score']})", "",
              f"Non-extreme {c['non_extreme']}, baseline-discriminating {c['baseline_discriminating']}, "
              f"floor {c['floor']}, saturated {c['ceiling']}.", "",
              "| Row | " + " | ".join(COLUMN_TITLES[x] for x in COLUMNS) + " |", "|---|---|---|---|"]
        for label, cells in table_rows(res):
            L.append(f"| {label} | " + " | ".join(cells) + " |")
        rq4p = res["rq4_population"]
        lab = res["rq3_label_on_extreme_strata"]
        mod = res["moderation"]
        L += ["", f"- RQ4 ({rq4p['design']}): {rq4p['population_note']} Eligible tasks outside the "
                  f"baseline-discriminating subset: {len(rq4p['eligible_not_baseline_discriminating'])}.",
              f"- RQ3 label on floor tasks: {lab['floor']['n_positive']}/{lab['floor']['n']} positive; on saturated "
              f"tasks: {lab['ceiling']['n_positive']}/{lab['ceiling']['n']} positive (fixed or near-fixed by construction).",
              f"- Moderation by baseline spread: RQ1 ρ = {_num(mod['RQ1']['rho'])} (p_perm {_num(mod['RQ1']['p_perm'], 4)}, "
              f"n={mod['RQ1']['n']}); RQ4 ρ = {_num(mod['RQ4']['rho'])} (p_perm {_num(mod['RQ4']['p_perm'], 4)}, "
              f"n={mod['RQ4']['n']}); Holm {json.dumps(mod['holm'], default=str)}. RQ2 cross-fit gap by spread tercile: "
              f"{', '.join(f'{k[-2:]} {_num(v)}' for k, v in mod['RQ2'].items())}. RQ3 AUC by spread tercile: "
              f"{', '.join(f'{k} {_num(v['auc'])} (n={v['n']})' for k, v in mod['RQ3'].items())}.",
              f"- Checks: {sum(c['ok'] for c in res['checks'])}/{len(res['checks'])} OK.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_tex(res: dict, path: Path) -> None:
    def esc(s):
        s = s.replace("τ_b", "TAUB").replace("_", r"\_")
        return (s.replace("TAUB", r"$\tau_b$").replace("−", "--").replace("→", r"$\to$")
                 .replace("≈", r"$\approx$"))
    L = [r"% generated by scripts/saturation_rq_table.py -- do not edit by hand",
         r"\begin{tabular}{lccc}", r"\toprule",
         "Row & " + " & ".join(COLUMN_TITLES[c] for c in COLUMNS) + r" \\", r"\midrule"]
    for label, cells in table_rows(res):
        L.append(esc(label) + " & " + " & ".join(esc(c) for c in cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--permutations", type=int, default=10000)
    args = ap.parse_args(argv)
    if not (sc.VIEWS / "tier1").exists() or not (sc.VIEWS / "tier2").exists():
        raise SystemExit("views missing: run scripts/saturation_baseline.py first")
    ar = sc.load_analyze_results()
    results = {}
    for name in RUNS:
        print(f"[{name}] ...", flush=True)
        results[name] = build_run(name, ar, args.permutations)
    all_checks = [c for r in results.values() for c in r["checks"]]
    for c in all_checks:
        print(("OK   " if c["ok"] else "FAIL ") + f"{c['run']}: {c['check']}  {c['detail'][:120]}")
    sc.dump(OUT / "rq_table.json", results)
    write_md(results, sc.DOC / "rq_table.md")
    write_tex(results["tier2_graded"], sc.DOC / "rq_table_tier2_graded.tex")
    sc.dump(OUT / "run_manifest.json", {
        "script": "scripts/saturation_rq_table.py", "argv": sys.argv if argv is None else argv,
        "git": sc.git_state(), "permutations": args.permutations, "seed": SEED,
        "inputs": {"simulation": {n: sc.sha256_file(sc.OUT / RUNS[n][1] / "simulation.json") for n in RUNS},
                   "rq4_reanalysis": sc.sha256_file(sc.OUT / "rq4_reanalysis.json"),
                   "tier2_rq4": sc.sha256_file(sc.T2_POST / "rq4" / "summary" / "tier2_rq4.json"),
                   "analysis_summary": {t: sc.sha256_file(p) for t, p in SUMMARY.items()}},
        "checks_ok": f"{sum(c['ok'] for c in all_checks)}/{len(all_checks)}"})
    bad = [c for c in all_checks if not c["ok"]]
    print(f"\n{len(all_checks) - len(bad)}/{len(all_checks)} checks OK; wrote {OUT} and {sc.DOC / 'rq_table.md'}")
    return int(bool(bad))


if __name__ == "__main__":
    sys.exit(main())
