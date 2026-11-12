"""Phases 2-3 of the saturation analysis: filter / resample the STORED Tier 1 and Tier 2 results
and see what happens to ranking stability (plan rev. 7). No model is run, nothing is re-scored,
no existing result file is written.

    python scripts/saturation_simulation.py [--replicates 1000] [--smoke]

Three outcomes are reported side by side, never merged into one verdict:
  1. information availability   - how many tasks give a usable (defined) comparison
  2. conditional ranking stability - tau_b / reversal among tasks that can distinguish the models
  3. benchmark-level stability  - aggregate 3-model leaderboard, margins, pairwise ordering changes

Every statistic is a weighted sum over one per-task table, so a subset, a bootstrap replicate, a
random control and a dial replicate all go through the same code (validated against the existing
``analyze_results.analyze_rq2`` in ``validate``).
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saturation_common as sc  # noqa: E402

from meta_real_eval.analysis.statistics import bootstrap_ci, spearman_rho, wilcoxon_test  # noqa: E402
from meta_real_eval.rq2.corpus import FAMILIES, min_families_covered  # noqa: E402
from meta_real_eval.rq2.ranking import (  # noqa: E402
    _rank_vector, _tau_b, cell_is_scored, collapse_tau_by_arm, comparable, relation_arm)

SEED = 42
RUNS = {  # name -> (tier, score key, rankings file, view)
    "tier1_pass1": ("tier1", "pass@1", "rankings.json"),
    "tier2_graded": ("tier2", "mean_primary", "rankings.json"),
    "tier2_pass1": ("tier2", "pass@1", "rankings_pass1.json"),
}
DIAL_SHARES = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
MIN_FILL_POOL = 30      # a floor-only / ceiling-only fill needs a pool this large to be meaningful


# ---------------------------------------------------------------------------
# Loading and the per-task row
# ---------------------------------------------------------------------------

def _sign(a: float, b: float) -> int:
    return (a > b) - (a < b)


def completion_values(cell: dict, key: str):
    """Per-completion scores of a cell (10 floats) or None."""
    vals = cell.get("primary_scores") if key == "mean_primary" else cell.get("per_completion")
    if vals is None or any(v is None for v in vals):
        return None
    return [float(v) for v in vals]


def load_run(view: Path, ranking_file: str, key: str) -> SimpleNamespace:
    root = view / "rq2" / "evaluate"
    dirs = sorted(p for p in root.iterdir() if p.is_dir())
    first = json.loads((dirs[0] / ranking_file).read_text())
    for d in dirs:                       # the model order and corpus families are run-wide
        rk = json.loads((d / ranking_file).read_text())
        if rk.get("corpus_families"):
            first = rk
            break
    models = first["model_ids"]
    families = first.get("corpus_families") or FAMILIES
    tasks = []
    for d in dirs:
        pr = json.loads((d / "pass_rates.json").read_text())
        rk = json.loads((d / ranking_file).read_text())
        scores, raw = {}, {}
        for rel, by_model in pr.items():
            scores[rel], raw[rel] = {}, {}
            for m, cell in by_model.items():
                if cell_is_scored(cell, key):
                    scores[rel][m] = comparable(cell[key])
                    vals = completion_values(cell, key)
                    if vals is not None and len(vals) == 10:
                        raw[rel][m] = vals
        tasks.append(SimpleNamespace(label=d.name, scores=scores, raw=raw,
                                     universe=list(rk["tau_b_per_relation"]), stored_tau=rk["tau_b_per_relation"]))
    return SimpleNamespace(models=models, min_cov=min_families_covered(families), tasks=tasks, key=key)


def reversal(scores: dict, models: list[str]):
    """Per-arm list of pair-level reversal values (variants collapsed as in RQ2), plus the number
    of compared and tied pairs; the same rule as ``analyze_results.analyze_rq2``."""
    base = {m: scores["original"][m] for m in models if m in scores.get("original", {})}
    n_cmp = n_tied = 0
    pair_vals: dict[str, dict[str, float]] = defaultdict(dict)
    for rel, cells in scores.items():
        if rel == "original":
            continue
        var = {m: cells[m] for m in models if m in cells}
        for i, j in combinations(models, 2):
            if i not in base or j not in base or i not in var or j not in var:
                continue
            n_cmp += 1
            bs, vs = _sign(base[i], base[j]), _sign(var[i], var[j])
            if bs == 0 or vs == 0:
                n_tied += 1
                continue
            pair_vals[f"{i} vs {j}"][rel] = float(bs != vs)
    arms: dict[str, list[float]] = defaultdict(list)
    for relvals in pair_vals.values():
        col = collapse_tau_by_arm(relvals)
        for arm in ("control", "template", "llm"):
            if col[arm] is not None:
                arms[arm].append(col[arm])
    return arms, n_cmp, n_tied


def paraphrase_score(scores: dict, models: list[str], rels: list[str]):
    """Per-model paraphrase score: variants averaged within a family, then families averaged."""
    by_fam: dict[str, list[str]] = defaultdict(list)
    for r in rels:
        arm, fam = relation_arm(r)
        if arm == "llm" and len(scores.get(r, {})) == len(models):
            by_fam[fam].append(r)
    if not by_fam:
        return None
    fam_means = [np.mean([[scores[r][m] for m in models] for r in rs], axis=0) for rs in by_fam.values()]
    return np.mean(fam_means, axis=0)


def build_row(scores: dict, universe: list[str], models: list[str], min_cov: int) -> dict:
    """Everything one task contributes to any statistic, from its model scores per relation.

    Mirrors rq2/ranking.compute_ranking_stability (tau_b per relation, completeness, family
    coverage) and the per-task part of analyze_results.analyze_rq2 (collapse to arms, coverage
    gate, pairwise reversal)."""
    base = scores.get("original", {})
    base_complete = len(base) == len(models)
    base_vec = _rank_vector(base, models)
    tau, complete_rels = {}, []
    for rel in universe:
        if not base_complete or len(scores.get(rel, {})) != len(models):
            tau[rel] = None
            continue
        complete_rels.append(rel)
        tau[rel] = _tau_b(base_vec, _rank_vector(scores[rel], models))
    by_arm = collapse_tau_by_arm(tau)
    n_fam = len({relation_arm(r)[1] for r in complete_rels if relation_arm(r)[1] is not None})
    covered = by_arm["llm"] is None or n_fam >= min_cov
    arms, n_cmp, n_tied = reversal(scores, models)
    nan = float("nan")

    def eff(v):
        return v if (covered and v is not None) else nan

    def mean_or_nan(v):
        return sum(v) / len(v) if v else nan

    vals = [base[m] for m in models if m in base] if base_complete else []
    lb_p = paraphrase_score(scores, models, universe)
    ctrl_complete = len(scores.get("control_resample", {})) == len(models)
    return {
        "tau": tau, "covered": covered,
        "tau_c": eff(by_arm["control"]), "tau_p": eff(by_arm["llm"]), "tau_t": eff(by_arm["template"]),
        "rev_c": mean_or_nan(arms.get("control")), "rev_p": mean_or_nan(arms.get("llm")),
        "rev_t": mean_or_nan(arms.get("template")),
        "n_cmp": n_cmp, "n_tied": n_tied, "rel_total": len(tau), "rel_undef": sum(v is None for v in tau.values()),
        # baseline-only indicators (never depend on a variant)
        "has_base": base_complete,
        "floor": base_complete and all(v == 0.0 for v in vals),
        "ceiling": base_complete and all(v == 1.0 for v in vals),
        "base_disc": base_complete and len(set(vals)) > 1,
        "difficulty": float(np.mean(vals)) if vals else nan,
        "spread": float(max(vals) - min(vals)) if vals else nan,
        # leaderboard inputs (same task set for all three arms)
        "lb_ok": bool(base_complete and ctrl_complete and lb_p is not None and covered),
        "S_o": [base[m] for m in models] if base_complete else [0.0] * len(models),
        "S_c": [scores["control_resample"][m] for m in models] if ctrl_complete else [0.0] * len(models),
        "S_p": list(lb_p) if lb_p is not None else [0.0] * len(models),
    }


def to_arrays(rows: list[dict]) -> dict:
    A = {k: np.array([r[k] for r in rows], dtype=float) for k in (
        "tau_c", "tau_p", "tau_t", "rev_c", "rev_p", "rev_t", "n_cmp", "n_tied", "rel_total", "rel_undef",
        "difficulty", "spread")}
    for k in ("floor", "ceiling", "base_disc", "has_base", "lb_ok", "covered"):
        A[k] = np.array([bool(r[k]) for r in rows])
    A["non_extreme"] = A["has_base"] & ~A["floor"] & ~A["ceiling"]
    for k in ("S_o", "S_c", "S_p"):
        A[k] = np.array([r[k] for r in rows], dtype=float)
    return A


# ---------------------------------------------------------------------------
# Statistics as weighted sums (W: replicates x tasks, non-negative counts)
# ---------------------------------------------------------------------------

def _div(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    out = np.full(np.broadcast(a, b).shape, np.nan)
    np.divide(a, b, out=out, where=b > 0)
    return out


def metrics(A: dict, W: np.ndarray) -> dict:
    """Information availability and conditional ranking stability for each weight row."""
    W = np.atleast_2d(W).astype(float)
    out = {"n_tasks": W.sum(1)}
    dc, dp, dt = (~np.isnan(A[k]) for k in ("tau_c", "tau_p", "tau_t"))
    both = dc & dp
    for name, d, v in (("c", dc, A["tau_c"]), ("p", dp, A["tau_p"]), ("t", dt, A["tau_t"])):
        out[f"n_tau_{name}"] = W @ d
        out[f"mean_tau_{name}"] = _div(W @ np.where(d, v, 0.0), out[f"n_tau_{name}"])
    out["n_both"] = W @ both
    diff = np.where(both, np.nan_to_num(A["tau_c"]) - np.nan_to_num(A["tau_p"]), 0.0)
    out["gap_paired"] = _div(W @ diff, out["n_both"])
    out["gap_unpaired"] = out["mean_tau_c"] - out["mean_tau_p"]
    s2 = W @ diff ** 2
    var = _div(s2 - (W @ diff) ** 2 / np.maximum(out["n_both"], 1), out["n_both"] - 1)
    out["se_gap_paired"] = np.sqrt(np.maximum(var, 0)) / np.sqrt(np.maximum(out["n_both"], 1))
    rb = ~np.isnan(A["rev_c"]) & ~np.isnan(A["rev_p"])
    out["n_rev_paired"] = W @ rb
    out["rev_llm"] = _div(W @ np.where(rb, np.nan_to_num(A["rev_p"]), 0.0), out["n_rev_paired"])
    out["rev_ctrl"] = _div(W @ np.where(rb, np.nan_to_num(A["rev_c"]), 0.0), out["n_rev_paired"])
    out["rev_diff"] = out["rev_llm"] - out["rev_ctrl"]
    out["n_cmp"], out["n_tied"] = W @ A["n_cmp"], W @ A["n_tied"]
    out["tied_share"] = _div(out["n_tied"], out["n_cmp"])
    out["undef_share"] = _div(W @ A["rel_undef"], W @ A["rel_total"])
    for name in ("c", "p"):
        out[f"yield_{name}"] = _div(out[f"n_tau_{name}"], out["n_tasks"])
    out["yield_both"] = _div(out["n_both"], out["n_tasks"])
    out["n_non_extreme"], out["n_base_disc"] = W @ A["non_extreme"], W @ A["base_disc"]
    return out


def _pair_signs(M: np.ndarray) -> np.ndarray:
    n = M.shape[1]
    return np.stack([np.sign(M[:, i] - M[:, j]) for i, j in combinations(range(n), 2)], axis=1)


def leaderboard(A: dict, W: np.ndarray, ref_signs: np.ndarray | None = None) -> dict:
    """Aggregate model scores under the original, control and paraphrase prompts over the same
    tasks, compared after rounding to 12 decimals (a real difference between aggregate scores is
    far larger; equal sums in a different order differ only in the last bits)."""
    W = np.atleast_2d(W).astype(float) * A["lb_ok"]
    n = W.sum(1, keepdims=True)
    M = {k: np.round(_div(W @ A[s], n), 12) for k, s in (("o", "S_o"), ("c", "S_c"), ("p", "S_p"))}
    so, sc_, sp = (_pair_signs(M[k]) for k in ("o", "c", "p"))
    out = {"lb_n_tasks": n[:, 0], "M_o": M["o"], "M_c": M["c"], "M_p": M["p"]}
    for name, s in (("c", sc_), ("p", sp)):
        flips = so * s == -1
        out[f"flip_{name}_pairs"] = flips
        out[f"flip_{name}_any"] = flips.any(1)
        out[f"tie_{name}_any"] = ((so == 0) | (s == 0)).any(1)
        out[f"shift_{name}"] = np.abs(M[name] - M["o"]).mean(1)
    srt = -np.sort(-M["o"], axis=1)
    out["margin_o"] = np.min(srt[:, :-1] - srt[:, 1:], axis=1)
    if ref_signs is not None:
        out["same_order_as_ref"] = (so == ref_signs).all(1)
    return out


def summ(x) -> dict:
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if not len(x):
        return {"mean": None, "lo": None, "hi": None, "n": 0}
    return {"mean": float(x.mean()), "lo": float(np.percentile(x, 2.5)), "hi": float(np.percentile(x, 97.5)),
            "n": int(len(x))}


# ---------------------------------------------------------------------------
# Weight generators: bootstrap, random controls, dial. None looks at tau values.
# ---------------------------------------------------------------------------

def boot_weights(mask: np.ndarray, R: int, rng) -> np.ndarray:
    """Task-level bootstrap restricted to ``mask`` (with replacement, same size)."""
    pos = np.flatnonzero(mask)
    W = np.zeros((R, len(mask)))
    if len(pos):
        W[:, pos] = rng.multinomial(len(pos), np.full(len(pos), 1 / len(pos)), size=R)
    return W


def sample_weights(pool: np.ndarray, size: int, R: int, rng) -> np.ndarray:
    """``R`` uniform random subsets of ``size`` tasks from ``pool`` (without replacement)."""
    pos = np.flatnonzero(pool)
    size = min(size, len(pos))
    sel = np.argsort(rng.random((R, len(pos))), axis=1)[:, :size]
    W = np.zeros((R, len(pool)))
    W[np.arange(R)[:, None], pos[sel]] = 1.0
    return W


def dial_weights(disc: np.ndarray, fill: np.ndarray, share: float, R: int, rng) -> np.ndarray:
    """Benchmark-sized resamples with ``share`` of the tasks from ``disc`` and the rest from ``fill``
    (both with replacement)."""
    N = len(disc)
    n_d = int(round(share * N))
    W = boot_weights_n(disc, n_d, R, rng) + boot_weights_n(fill, N - n_d, R, rng)
    return W


def boot_weights_n(mask: np.ndarray, k: int, R: int, rng) -> np.ndarray:
    pos = np.flatnonzero(mask)
    W = np.zeros((R, len(mask)))
    if k and len(pos):
        W[:, pos] = rng.multinomial(k, np.full(len(pos), 1 / len(pos)), size=R)
    return W


def terciles(values: np.ndarray, mask: np.ndarray) -> list[np.ndarray]:
    """Three near-equal groups of ``mask`` ordered by ``values``; ties broken by position (task
    label order), which is independent of every outcome."""
    pos = np.flatnonzero(mask)
    order = pos[np.lexsort((pos, values[pos]))]
    groups = []
    for part in np.array_split(order, 3):
        g = np.zeros(len(mask), bool)
        g[part] = True
        groups.append(g)
    return groups


def define_subsets(A: dict) -> dict[str, np.ndarray]:
    sub = {"S0_full": np.ones(len(A["tau_c"]), bool),
           "S1a_non_extreme": A["non_extreme"].copy(),
           "S1b_baseline_discriminating": A["base_disc"].copy(),
           "S2_drop_ceiling": ~A["ceiling"], "S2_drop_floor": ~A["floor"],
           "S3_floor_only": A["floor"].copy(), "S3_ceiling_only": A["ceiling"].copy()}
    for i, g in enumerate(terciles(A["spread"], A["base_disc"]), 1):
        sub[f"S4_spread_T{i}"] = g
    for i, g in enumerate(terciles(A["difficulty"], A["base_disc"]), 1):
        sub[f"S4_difficulty_T{i}"] = g       # T1 = hardest (lowest mean score)
    return {k: v for k, v in sub.items() if v.sum() > 0}


# ---------------------------------------------------------------------------
# One run: subsets, controls, dial, leaderboard
# ---------------------------------------------------------------------------

POINT_KEYS = ["n_tasks", "n_non_extreme", "n_base_disc", "n_tau_c", "n_tau_p", "n_both", "n_rev_paired",
              "yield_c", "yield_p", "yield_both", "mean_tau_c", "mean_tau_p", "mean_tau_t", "gap_paired",
              "gap_unpaired", "se_gap_paired", "rev_llm", "rev_ctrl", "rev_diff", "n_cmp", "n_tied",
              "tied_share", "undef_share"]
CONTROL_KEYS = ["n_both", "yield_both", "mean_tau_c", "mean_tau_p", "gap_paired", "se_gap_paired", "rev_diff",
                "undef_share"]
LB_KEYS = ["flip_c_any", "flip_p_any", "tie_c_any", "tie_p_any", "margin_o", "shift_c", "shift_p"]


def point(A, mask) -> dict:
    m = metrics(A, mask[None, :])
    return {k: (None if np.isnan(m[k][0]) else float(m[k][0])) for k in POINT_KEYS}


def lb_point(A, mask) -> dict:
    out = leaderboard(A, mask[None, :].astype(float))
    n = int(out["lb_n_tasks"][0])
    return {"n_tasks": n, "scores_original": out["M_o"][0].tolist(), "scores_control": out["M_c"][0].tolist(),
            "scores_paraphrase": out["M_p"][0].tolist(),
            "reversed_pairs_control": out["flip_c_pairs"][0].tolist(),
            "reversed_pairs_paraphrase": out["flip_p_pairs"][0].tolist(),
            "margin_original": float(out["margin_o"][0]) if n else None,
            "mean_abs_shift_control": float(out["shift_c"][0]) if n else None,
            "mean_abs_shift_paraphrase": float(out["shift_p"][0]) if n else None}


def tests(A, mask) -> dict:
    """Original-function bootstrap CIs and paired Wilcoxon tests for a deterministic subset."""
    out = {}
    for name, key in (("control", "tau_c"), ("paraphrase", "tau_p"), ("template", "tau_t")):
        v = A[key][mask & ~np.isnan(A[key])]
        out[f"tau_{name}"] = ({"mean": float(v.mean()), "n": int(len(v)),
                               "ci": list(bootstrap_ci(list(v)))} if len(v) > 1 else {"n": int(len(v))})
    both = mask & ~np.isnan(A["tau_c"]) & ~np.isnan(A["tau_p"])
    out["wilcoxon_tau_paired"] = (wilcoxon_test(list(A["tau_c"][both]), list(A["tau_p"][both]))
                                  if both.sum() > 1 else None)
    rb = mask & ~np.isnan(A["rev_c"]) & ~np.isnan(A["rev_p"])
    out["wilcoxon_reversal_paired"] = (wilcoxon_test(list(A["rev_p"][rb]), list(A["rev_c"][rb]))
                                       if rb.sum() > 1 else None)
    return out


def summ_freq(x) -> dict:
    """A frequency over replicates (0/1 indicators): mean with its Monte Carlo 95% interval,
    mean +- 1.96 sd / sqrt(R). Percentiles of a 0/1 variable would be meaningless (always 0 and 1)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if not len(x):
        return {"mean": None, "lo": None, "hi": None, "n": 0, "interval": "Monte Carlo 95% of the frequency"}
    se = 1.96 * x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else float("nan")
    return {"mean": float(x.mean()), "lo": float(x.mean() - se), "hi": float(x.mean() + se), "n": int(len(x)),
            "interval": "Monte Carlo 95% of the frequency"}


