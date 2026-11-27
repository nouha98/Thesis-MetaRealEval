"""RQ3 with H, task level (plan rev. 9.3, Stage 5; frozen in config/extensions_protocol/rq3_population_v1.json).

    python scripts/analyze_rq3_h.py --grading results_tier2_ext/stage5/grading.json \
        --audit results_tier2_ext/audit_h/round1/audit_reserved.json --out results_tier2_ext/stage5/rq3_h

Descriptive (n <= 41). Unit: the task. Score: the stored RQ3 ``pairwise_disagreement_rate``. Population: the
held-out half of the frozen tau_div split, minus the audit-reserved tasks, H-ready only (= the Stage 5 cohort).

RQ3-scored solutions are rebuilt by RQ3's own rule (``rq3.divergence._pick_best_completion`` with RQ2's stored
pass flags): per (selected relation, model), the first P-passing completion, else the first completion.
  * primary label:   >= 1 RQ3-scored solution passes P and fails H (operational disagreement, D7);
  * secondary label: >= 1 RQ3-scored solution fails P and H combined;
  * sensitivity:     label-independent representatives (the first completion of every cell).
AUC on the continuous score; sensitivity / specificity / J only at the frozen tau_div (rule ``score >= tau``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

POP = ec.PROTOCOL_DIR / "rq3_population_v1.json"


def outcomes(grading: dict) -> dict:
    """{task: {(relation, model): {index: (p, h)}}} from the grading's solution-group members."""
    out: dict = {}
    for t in grading["tasks"]:
        cells = out.setdefault(t["task"], {})
        for r in t["rows"]:
            for m in r["members"]:
                cells.setdefault((m["relation"], m["model"]), {})[m["index"]] = (m["stored_p_pass"], r["h_pass"])
    return out


def scored(cells: dict, relations: list[str], first_only: bool) -> list[tuple]:
    """RQ3's scored solutions of one task: [(relation, model, index, p, h)]."""
    sols = []
    for (rel, model), by_index in sorted(cells.items()):
        if rel not in relations or not by_index:
            continue
        idx = sorted(by_index)
        pick = idx[0] if first_only else next((i for i in idx if by_index[i][0]), idx[0])
        sols.append((rel, model, pick, *by_index[pick]))
    return sols


def metrics(scores: list[float], labels: list[int], tau: float) -> dict:
    from meta_real_eval.analysis.statistics import roc_auc
    pos, neg = sum(labels), len(labels) - sum(labels)
    res = {"n": len(labels), "n_positive": pos, "n_negative": neg, "auc": roc_auc(scores, labels).get("auc")}
    if pos and neg:
        tp = sum(1 for s, y in zip(scores, labels) if y and s >= tau)
        fp = sum(1 for s, y in zip(scores, labels) if not y and s >= tau)
        res.update(sensitivity=tp / pos, specificity=1 - fp / neg, youden_j=tp / pos - fp / neg)
    return res


def analyse(grading: dict, cohort: set, pop: dict) -> dict:
    tl, tau = pop["task_level"]["tasks"], pop["tau_div"]
    held = set(pop["held_out_labels"])
    population = sorted(held & cohort)
    outs = outcomes(grading)
    res = {"tau_div": tau, "population": len(population), "held_out_split": len(held), "cohort": len(cohort)}
    for name, first_only in (("primary_selection", False), ("first_completion_sensitivity", True)):
        rows, skipped = [], []
        for lab in population:
            entry = tl.get(lab) or {}
            score = entry.get("pairwise_disagreement_rate")
            if score is None:
                skipped.append({"task": lab, "reason": "no RQ3 score"})
                continue
            sols = scored(outs.get(lab, {}), entry.get("selected_relations", []), first_only)
            rows.append({"task": lab, "score": score, "n_scored": len(sols), "n_solutions_rq3": entry.get("n_solutions"),
                         "label_primary": int(any(p and not h for *_, p, h in sols)),
                         "label_secondary": int(any(not (p and h) for *_, p, h in sols)),
                         "p_pass_h_fail": [f"{r}/{m}/{i}" for r, m, i, p, h in sols if p and not h]})
        res[name] = {"tasks": rows, "skipped": skipped,
                     "count_mismatch": [r["task"] for r in rows if r["n_scored"] != r["n_solutions_rq3"]],
                     "primary": metrics([r["score"] for r in rows], [r["label_primary"] for r in rows], tau),
                     "secondary": metrics([r["score"] for r in rows], [r["label_secondary"] for r in rows], tau)}
    return res


def report_md(res: dict, grading_path: Path) -> str:
    L = [f"# RQ3 with H, task level (`{grading_path}`)", "",
         f"Population {res['population']} tasks (held-out split {res['held_out_split']} ∩ cohort {res['cohort']}); "
         f"tau_div = {res['tau_div']:.4f}. Descriptive.", "",
         "| selection | label | n | positives | AUC | sensitivity | specificity | J |", "|---|---|---|---|---|---|---|---|"]
    f = lambda x: "-" if x is None else f"{x:.3f}"  # noqa: E731
    for sel in ("primary_selection", "first_completion_sensitivity"):
        for lab in ("primary", "secondary"):
            m = res[sel][lab]
            L.append(f"| {sel} | {lab} | {m['n']} | {m['n_positive']} | {f(m['auc'])} | {f(m.get('sensitivity'))} | "
                     f"{f(m.get('specificity'))} | {f(m.get('youden_j'))} |")
    s = res["primary_selection"]
    L += ["", f"Tasks with a primary-label positive: {[r['task'] for r in s['tasks'] if r['label_primary']]}",
          f"Skipped: {s['skipped']}; scored-solution count differs from RQ3's on: {s['count_mismatch']}"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import analyze_stage5
    import freeze_h
    from meta_real_eval.core.provenance import write_run_manifest
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--grading", type=Path, required=True)
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expect-cohort", type=int, default=55)
    args = ap.parse_args(argv)
    grading = json.loads(args.grading.read_text(encoding="utf-8"))
    if grading.get("isolation") != "per_test_process":
        raise SystemExit("ERROR: the grading was not produced by the isolated runner (decisions 10.5)")
    audit = set(json.loads(args.audit.read_text(encoding="utf-8"))["tasks"])
    record = freeze_h.record_for(Path(grading["hidden"]))
    cohort = analyze_stage5.cohort_from_freeze(grading, audit, record, args.expect_cohort)
    res = analyse(grading, cohort, json.loads(POP.read_text(encoding="utf-8")))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "rq3_h.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (args.out / "rq3_h.md").write_text(report_md(res, args.grading), encoding="utf-8")
    write_run_manifest(args.out, stage="rq3_with_h", inputs={"grading": args.grading, "audit": args.audit,
                                                             "freeze_record": record, "rq3_population": POP})
    print(report_md(res, args.grading))
    return 0


if __name__ == "__main__":
    sys.exit(main())
