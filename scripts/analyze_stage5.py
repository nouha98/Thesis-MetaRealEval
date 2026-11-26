"""Stage 5: P vs P∧H on the stored RQ2 completions of the evaluation cohort (plan rev. 9.3; decisions 10.5).

    python scripts/analyze_stage5.py --grading results_tier2_ext/stage5/grading.json \
        --audit results_tier2_ext/audit_h/round1/audit_reserved.json --out results_tier2_ext/stage5

Cohort: the tasks of the frozen H v1 bundle minus the 20 audit-reserved tasks (development tasks are not in the
bundle). Reported separately (plan, Stage 5): P success; H failure; P∧H success; P-pass/H-fail with its failure
kinds (exception-only and timeout-only as sensitivities); grading coverage; the number of tasks with >= 1
P-passing completion (P∧H can differ from P only there, decisions 10.3); per-model pass@1 under P and P∧H with
task-cluster bootstrap intervals; the leaderboard order and per-task Kendall tau_b between the model scores under
P and under P∧H. Primary relation: `original`; all relations pooled as a sensitivity.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import kendalltau, rankdata

B, SEED = 2000, 20261126


def completions(grading: dict, cohort: set) -> list[dict]:
    """One record per stored completion of a cohort task."""
    out = []
    for t in grading["tasks"]:
        if t["task"] not in cohort:
            continue
        for r in t["rows"]:
            timeout_only = not r["h_pass"] and set(r.get("h_outcomes", {}).values()) == {"timeout"}
            for m in r["members"]:
                p = m["stored_p_pass"]
                out.append({"task": t["task"], "split": "csn" if "_csn_" in t["task"] else "post",
                            "relation": m["relation"], "model": m["model"], "p": p, "h": r["h_pass"],
                            "ph": None if p is None else (p and r["h_pass"]), "group": r["group_id"],
                            "kinds": r.get("failure_kinds", []) if p and not r["h_pass"] else [],
                            "timeout_only": timeout_only, "h_error": "error" in r.get("h_outcomes", {}).values()})
    return out


def rate(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def per_task_model(recs: list[dict], key: str) -> dict:
    """{(task, model): pass rate under `key`} (a task's pass@1 for that model)."""
    by = defaultdict(list)
    for r in recs:
        by[(r["task"], r["model"])].append(r[key])
    return {k: rate(v) for k, v in by.items()}


def boot_diff(pt: dict, ph: dict, model: str) -> dict:
    """Mean over tasks of P - P∧H pass@1 for one model, with a task-cluster bootstrap interval."""
    tasks = sorted(t for (t, m) in pt if m == model and pt[(t, m)] is not None and ph.get((t, m)) is not None)
    if not tasks:
        return {"tasks": 0}
    d = {t: pt[(t, model)] - ph[(t, model)] for t in tasks}
    rng, vals = random.Random(SEED), []
    for _ in range(B):
        s = [d[rng.choice(tasks)] for _ in tasks]
        vals.append(sum(s) / len(s))
    vals.sort()
    return {"tasks": len(tasks), "p": sum(pt[(t, model)] for t in tasks) / len(tasks),
            "p_and_h": sum(ph[(t, model)] for t in tasks) / len(tasks), "diff": sum(d.values()) / len(tasks),
            "diff_ci95": [vals[int(0.025 * B)], vals[int(0.975 * B) - 1]]}


def leaderboard(pt: dict, ph: dict, models: list[str]) -> dict:
    tasks = sorted({t for t, _ in pt})
    mean = lambda tab, m: rate([tab.get((t, m)) for t in tasks])  # noqa: E731
    def ranks(tab):                                  # 1 = best; tied models share the rank (method "min")
        r = rankdata([-(mean(tab, m) or 0) for m in models], method="min")
        return {m: int(x) for m, x in zip(models, r)}
    rank_p, rank_ph = ranks(pt), ranks(ph)
    taus, changed, undefined, collapsed, tied_p, broken = [], 0, 0, 0, 0, 0
    for t in tasks:
        a = [pt.get((t, m)) for m in models]
        b = [ph.get((t, m)) for m in models]
        if None in a or None in b:
            undefined += 1
            continue
        changed += a != b
        if len(set(a)) >= 2 and len(set(b)) < 2:
            collapsed += 1                       # H tied models that P separated: counted, never dropped silently
            continue
        if len(set(a)) < 2:
            tied_p += 1                          # no order under P (tau_b undefined); broken by H if b varies
            broken += len(set(b)) >= 2
            continue
        taus.append(float(kendalltau(a, b).statistic))
    return {"rank_p": rank_p, "rank_p_and_h": rank_ph, "order_changed": rank_p != rank_ph,
            "mean_score_p": {m: mean(pt, m) for m in models}, "mean_score_p_and_h": {m: mean(ph, m) for m in models},
            "tasks_with_changed_scores": changed, "tau_b_tasks": len(taus), "tau_b_missing_scores": undefined,
            "ranking_collapsed_to_tie": collapsed, "tied_under_p": tied_p, "tie_broken_by_h": broken,
            "tau_b_mean": sum(taus) / len(taus) if taus else None, "tau_b_below_1": sum(x < 1 for x in taus)}


def summarise(recs: list[dict]) -> dict:
    c = Counter()
    for r in recs:
        c["completions"] += 1
        c["p_ungradable"] += r["p"] is None
        c["p_pass"] += bool(r["p"])
        c["h_fail"] += not r["h"]
        c["p_and_h"] += bool(r["ph"])
        c["p_pass_h_fail"] += bool(r["p"]) and not r["h"]
        c["p_pass_h_fail_timeout_only"] += bool(r["p"]) and r["timeout_only"]
        c["p_pass_h_fail_exception_only"] += set(r["kinds"]) == {"unexpected_exception"}
        c["h_timeout_only"] += r["timeout_only"]
        c["h_error"] += r["h_error"]
        for k in r["kinds"]:
            c[f"p_pass_h_fail:{k}"] += 1
    n = c["completions"] - c["p_ungradable"]
    return {**dict(c), "p_rate": c["p_pass"] / n if n else None, "p_and_h_rate": c["p_and_h"] / n if n else None,
            "h_fail_rate": c["h_fail"] / c["completions"] if c["completions"] else None,
            "p_pass_h_fail_share_of_p_pass": c["p_pass_h_fail"] / c["p_pass"] if c["p_pass"] else None}


def analyse(grading: dict, cohort: set) -> dict:
    recs = completions(grading, cohort)
    models = sorted({r["model"] for r in recs})
    res = {"cohort_tasks": len(cohort), "graded_tasks": len({r["task"] for r in recs}),
           "tasks_with_p_pass": len({r["task"] for r in recs if r["p"]}),
           "tasks_with_p_pass_original": len({r["task"] for r in recs if r["p"] and r["relation"] == "original"}),
           "tasks_with_p_pass_h_fail": sorted({r["task"] for r in recs if r["p"] and not r["h"]}),
           "all": summarise(recs), "by_split": {s: summarise([r for r in recs if r["split"] == s]) for s in ("csn", "post")},
           "by_model": {m: summarise([r for r in recs if r["model"] == m]) for m in models}}
    for scope, sel in (("original", [r for r in recs if r["relation"] == "original"]), ("all_relations", recs)):
        pt, ph = per_task_model(sel, "p"), per_task_model(sel, "ph")
        res[f"pass_at_1_{scope}"] = {m: boot_diff(pt, ph, m) for m in models}
        res[f"leaderboard_{scope}"] = leaderboard(pt, ph, models)
    return res


def report_md(res: dict) -> str:
    a = res["all"]
    L = ["# Stage 5: P vs P∧H on the evaluation cohort", "",
         f"Cohort {res['cohort_tasks']} tasks (graded {res['graded_tasks']}); tasks with >= 1 P-passing completion: "
         f"{res['tasks_with_p_pass']} (original relation: {res['tasks_with_p_pass_original']}). P∧H can differ from P "
         "only on those tasks.", "",
         "| | completions | P pass | P∧H pass | P-pass/H-fail | H fail | P ungradable | H timeout-only | H error |",
         "|---|---|---|---|---|---|---|---|---|"]
    for name, s in [("all", a)] + list(res["by_split"].items()) + list(res["by_model"].items()):
        L.append(f"| {name} | {s.get('completions', 0)} | {s.get('p_pass', 0)} | {s.get('p_and_h', 0)} | "
                 f"{s.get('p_pass_h_fail', 0)} | {s.get('h_fail', 0)} | {s.get('p_ungradable', 0)} | "
                 f"{s.get('h_timeout_only', 0)} | {s.get('h_error', 0)} |")
    kinds = {k: v for k, v in a.items() if k.startswith("p_pass_h_fail")}
    L += ["", f"P-pass/H-fail breakdown: `{json.dumps(kinds)}`; tasks: {res['tasks_with_p_pass_h_fail']}", ""]
    for scope in ("original", "all_relations"):
        L += [f"## pass@1 and leaderboard ({scope})", "", "| model | tasks | P | P∧H | P − P∧H | 95% CI |", "|---|---|---|---|---|---|"]
        for m, d in res[f"pass_at_1_{scope}"].items():
            if d.get("tasks"):
                L.append(f"| {m} | {d['tasks']} | {d['p']:.3f} | {d['p_and_h']:.3f} | {d['diff']:.4f} | "
                         f"[{d['diff_ci95'][0]:.4f}, {d['diff_ci95'][1]:.4f}] |")
        lb = res[f"leaderboard_{scope}"]
        L += ["", f"Ranks under P: {lb['rank_p']}; under P∧H: {lb['rank_p_and_h']} (changed: {lb['order_changed']}). "
              f"Tasks with changed model scores: {lb['tasks_with_changed_scores']}; per-task tau_b defined on "
              f"{lb['tau_b_tasks']} tasks, mean {lb['tau_b_mean']}, below 1 on {lb['tau_b_below_1']}; ranking collapsed "
              f"to a tie under P∧H on {lb['ranking_collapsed_to_tie']}; tied under P on {lb['tied_under_p']} (tie "
              f"broken by H on {lb['tie_broken_by_h']}); missing scores {lb['tau_b_missing_scores']}.", ""]
    return "\n".join(L) + "\n"


def cohort_from_freeze(grading: dict, audit: set, record_path: Path, expect: int) -> set:
    """The cohort comes from the committed freeze record, not from whatever the grading file contains."""
    import freeze_h
    rec = freeze_h.verify(Path(grading["hidden"]), record_path)      # the graded bundle is the frozen H v1
    if grading.get("frozen_h_sha256") not in (None, rec["global_sha256"]):
        raise SystemExit("ERROR: the grading names another frozen H than the committed record")
    frozen, graded = set(rec["tasks"]), {t["task"] for t in grading["tasks"]}
    if graded != frozen:
        raise SystemExit(f"ERROR: graded tasks differ from the frozen H: missing {sorted(frozen - graded)[:5]}, "
                         f"extra {sorted(graded - frozen)[:5]}")
    if not audit <= frozen:
        raise SystemExit("ERROR: audit-reserved tasks outside the frozen H")
    cohort = frozen - audit
    if len(cohort) != expect:
        raise SystemExit(f"ERROR: cohort has {len(cohort)} tasks, expected {expect}")
    return cohort


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")         # the report prints "P∧H" on any console
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import freeze_h
    from meta_real_eval.core.provenance import write_run_manifest
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--grading", type=Path, required=True)
    ap.add_argument("--audit", type=Path, required=True, help="audit_reserved.json (excluded from the cohort)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--record", type=Path, default=freeze_h.RECORD, help="committed freeze record of H v1")
    ap.add_argument("--expect-cohort", type=int, default=55)
    args = ap.parse_args(argv)
    grading = json.loads(args.grading.read_text(encoding="utf-8"))
    if grading.get("isolation") != "per_test_process":
        raise SystemExit("ERROR: the grading was not produced by the isolated runner (decisions 10.5)")
    audit = set(json.loads(args.audit.read_text(encoding="utf-8"))["tasks"])
    cohort = cohort_from_freeze(grading, audit, args.record, args.expect_cohort)
    res = analyse(grading, cohort)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "stage5_summary.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (args.out / "stage5_report.md").write_text(report_md(res), encoding="utf-8")
    write_run_manifest(args.out, stage="stage5_analysis", inputs={"grading": args.grading, "audit": args.audit,
                                                                  "freeze_record": args.record},
                       seeds={"bootstrap": SEED}, settings={"bootstrap_replicates": B, "cohort_tasks": len(cohort)})
    print(report_md(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