def lb_boot(A, W, ref_signs) -> dict:
    """Leaderboard summaries over replicates. Frequencies carry a Monte Carlo interval; margin and
    shift (continuous) carry the 2.5-97.5 percentile range across replicates. The frequency is a
    sensitivity to task composition under the recorded prompt conditions, not a fresh-run probability."""
    out = leaderboard(A, W, ref_signs)
    res = {k: (summ(out[k].astype(float)) if k in ("margin_o", "shift_c", "shift_p")
               else summ_freq(out[k].astype(float))) for k in LB_KEYS}
    if "same_order_as_ref" in out:
        res["same_order_as_ref"] = summ_freq(out["same_order_as_ref"].astype(float))
    res["flip_diff_para_minus_ctrl"] = summ_freq(out["flip_p_any"].astype(float) - out["flip_c_any"].astype(float))
    return res


def run_subsets(A: dict, R: int, rng) -> dict:
    subsets = define_subsets(A)
    N = len(A["tau_c"])
    full = subsets["S0_full"]
    ref_signs = _pair_signs(leaderboard(A, full[None, :].astype(float))["M_o"])
    p0 = point(A, full)
    result = {}
    Wfull = boot_weights(full, R, rng)                      # one shared resample of the whole benchmark
    m_full = metrics(A, Wfull)
    for name, mask in subsets.items():
        blk = {"n_tasks": int(mask.sum()), "point": point(A, mask), "tests": tests(A, mask),
               "leaderboard_point": lb_point(A, mask)}
        Wb = boot_weights(mask, R, rng)
        mb = metrics(A, Wb)
        blk["bootstrap_within_subset"] = {k: summ(mb[k]) for k in ("mean_tau_c", "mean_tau_p", "gap_paired",
                                                                    "rev_diff", "n_both", "yield_both")}
        blk["leaderboard_bootstrap"] = lb_boot(A, Wb, ref_signs)
        # difference against the full benchmark on the SAME resampled tasks
        ms = metrics(A, Wfull * mask)
        blk["difference_vs_S0"] = {k: summ(ms[k] - m_full[k]) for k in ("mean_tau_c", "mean_tau_p", "gap_paired",
                                                                         "rev_diff", "yield_both")}
        # random controls: drawn without looking at any tau value or at the paraphrase effect
        if name != "S0_full":
            n_f = int(mask.sum())
            Wa = sample_weights(np.ones(N, bool), n_f, R, rng)
            ma = metrics(A, Wa)
            blk["S5a_total_count_control"] = {
                "size": n_f, **{k: summ(ma[k]) for k in CONTROL_KEYS},
                "leaderboard": lb_boot(A, Wa, ref_signs),
                "observed_percentile": {k: _percentile(ma[k], blk["point"][k]) for k in CONTROL_KEYS}}
            yb = p0["yield_both"]
            d_both = blk["point"]["n_both"] or 0
            m_size = int(round(d_both / yb)) if yb else None
            if m_size and m_size < N:
                Wi = sample_weights(np.ones(N, bool), m_size, R, rng)
                mi = metrics(A, Wi)
                blk["S5b_information_count_control"] = {
                    "size": m_size, "target_paired_defined": d_both,
                    "realised_n_both": summ(mi["n_both"]), "realised_n_tau_c": summ(mi["n_tau_c"]),
                    "realised_n_tau_p": summ(mi["n_tau_p"]),
                    **{k: summ(mi[k]) for k in CONTROL_KEYS},
                    "leaderboard": lb_boot(A, Wi, ref_signs),
                    "observed_percentile": {k: _percentile(mi[k], blk["point"][k]) for k in CONTROL_KEYS}}
            else:
                blk["S5b_information_count_control"] = {
                    "note": "matched size equals the full benchmark: the subset holds all the usable comparisons"}
        result[name] = blk
    return {"subsets": result, "ref_leaderboard_signs": ref_signs[0].tolist()}


