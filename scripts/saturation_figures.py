"""Figures and markdown tables for the saturation analysis, generated from results_saturation/*.json
(no recomputation). Writes results_saturation/figures/*.png and results_saturation/tables.md."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saturation_common as sc  # noqa: E402

RUNS = {"tier1_pass1": "Tier 1, pass@1", "tier2_graded": "Tier 2, graded", "tier2_pass1": "Tier 2, pass@1"}
COL = {"para": "#c0392b", "ctrl": "#1f77b4", "gap": "#444444"}


def load(name):
    return json.loads((sc.OUT / name / "simulation.json").read_text())


def f(v, d=3):
    return "n/a" if v is None else f"{v:.{d}f}"


def fp(v):
    """A p-value to two significant digits (so 1.4e-5 never prints as 0.0000)."""
    return "n/a" if v is None else f"{v:.2g}"


def band(ax, xs, rows, key, color, label, sub=None):
    get = (lambda r: r[key]) if sub is None else (lambda r: r["leaderboard"][key])
    m = [get(r)["mean"] for r in rows]
    ax.plot(xs, m, color=color, label=label, lw=1.8)
    ax.fill_between(xs, [get(r)["lo"] for r in rows], [get(r)["hi"] for r in rows], color=color, alpha=0.15, lw=0)


def fig_dial(sims, out):
    fig, axes = plt.subplots(3, 3, figsize=(12, 8.5), sharex=True)
    for j, (name, title) in enumerate(RUNS.items()):
        d = sims[name]["dial"]
        rows = d["variants"]["mixed"]
        shares = sorted(rows, key=float)
        xs = [float(s) for s in shares]
        rr = [rows[s] for s in shares]
        ax = axes[0, j]
        ax.plot(xs, [r["yield_both"]["mean"] for r in rr], color="#2c3e50", lw=1.8, label="share of tasks with a usable comparison")
        ax2 = ax.twinx()
        ax2.plot(xs, [r["se_gap_paired"]["mean"] for r in rr], color="#8e44ad", ls="--", lw=1.5, label="SE of the gap")
        ax.set_title(title)
        ax.set_ylabel("information yield" if j == 0 else "")
        ax2.set_ylabel("SE of paired gap" if j == 2 else "")
        ax.set_ylim(0, 1)
        ax = axes[1, j]
        band(ax, xs, rr, "gap_paired", COL["gap"], "control - paraphrase")
        band(ax, xs, rr, "mean_tau_c", COL["ctrl"], "tau_b control")
        band(ax, xs, rr, "mean_tau_p", COL["para"], "tau_b paraphrase")
        ax.set_ylabel("conditional stability" if j == 0 else "")
        ax = axes[2, j]
        band(ax, xs, rr, "flip_c_any", COL["ctrl"], "control", sub=True)
        band(ax, xs, rr, "flip_p_any", COL["para"], "paraphrase", sub=True)
        ax.set_ylabel("leaderboard order flipped" if j == 0 else "")
        ax.set_xlabel("share of tasks that can distinguish the models")
        for a in axes[:, j]:
            a.axvline(d["observed_share"], color="grey", ls=":", lw=1)
            a.grid(alpha=0.25)
        if j == 0:
            axes[1, 0].legend(fontsize=7, loc="lower left")
            axes[2, 0].legend(fontsize=7, loc="upper left")
    fig.suptitle("Saturation dial: resampled benchmarks at a fixed discriminating share (dotted: observed share).\n"
                 "Conditional tau_b is flat by construction; yield, precision and leaderboard behaviour move.", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def fig_terciles(sims, out):
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.5))
    for j, (name, title) in enumerate(RUNS.items()):
        s = sims[name]
        for i, kind in enumerate(("spread", "difficulty")):
            ax = axes[i, j]
            xs = [1, 2, 3]
            names = [f"S4_{kind}_T{t}" for t in xs]
            gap = [s["subsets"][n]["point"]["gap_paired"] for n in names]
            lo = [s["subsets"][n]["bootstrap_within_subset"]["gap_paired"]["lo"] for n in names]
            hi = [s["subsets"][n]["bootstrap_within_subset"]["gap_paired"]["hi"] for n in names]
            ax.errorbar([x - 0.06 for x in xs], gap, yerr=[[g - l for g, l in zip(gap, lo)], [h - g for g, h in zip(gap, hi)]],
                        fmt="o", color="#2c3e50", capsize=3, label="all completions")
            if kind == "spread":
                xf = [s["crossfit"][n]["average_of_both_directions"]["gap_paired"] for n in names]
                ax.plot([x + 0.06 for x in xs], xf, "s", color="#e67e22", label="independent halves")
            ax.axhline(s["subsets"]["S0_full"]["point"]["gap_paired"], color="grey", ls=":", lw=1)
            ax.axhline(0, color="black", lw=0.6)
            ax.set_xticks(xs)
            ax.set_xticklabels(["low", "mid", "high"] if kind == "spread" else ["hardest", "mid", "easiest"])
            ax.set_title(f"{title}: by {kind} tercile", fontsize=9)
            ax.set_ylabel("tau_b gap (control - paraphrase)" if j == 0 else "")
            ax.grid(alpha=0.25)
            if i == 0 and j == 0:
                ax.legend(fontsize=7)
    fig.suptitle("Paraphrase-specific instability (gap) within tasks that can distinguish the models "
                 "(bars: 95% bootstrap interval within the tercile; dotted: whole benchmark)", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def fig_leaderboard(sims, out):
    names = ["S0_full", "S1b_baseline_discriminating", "S2_drop_floor", "S2_drop_ceiling", "S4_spread_T1",
             "S4_spread_T2", "S4_spread_T3"]
    labels = ["full", "discriminating", "drop floor", "drop ceiling", "spread low", "spread mid", "spread high"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    for ax, (name, title) in zip(axes, RUNS.items()):
        s = sims[name]["subsets"]
        xs = range(len(names))
        c = [s[n]["leaderboard_bootstrap"]["flip_c_any"]["mean"] for n in names]
        p = [s[n]["leaderboard_bootstrap"]["flip_p_any"]["mean"] for n in names]
        ax.bar([x - 0.2 for x in xs], c, 0.4, color=COL["ctrl"], label="control (re-sample)")
        ax.bar([x + 0.2 for x in xs], p, 0.4, color=COL["para"], label="paraphrase")
        ax.set_xticks(list(xs))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("share of task resamples with\na reversed leaderboard pair")
    axes[0].legend(fontsize=7)
    fig.suptitle("Leaderboard-level sensitivity to task composition under the recorded prompt conditions "
                 "(not a fresh-run probability)", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def fig_rq4(rq4, out):
    sets = {"tier1_assertions_pass1": "Tier 1, pass@1 (34 tasks)", "tier2_units_graded": "Tier 2, graded (84)",
            "tier2_units_pass1": "Tier 2, pass@1 (37)"}
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for k, (key, label) in enumerate(sets.items()):
        t = rq4[key]["by_spread_tercile"]
        ax.plot([1, 2, 3], [100 * g["collapsed_0.8"] for g in t], marker="o", label=f"{label}, rho={rq4[key]['spearman_spread_vs_levels_collapsed']['rho']:.2f}")
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["low spread", "mid", "high spread"])
    ax.set_ylabel("% of executed tasks whose ranking\ncollapsed into ties at 80% removal")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def tables(sims, rq4, cross) -> str:
    L = ["# Saturation analysis: tables (generated; do not edit)", ""]
    L += ["## A. Task classification and usable comparisons", "",
          "| Run | Tasks | floor | ceiling | non-extreme | baseline-discriminating | tau defined: control | paraphrase | both |",
          "|---|---|---|---|---|---|---|---|---|"]
    for n, t in RUNS.items():
        m, p = sims[n]["meta"], sims[n]["subsets"]["S0_full"]["point"]
        c = m["counts"]
        L.append(f"| {t} | {m['n_tasks']} | {c['floor']} | {c['ceiling']} | {c['non_extreme']} | {c['baseline_discriminating']} | "
                 f"{c['tau_defined_control']} | {c['tau_defined_paraphrase']} | {int(p['n_both'])} |")
    for n, t in RUNS.items():
        L += ["", f"## B. Subsets, {t}", "",
              "| Subset | Tasks | usable (both arms) | tau_b control | tau_b paraphrase | gap (paired) | SE | reversal para - ctrl | Wilcoxon p | flip ctrl | flip para | margin |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for sname, b in sims[n]["subsets"].items():
            p = b["point"]
            w = (b["tests"]["wilcoxon_reversal_paired"] or {}).get("p_value")
            lb = b["leaderboard_bootstrap"]
            L.append(f"| {sname} | {int(p['n_tasks'])} | {int(p['n_both'])} | {f(p['mean_tau_c'])} | {f(p['mean_tau_p'])} | "
                     f"{f(p['gap_paired'])} | {f(p['se_gap_paired'])} | {f(p['rev_diff'])} | {fp(w)} | "
                     f"{f(lb['flip_c_any']['mean'], 2)} | {f(lb['flip_p_any']['mean'], 2)} | {f(lb['margin_o']['mean'], 4)} |")
    for n, t in RUNS.items():
        L += ["", f"## C. Random controls, {t} (gap = tau_b control - paraphrase)", "",
              "| Subset | control | size | usable (realised) | observed gap | control gap [95%] | observed percentile |", "|---|---|---|---|---|---|---|"]
        for sname in ("S4_spread_T1", "S4_spread_T3", "S4_difficulty_T1", "S4_difficulty_T3", "S2_drop_ceiling", "S2_drop_floor"):
            b = sims[n]["subsets"].get(sname)
            if not b:
                continue
            for tag, lab in (("S5a_total_count_control", "S5a total count"), ("S5b_information_count_control", "S5b information count")):
                c = b[tag]
                if "size" not in c:
                    L.append(f"| {sname} | {lab} | - | - | - | - | {c['note']} |")
                    continue
                g = c["gap_paired"]
                L.append(f"| {sname} | {lab} | {c['size']} | {f(c['n_both']['mean'], 1)} | {f(b['point']['gap_paired'])} | "
                         f"{f(g['mean'])} [{f(g['lo'])}, {f(g['hi'])}] | {f(c['observed_percentile']['gap_paired'], 2)} |")
    for n, t in RUNS.items():
        d = sims[n]["dial"]
        L += ["", f"## D. Saturation dial, {t} (observed share {d['observed_share']:.3f})", "",
              "| Discriminating share | usable share | tau_b control | tau_b paraphrase | gap [95%] | SE | flip ctrl | flip para | same order as full | margin |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for s, r in d["variants"]["mixed"].items():
            lb = r["leaderboard"]
            L.append(f"| {float(s):.2f} | {f(r['yield_both']['mean'])} | {f(r['mean_tau_c']['mean'])} | {f(r['mean_tau_p']['mean'])} | "
                     f"{f(r['gap_paired']['mean'])} [{f(r['gap_paired']['lo'])}, {f(r['gap_paired']['hi'])}] | {f(r['se_gap_paired']['mean'])} | "
                     f"{f(lb['flip_c_any']['mean'], 2)} | {f(lb['flip_p_any']['mean'], 2)} | {f(lb['same_order_as_ref']['mean'], 2)} | {f(lb['margin_o']['mean'], 4)} |")
        for fn, v in d["variants"].items():
            if "skipped" in v:
                L.append(f"\n*{fn} fill: {v['skipped']}*")
        ts = sims[n]["two_stage_leaderboard_S0"]
        L.append(f"\nTwo-stage bootstrap (tasks then completions, S0, {ts['replicates']} replicates): flip control {f(ts['flip_control_any'], 2)}, "
                 f"flip paraphrase {f(ts['flip_paraphrase_any'], 2)}, same order as full {f(ts['same_order_as_ref'], 2)}.")
    for n, t in RUNS.items():
        L += ["", f"## E. Independent halves vs all completions, {t}", "",
              "| Subset | usable | tau_b ctrl | tau_b para | gap | reversal diff | usable (halves) | gap (halves) | reversal diff (halves) |", "|---|---|---|---|---|---|---|---|---|"]
        for sname, v in sims[n]["crossfit"].items():
            a, p = v["average_of_both_directions"], sims[n]["subsets"][sname]["point"]
            L.append(f"| {sname} | {int(p['n_both'])} | {f(p['mean_tau_c'])} | {f(p['mean_tau_p'])} | {f(p['gap_paired'])} | {f(p['rev_diff'])} | "
                     f"{f(a['n_both'], 1)} | {f(a['gap_paired'])} | {f(a['rev_diff'])} |")
    L += ["", "## F. RQ4: collapse and score spread (executed tasks only)", "",
          "| Set | Tasks | rho(spread, levels collapsed) | p | rho(difficulty) | p | rho(suite size) | p |", "|---|---|---|---|---|---|---|---|"]
    for k, v in rq4.items():
        s, d, z = (v[x] for x in ("spearman_spread_vs_levels_collapsed", "spearman_difficulty_vs_levels_collapsed", "spearman_suite_size_vs_levels_collapsed"))
        L.append(f"| {k} | {v['n']} | {f(s['rho'])} | {f(s['p'])} | {f(d['rho'])} | {f(d['p'])} | {f(z['rho'])} | {f(z['p'])} |")
    for k, v in rq4.items():
        L += ["", f"**{k}: collapse by spread tercile (low to high)**", "", "| Tercile | Tasks | collapsed at 50% | collapsed at 80% | mean levels collapsed |", "|---|---|---|---|---|"]
        for g in v["by_spread_tercile"]:
            L.append(f"| {g['spread_tercile']} | {g['n']} | {f(g['collapsed_0.5'], 2)} | {f(g['collapsed_0.8'], 2)} | {f(g['mean_levels_collapsed'], 2)} |")
        for lab, s in v["by_suite_size_stratum"].items():
            r = s["spearman_spread_vs_levels_collapsed"]
            L.append(f"\n{lab} (n={s['n']}): rho(spread, levels collapsed) = {f(r['rho'])}, p = {f(r['p'])}")
    o, m, s = cross["tier1_observed"], cross["tier2_pass1_information_matched"], cross["saturation_matched"]
    L += ["", "## G. Cross-tier (pass@1 for both; descriptive)", "",
          "| | usable | tau_b control | tau_b paraphrase | gap | reversal diff |", "|---|---|---|---|---|---|",
          f"| Tier 1 observed | {int(o['n_both'])} | {f(o['mean_tau_c'])} | {f(o['mean_tau_p'])} | {f(o['gap_paired'])} | {f(o['rev_diff'])} |"]
    t = cross["tier2_pass1_observed"]
    L.append(f"| Tier 2 pass@1 observed | {int(t['n_both'])} | {f(t['mean_tau_c'])} | {f(t['mean_tau_p'])} | {f(t['gap_paired'])} | {f(t['rev_diff'])} |")
    L.append(f"| Tier 2 pass@1, information matched to Tier 1 ({m['size']} tasks) | {f(m['n_both']['mean'], 1)} | {f(m['mean_tau_c']['mean'])} | "
             f"{f(m['mean_tau_p']['mean'])} | {f(m['gap_paired']['mean'])} [{f(m['gap_paired']['lo'])}, {f(m['gap_paired']['hi'])}] | {f(m['rev_diff']['mean'])} |")
    for k, lab in (("tier2_pass1_at_tier1_share", "Tier 2 pass@1 at Tier 1's share"), ("tier1_at_tier2_pass1_share", "Tier 1 at Tier 2 pass@1's share")):
        v = s[k]
        L.append(f"| {lab} | {f(v['n_both']['mean'], 1)} | {f(v['mean_tau_c']['mean'])} | {f(v['mean_tau_p']['mean'])} | "
                 f"{f(v['gap_paired']['mean'])} [{f(v['gap_paired']['lo'])}, {f(v['gap_paired']['hi'])}] | {f(v['rev_diff']['mean'])} |")
    L += ["", cross["note"], ""]
    return "\n".join(L)


def main() -> None:
    sims = {n: load(n) for n in RUNS}
    rq4 = json.loads((sc.OUT / "rq4_reanalysis.json").read_text())
    cross = json.loads((sc.OUT / "cross_tier.json").read_text())
    fig_dir = sc.OUT / "figures"
    fig_dir.mkdir(exist_ok=True)
    fig_dial(sims, fig_dir / "fig1_saturation_dial.png")
    fig_terciles(sims, fig_dir / "fig2_gap_by_tercile.png")
    fig_leaderboard(sims, fig_dir / "fig3_leaderboard_by_subset.png")
    fig_rq4(rq4, fig_dir / "fig4_rq4_collapse_by_spread.png")
    (sc.OUT / "tables.md").write_text(tables(sims, rq4, cross), encoding="utf-8")
    print("figures:", sorted(p.name for p in fig_dir.glob("*.png")), "tables:", sc.OUT / "tables.md")


if __name__ == "__main__":
    main()