def _percentile(dist, value) -> float | None:
    d = np.asarray(dist, float)
    d = d[~np.isnan(d)]
    return None if value is None or not len(d) else float((d <= value).mean())


def run_dial(A: dict, R: int, rng, observed_share: float) -> dict:
    N = len(A["tau_c"])
    disc = A["base_disc"]
    full = np.ones(N, bool)
    ref_signs = _pair_signs(leaderboard(A, full[None, :].astype(float))["M_o"])
    fills = {"mixed": ~disc, "ceiling_only": A["ceiling"], "floor_only": A["floor"]}
    out = {"observed_share": observed_share, "variants": {}}
    for fname, fill in fills.items():
        if fill.sum() < (1 if fname == "mixed" else MIN_FILL_POOL):
            out["variants"][fname] = {"skipped": f"fill pool has {int(fill.sum())} tasks (< {MIN_FILL_POOL})"}
            continue
        rows = {}
        for share in sorted(set(DIAL_SHARES + [round(observed_share, 4)])):
            W = dial_weights(disc, fill, share, R, rng)
            m = metrics(A, W)
            rows[f"{share:.4f}"] = {
                **{k: summ(m[k]) for k in ("n_both", "yield_both", "yield_c", "yield_p", "mean_tau_c", "mean_tau_p",
                                           "gap_paired", "se_gap_paired", "rev_diff", "undef_share")},
                "leaderboard": lb_boot(A, W, ref_signs)}
        out["variants"][fname] = rows
    return out


# ---------------------------------------------------------------------------
# Independence check: select on one half of the completions, evaluate on the other
# ---------------------------------------------------------------------------

def crossfit(run: SimpleNamespace, R: int, rng) -> dict:
    halves = (list(range(5)), list(range(5, 10)))
    per_dir = []
    for cls_h, ev_h in ((0, 1), (1, 0)):
        rows = []
        for t in run.tasks:
            def half_scores(rel, idx):
                return {m: comparable(float(np.mean([v[i] for i in idx]))) for m, v in t.raw.get(rel, {}).items()}
            ev = {rel: half_scores(rel, halves[ev_h]) for rel in t.raw}
            row = build_row(ev, t.universe, run.models, run.min_cov)
            cls = build_row({"original": half_scores("original", halves[cls_h])}, [], run.models, run.min_cov)
            for k in ("has_base", "floor", "ceiling", "base_disc", "difficulty", "spread"):
                row[k] = cls[k]               # selection indicators come from the other half only
            rows.append(row)
        A = to_arrays(rows)
        masks = {"S0_full": np.ones(len(rows), bool), "S1b_baseline_discriminating": A["base_disc"]}
        for i, g in enumerate(terciles(A["spread"], A["base_disc"]), 1):
            masks[f"S4_spread_T{i}"] = g
        per_dir.append({n: point(A, m) for n, m in masks.items()})
    out = {}
    for name in per_dir[0]:
        avg = {}
        for k in POINT_KEYS:
            vals = [d[name][k] for d in per_dir if d[name][k] is not None]
            avg[k] = float(np.mean(vals)) if vals else None
        out[name] = {"average_of_both_directions": avg, "direction_A_to_B": per_dir[0][name],
                     "direction_B_to_A": per_dir[1][name]}
    return out


# ---------------------------------------------------------------------------
# Two-stage bootstrap (tasks, then completions within each cell): secondary layer
# ---------------------------------------------------------------------------

def two_stage(run: SimpleNamespace, rows: list[dict], R: int, rng, ref_signs) -> dict:
    models, n_m = run.models, len(run.models)
    ok = [i for i, r in enumerate(rows) if r["lb_ok"]]

    def cell_arr(t, rel):
        return np.array([t.raw[rel][m] for m in models]) if all(m in t.raw.get(rel, {}) for m in models) else None
    cache = []
    for i in ok:
        t = run.tasks[i]
        fam: dict[str, list] = defaultdict(list)
        for rel in t.universe:
            arm, f = relation_arm(rel)
            if arm == "llm" and cell_arr(t, rel) is not None:
                fam[f].append(cell_arr(t, rel))
        if cell_arr(t, "original") is None or cell_arr(t, "control_resample") is None or not fam:
            continue
        cache.append((cell_arr(t, "original"), cell_arr(t, "control_resample"), list(fam.values())))
    flips = {"c": [], "p": []}
    same = []
    for _ in range(R):
        pick = rng.integers(0, len(cache), len(cache))
        acc = np.zeros((3, n_m))
        for idx in pick:
            o, c, fams = cache[idx]
            take = lambda a: a[np.arange(n_m)[:, None], rng.integers(0, 10, (n_m, 10))].mean(1)  # noqa: E731
            acc[0] += take(o)
            acc[1] += take(c)
            acc[2] += np.mean([np.mean([take(a) for a in vs], axis=0) for vs in fams], axis=0)
        M = np.round(acc / len(pick), 12)
        so, sc_, sp = (_pair_signs(M[i][None, :])[0] for i in (0, 1, 2))
        flips["c"].append(bool((so * sc_ == -1).any()))
        flips["p"].append(bool((so * sp == -1).any()))
        same.append(bool((so == ref_signs).all()))
    return {"n_tasks": len(cache), "replicates": R,
            "flip_control_any": float(np.mean(flips["c"])), "flip_paraphrase_any": float(np.mean(flips["p"])),
            "same_order_as_ref": float(np.mean(same)),
            "note": "tasks resampled, then completions within each cell; still conditional on n=10 recorded "
                    "completions per cell, so not a fresh-generation probability"}


# ---------------------------------------------------------------------------
# RQ4 re-analysis (executed tasks only)
# ---------------------------------------------------------------------------

def _rho(x, y) -> dict:
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~np.isnan(x) & ~np.isnan(y)
    if ok.sum() < 4 or len(set(x[ok])) < 2 or len(set(y[ok])) < 2:
        return {"rho": None, "p": None, "n": int(ok.sum())}
    r = spearman_rho(list(x[ok]), list(y[ok]))
    return {"rho": float(r["rho"]), "p": float(r["p_value"]), "n": int(ok.sum())}


def rq4_table(rows: list[dict], title: str) -> dict:
    """Collapse by difficulty / spread tercile and by suite size among EXECUTED tasks."""
    if not rows:
        return {"title": title, "n": 0}
    sp = np.array([r["spread"] for r in rows])
    di = np.array([r["difficulty"] for r in rows])
    su = np.array([r["suite_size"] for r in rows], float)
    nc = np.array([r["n_collapsed_levels"] for r in rows], float)
    c50 = np.array([r["collapsed_0.5"] for r in rows], float)
    c80 = np.array([r["collapsed_0.8"] for r in rows], float)
    drop = np.array([np.nan if r["tau_drop"] is None else r["tau_drop"] for r in rows])
    allm = np.ones(len(rows), bool)

    def by_group(groups, label):
        return [{label: i + 1, "n": int(g.sum()), "collapsed_0.5": float(c50[g].mean()),
                 "collapsed_0.8": float(c80[g].mean()), "mean_levels_collapsed": float(nc[g].mean())}
                for i, g in enumerate(groups) if g.sum()]
    med = float(np.median(su))
    strata = {}
    for lab, g in (("suite_size<=median", su <= med), ("suite_size>median", su > med)):
        if g.sum() >= 6:
            strata[lab] = {"n": int(g.sum()), "spearman_spread_vs_levels_collapsed": _rho(sp[g], nc[g]),
                           "spearman_difficulty_vs_levels_collapsed": _rho(di[g], nc[g])}
    return {"title": title, "n": len(rows), "median_suite_size": med,
            "spearman_spread_vs_levels_collapsed": _rho(sp, nc),
            "spearman_difficulty_vs_levels_collapsed": _rho(di, nc),
            "spearman_suite_size_vs_levels_collapsed": _rho(su, nc),
            "spearman_spread_vs_tau_drop": _rho(sp, drop),
            "by_spread_tercile": by_group(terciles(sp, allm), "spread_tercile"),
            "by_difficulty_tercile": by_group(terciles(di, allm), "difficulty_tercile (1 = hardest)"),
            "by_suite_size_stratum": strata,
            "note": "executed tasks only; Tier 2 eligibility already requires a tie-free intact ranking"}


def rq4_tier2() -> dict:
    from meta_real_eval.core.config import Config
    from meta_real_eval.rq4 import tier2
    cfg = Config.from_yaml(sc.REPO / "config" / "tier2_realclasseval.yaml")
    models, relations = cfg.model_ids(), cfg.rq2.relations
    summary = json.loads((sc.T2_POST / "rq4" / "summary" / "tier2_rq4.json").read_text())
    out = {}
    for key, label in (("mean_primary", "tier2_units_graded"), ("pass@1", "tier2_units_pass1")):
        rows = []
        for t in summary["designs"]["units"][key]["eligible_tasks"]:
            rec = json.loads((sc.T2_SCORES / "rq4" / "degrade" / t / "degradation_tier2.json").read_text())
            lv = rec["designs"]["units"]["levels"]
            lvl = {k: tier2.level_summary(v["cells"], models, relations, key) for k, v in lv.items() if not v["missing"]}
            intact = list(lvl["0.0"]["scores"]["original"].values())
            tied = {k: len(set(s["scores"]["original"].values())) <= 1 for k, s in lvl.items()}
            t0, t8 = lvl["0.0"]["mean_tau_b"], lvl.get("0.8", {}).get("mean_tau_b")
            rows.append({"label": t, "spread": max(intact) - min(intact), "difficulty": float(np.mean(intact)),
                         "suite_size": rec["eligibility"]["n_units"], "collapsed_0.5": tied.get("0.5", False),
                         "collapsed_0.8": tied.get("0.8", False),
                         "n_collapsed_levels": sum(tied[k] for k in ("0.2", "0.5", "0.8") if k in tied),
                         "tau_drop": None if t0 is None or t8 is None else t0 - t8})
        out[label] = {"rows": rows, **rq4_table(rows, f"{label}: executed tasks")}
    return out


def rq4_tier1() -> dict:
    from meta_real_eval.benchmarks import get_benchmark
    from meta_real_eval.core.config import Config
    from meta_real_eval.rq4.degradation import _assert_nodes
    cfg = Config.from_yaml(sc.REPO / "config" / "default.yaml")
    n_assert = {}
    for task in get_benchmark(cfg).load_tasks():
        tree = ast.parse(task.test_code)
        check = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "check"), None)
        n_assert[task.label] = len(_assert_nodes(check)) if check else 0
    rows = []
    for d in sorted((sc.TIER1 / "rq4" / "degrade").iterdir()):
        f = d / "degradation_analysis.json"
        if not d.is_dir() or not f.exists():
            continue
        rec = json.loads(f.read_text())
        levels = sorted(k for k in rec if k != "trend_test")
        base = (rec[levels[0]].get("pass_at_1") or {}).get("original")
        if not base or len(set(base.values())) <= 1:        # discriminating on the intact suite
            continue
        vals = list(base.values())
        tied = {k: len(set(((rec[k].get("pass_at_1") or {}).get("original") or {"x": 0}).values())) <= 1
                for k in levels[1:]}
        t0, t8 = rec[levels[0]].get("mean_tau_b"), rec[levels[-1]].get("mean_tau_b")
        rows.append({"label": d.name, "spread": max(vals) - min(vals), "difficulty": float(np.mean(vals)),
                     "suite_size": n_assert.get(d.name, 0), "collapsed_0.5": tied.get("0.5", False),
                     "collapsed_0.8": tied.get("0.8", False), "n_collapsed_levels": sum(tied.values()),
                     "tau_drop": None if t0 is None or t8 is None else t0 - t8})
    return {"tier1_assertions_pass1": {"rows": rows, **rq4_table(rows, "tier1: discriminating tasks (all executed)")}}


# ---------------------------------------------------------------------------
# Validation against the existing analysis
# ---------------------------------------------------------------------------

def validate(name: str, run: SimpleNamespace, rows: list[dict], A: dict, view: Path, ranking_file: str, ar) -> list[dict]:
    checks = []
    worst = 0.0
    for t, r in zip(run.tasks, rows):
        for rel, stored in t.stored_tau.items():
            mine = r["tau"][rel]
            if (mine is None) != (stored is None):
                worst = max(worst, 1.0)
            elif mine is not None:
                worst = max(worst, abs(mine - stored))
    checks.append({"check": f"{name}: per-relation tau_b recomputed == stored rankings", "max_abs_diff": worst,
                   "ok": worst <= 1e-12})
    subsets = define_subsets(A)
    labels = np.array([t.label for t in run.tasks])
    for sub in [s for s in ("S0_full", "S1b_baseline_discriminating", "S2_drop_floor", "S2_drop_ceiling",
                            "S4_spread_T3") if s in subsets]:
        mask = subsets[sub]
        ar.RESULTS, ar.RANKINGS = view, ranking_file
        ar.EXCLUDE.clear()
        ar.EXCLUDE.update(labels[~mask])
        got = ar.analyze_rq2()
        ar.EXCLUDE.clear()
        p = point(A, mask)
        t = tests(A, mask)
        arms = got["ranking_stability"]["by_arm"]
        pv = got["pairwise_reversal_rate"]["arm_vs_control_paired"].get("llm", {})
        pr = got["pairwise_reversal_rate"]
        diffs = [abs(arms["control"]["mean"] - t["tau_control"]["mean"]) if arms.get("control", {}).get("n") else 0.0,
                 abs(arms["llm"]["mean"] - t["tau_paraphrase"]["mean"]) if arms.get("llm", {}).get("n") else 0.0,
                 abs(arms["control"]["n"] - p["n_tau_c"]), abs(arms["llm"]["n"] - p["n_tau_p"]),
                 abs(pr["n_pair_comparisons"] - p["n_cmp"]), abs(pr["n_tied_excluded"] - p["n_tied"]),
                 abs(got["ranking_stability"]["n_degenerate_pairs"] - A["rel_undef"][mask].sum()),
                 abs(got["ranking_stability"]["n_task_relation_pairs"] - A["rel_total"][mask].sum())]
        if pv.get("n_tasks"):
            diffs += [abs(pv["n_tasks"] - p["n_rev_paired"]), abs(pv["mean_arm"] - p["rev_llm"]),
                      abs(pv["mean_control"] - p["rev_ctrl"]),
                      abs(pv["wilcoxon"]["p_value"] - t["wilcoxon_reversal_paired"]["p_value"])
                      if t["wilcoxon_reversal_paired"] and "p_value" in pv["wilcoxon"] else 0.0]
        checks.append({"check": f"{name}: subset {sub} ({int(mask.sum())} tasks) == existing analyze_rq2 (EXCLUDE route)",
                       "max_abs_diff": float(max(diffs)), "ok": max(diffs) <= 1e-9})
    full, disc, nonext = (subsets[k] for k in ("S0_full", "S1b_baseline_discriminating", "S1a_non_extreme"))
    ident = max(abs((point(A, m)[k] or 0) - (point(A, full)[k] or 0)) for m in (disc, nonext)
                for k in ("n_tau_c", "n_tau_p", "mean_tau_c", "mean_tau_p", "gap_paired", "rev_llm", "rev_ctrl",
                          "n_rev_paired"))
    checks.append({"check": f"{name}: S1 (floor/ceiling/tied tasks removed) == S0 on tau_b and reversal level",
                   "max_abs_diff": float(ident), "ok": ident <= 1e-12})
    # independent plain-Python leaderboard on the lb_ok tasks
    ok_tasks = [t for t, r in zip(run.tasks, rows) if r["lb_ok"]]
    plain = [sum(t.scores["original"][m] for t in ok_tasks) / len(ok_tasks) for m in run.models]
    mine = leaderboard(A, np.ones((1, len(rows))))["M_o"][0]
    d = float(np.max(np.abs(np.array(plain) - mine)))
    checks.append({"check": f"{name}: leaderboard aggregate == plain-Python mean of stored scores", "max_abs_diff": d,
                   "ok": d <= 1e-9})
    return checks


def validate_dial(name: str, res: dict) -> list[dict]:
    """At the observed discriminating share the dial must reproduce S0 *approximately across
    resamples* (S0 inside the central 95% of the replicates), not exactly in every replicate."""
    s0 = res["subsets"]["S0_full"]["point"]
    row = res["dial"]["variants"]["mixed"][f"{res['dial']['observed_share']:.4f}"]
    checks = []
    for k in ("yield_both", "mean_tau_c", "mean_tau_p", "gap_paired", "rev_diff"):
        lo, hi, v = row[k]["lo"], row[k]["hi"], s0[k]
        checks.append({"check": f"{name}: dial at the observed share brackets S0 on {k} (S0 {v:.4f}, "
                                f"replicates [{lo:.4f}, {hi:.4f}])", "max_abs_diff": 0.0 if lo <= v <= hi else 1.0,
                       "ok": lo <= v <= hi})
    return checks


def cross_tier(A1: dict, A2: dict, R: int, rng) -> dict:
    """Tier 1 against Tier 2 at matched scoring (both pass@1), matched amount of usable ranking
    information, and matched saturation share. Panel, benchmark and corpus differ: descriptive."""
    N1, N2 = len(A1["tau_c"]), len(A2["tau_c"])
    one1, one2 = np.ones(N1, bool), np.ones(N2, bool)
    p1, p2 = point(A1, one1), point(A2, one2)
    ref2 = _pair_signs(leaderboard(A2, one2[None, :].astype(float))["M_o"])
    ref1 = _pair_signs(leaderboard(A1, one1[None, :].astype(float))["M_o"])
    keys = ["n_both", "yield_both", "mean_tau_c", "mean_tau_p", "gap_paired", "se_gap_paired", "rev_diff"]
    out = {"tier1_observed": {k: p1[k] for k in keys}, "tier2_pass1_observed": {k: p2[k] for k in keys}}
    m_size = int(round(p1["n_both"] / p2["yield_both"]))
    mi = metrics(A2, sample_weights(one2, m_size, R, rng))
    Wi = sample_weights(one2, m_size, R, rng)
    out["tier2_pass1_information_matched"] = {
        "size": m_size, "target_paired_defined": p1["n_both"], **{k: summ(mi[k]) for k in keys},
        "leaderboard": lb_boot(A2, Wi, ref2)}
    s1, s2 = float(A1["base_disc"].mean()), float(A2["base_disc"].mean())
    W2 = dial_weights(A2["base_disc"], ~A2["base_disc"], s1, R, rng)
    W1 = dial_weights(A1["base_disc"], ~A1["base_disc"], s2, R, rng)
    m2, m1 = metrics(A2, W2), metrics(A1, W1)
    out["saturation_matched"] = {
        "tier1_share": s1, "tier2_pass1_share": s2,
        "tier2_pass1_at_tier1_share": {**{k: summ(m2[k]) for k in keys}, "leaderboard": lb_boot(A2, W2, ref2)},
        "tier1_at_tier2_pass1_share": {**{k: summ(m1[k]) for k in keys}, "leaderboard": lb_boot(A1, W1, ref1)}}
    out["note"] = ("Different benchmark, corpus, model panel (qwen3-next vs qwen38) and test oracle; Tier 1 has no graded "
                   "score. Read as descriptive context, never as a causal comparison.")
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_task_table(path: Path, run: SimpleNamespace, rows: list[dict]) -> None:
    import csv
    cols = ["label", "has_base", "floor", "ceiling", "non_extreme", "base_disc", "difficulty", "spread", "covered",
            "tau_c", "tau_p", "tau_t", "rev_c", "rev_p", "n_cmp", "n_tied", "lb_ok"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for t, r in zip(run.tasks, rows):
            ne = r["has_base"] and not r["floor"] and not r["ceiling"]
            w.writerow([t.label] + [ne if c == "non_extreme" else (t.label if c == "label" else r[c]) for c in cols[1:]])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicates", type=int, default=1000)
    ap.add_argument("--two-stage-replicates", type=int, default=200)
    ap.add_argument("--smoke", action="store_true", help="tiny replicate counts, for a quick check")
    args = ap.parse_args()
    R = 40 if args.smoke else args.replicates
    R2 = 10 if args.smoke else args.two_stage_replicates

    views = {"tier1": sc.VIEWS / "tier1", "tier2": sc.VIEWS / "tier2"}
    if not (views["tier1"].exists() and views["tier2"].exists()):
        raise SystemExit("views missing: run scripts/saturation_baseline.py first (Phase 1)")
    ar = sc.load_analyze_results()
    all_checks, results, arrays = [], {}, {}
    for i, (name, (tier, key, ranking)) in enumerate(RUNS.items()):
        print(f"[{name}] loading ...", flush=True)
        run = load_run(views[tier], ranking, key)
        rows = [build_row(t.scores, t.universe, run.models, run.min_cov) for t in run.tasks]
        A = to_arrays(rows)
        rng = np.random.default_rng([SEED, i])
        res = run_subsets(A, R, rng)
        share = float(A["base_disc"].mean())
        res["dial"] = run_dial(A, R, rng, share)
        res["crossfit"] = crossfit(run, R, rng)
        ref = np.array(res["ref_leaderboard_signs"])
        res["two_stage_leaderboard_S0"] = two_stage(run, rows, R2, rng, ref)
        res["meta"] = {"run": name, "tier": tier, "score": key, "models": run.models, "n_tasks": len(rows),
                       "replicates": R, "seed": SEED, "base_disc_share": share,
                       "counts": {"non_extreme": int(A["non_extreme"].sum()), "baseline_discriminating": int(A["base_disc"].sum()),
                                  "floor": int(A["floor"].sum()), "ceiling": int(A["ceiling"].sum()),
                                  "tau_defined_control": int((~np.isnan(A["tau_c"])).sum()),
                                  "tau_defined_paraphrase": int((~np.isnan(A["tau_p"])).sum())}}
        arrays[name] = A
        if not args.smoke:
            res["validation"] = validate(name, run, rows, A, views[tier], ranking, ar) + validate_dial(name, res)
            all_checks += res["validation"]
            for c in res["validation"]:
                print(("OK   " if c["ok"] else "FAIL ") + c["check"], f"(max diff {c['max_abs_diff']:.1e})")
        write_task_table(sc.OUT / name / "task_table.csv", run, rows)
        sc.dump(sc.OUT / name / "simulation.json", res)
        results[name] = res
    sc.dump(sc.OUT / "cross_tier.json",
            cross_tier(arrays["tier1_pass1"], arrays["tier2_pass1"], R, np.random.default_rng([SEED, 99])))
    rq4 = {**rq4_tier2(), **rq4_tier1()}
    sc.dump(sc.OUT / "rq4_reanalysis.json", rq4)
    sc.dump(sc.OUT / "validation.json", all_checks)
    bad = [c for c in all_checks if not c["ok"]]
    print(f"\n{len(all_checks) - len(bad)}/{len(all_checks)} validation checks OK")
    return int(bool(bad))


if __name__ == "__main__":
    sys.exit(main())
