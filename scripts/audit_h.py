"""Audit of the hidden oracle H (decisions 6; plan rev. 9.3, Stage 4).

    # 1. select the audit-reserved tasks: the first 20 H-ready tasks of the frozen audit_order (no outcome used)
    python scripts/audit_h.py select --a2 results_tier2_ext/a2/full --out results_tier2_ext/audit_h/round1
    # 2. H outcomes on the audit tasks' RQ2 completions only (allowed before the freeze, decisions 6)
    python scripts/grade_hidden.py --config config/tier2_extensions.yaml --hidden results_tier2_ext/a2/full \
        --audit-reserved results_tier2_ext/audit_h/round1/audit_reserved.json \
        --out results_tier2_ext/audit_h/round1/grading.json
    # 3. the sheet: Q1 test validity (seeded min(5, n) tests per task), Q2 erroneous rejection (min(5, n)
    #    P-pass/H-fail programs per task, round-robin over models)
    python scripts/audit_h.py sheet --config config/tier2_extensions.yaml --a2 results_tier2_ext/a2/full \
        --out results_tier2_ext/audit_h/round1 [--ungated]
    # 4. after the verdicts are filled in items.csv: weighted ratio estimates, task-cluster bootstrap, acceptance
    python scripts/audit_h.py estimate --out results_tier2_ext/audit_h/round1

Verdicts: Q1 valid / over-specified / invalid; Q2 true fault / erroneous rejection / unclear (unclear is bounded
both ways). Acceptance (pre-registered): invalid share point <= 5% and upper <= 15%; erroneous-rejection share
point <= 10% and upper <= 25%.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402
import freeze_h  # noqa: E402

N_TASKS, PER_TASK, B, SEED_BOOT = 20, 5, 2000, 20261124
Q1 = ("valid", "over-specified", "invalid")
Q2 = ("true fault", "erroneous rejection", "unclear")


def ready_tasks(a2: Path) -> set[str]:
    return {p.parent.name for p in a2.glob("*/a2.json") if json.loads(p.read_text(encoding="utf-8"))["ready"]}


def select(a2: Path, out: Path) -> int:
    cohorts = json.loads((ec.PROTOCOL_DIR / "cohorts_v1.json").read_text(encoding="utf-8"))
    ready = ready_tasks(a2)
    chosen = [t for t in cohorts["audit_order"] if t in ready][:N_TASKS]
    out.mkdir(parents=True, exist_ok=True)
    rec = {"rule": cohorts["audit_reserved_rule"], "a2": str(a2), "n_ready": len(ready), "tasks": chosen,
           "strata": dict(Counter("csn" if "csn" in t else "post_cut-off" for t in chosen)),
           "evaluation_cohort": sorted(ready - set(chosen))}
    (out / "audit_reserved.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(f"{len(chosen)} audit tasks {rec['strata']}; evaluation cohort {len(rec['evaluation_cohort'])} tasks -> "
          f"{out / 'audit_reserved.json'}")
    return 0


def task_rng(label: str, seed: int) -> random.Random:
    return random.Random(int(hashlib.sha256(f"{seed}|audit|{label}".encode()).hexdigest()[:16], 16))


def show_token(tok) -> str:
    if tok[0] == "@any":
        return "returns normally"
    if tok[0] == "@type":
        return f"returns a value of kind {'/'.join(tok[1])}"
    if tok[0] == "exc":
        return f"raises {tok[1][0]}"
    return "returns " + json.dumps(tok)[:300]


def sheet(cfg_path: Path, a2: Path, out: Path, ungated: bool) -> int:
    cfg = ec.load_ext_config(cfg_path)
    tasks, _ = ec.load_tasks(cfg, ungated)
    sel = json.loads((out / "audit_reserved.json").read_text(encoding="utf-8"))
    grading = json.loads((out / "grading.json").read_text(encoding="utf-8")) if (out / "grading.json").exists() else None
    if grading is None:
        raise SystemExit("ERROR: run grade_hidden.py --audit-reserved first (Q2 needs the H outcomes)")
    gtask = {t["task"]: t for t in grading["tasks"]}
    spec = json.loads((ec.PROTOCOL_DIR / "output_spec_v1.json").read_text(encoding="utf-8"))["tasks"]
    items, L = [], ["# Audit of H (round 1)", "",
                    "Judge only against the **skeleton docstrings** (what the coding models saw) and the contract.", "",
                    "- **Q1** per test: *valid* (every assertion follows from the docstring) / *over-specified* (asserts "
                    "something the docstring does not promise) / *invalid* (contradicts the docstring).",
                    "- **Q2** per (completion, first failing test): *true fault* (the completion violates the docstring) / "
                    "*erroneous rejection* (the completion is acceptable; H is wrong) / *unclear*.", "",
                    "Write the verdicts in `items.csv` (column `verdict`).", ""]
    for lab in sel["tasks"]:
        a = json.loads((a2 / lab / "a2.json").read_text(encoding="utf-8"))
        tests = a["final_tests"]
        rng = task_rng(lab, cfg.extensions.seed)
        q1 = sorted(rng.sample(range(len(tests)), min(PER_TASK, len(tests))))
        L += [f"## {lab}", "", "<details><summary>skeleton (what the models saw)</summary>", "", "```python",
              tasks[lab].prompt.strip(), "```", "", "</details>", "",
              f"R7 levels: `{json.dumps(spec.get(lab, {}).get('levels', {}))}`", ""]
        for i in q1:
            t = tests[i]
            iid = f"Q1-{len(items) + 1}"
            items.append({"id": iid, "question": "Q1", "task": lab, "item": t["name"],
                          "weight": len(tests) / len(q1), "verdict": ""})
            L += [f"### {iid}: test `{t['name']}`", "", "| step | asserted |", "|---|---|"]
            for k, st in enumerate(t["steps"]):
                exp = t["expected"].get(f"api:s{k}")
                L.append(f"| `{st['src'][:160]}` | {show_token(exp) if exp else '-'} |")
            L += ["", "Verdict (valid / over-specified / invalid): ______", ""]
        g = gtask.get(lab)
        bad = [r for r in (g["rows"] if g else []) if r["p_pass"] and not r["h_pass"]]
        by_model: dict = {}
        for r in sorted(bad, key=lambda r: r["group_id"]):
            by_model.setdefault(r["models"][0], []).append(r)
        order, queues = [], [by_model[m] for m in sorted(by_model)]
        while any(queues) and len(order) < PER_TASK:          # round-robin over models
            for q in queues:
                if q and len(order) < PER_TASK:
                    order.append(q.pop(0))
        L += [f"**Q2: {len(bad)} P-pass/H-fail program(s) on this task; {len(order)} sampled.**", ""]
        for r in order:
            iid = f"Q2-{len(items) + 1}"
            first = r["failing"][0]
            items.append({"id": iid, "question": "Q2", "task": lab, "item": f"{r['group_id']}:{first}",
                          "weight": len(bad) / len(order), "verdict": "", "failure_kinds": ";".join(r.get("failure_kinds", []))})
            L += [f"### {iid}: program {r['group_id'][:12]} ({len(r['members'])} completions, {', '.join(r['models'])})", "",
                  f"First failing test `{first}`: " + "; ".join(r.get("differences", {}).get(first, [])[:3]),
                  f"(failure kinds: {', '.join(r.get('failure_kinds', []))})", "",
                  "<details><summary>completion</summary>", "", "```python", r.get("code", ""), "```", "", "</details>", "",
                  "Verdict (true fault / erroneous rejection / unclear): ______", ""]
    (out / "sheet.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    with (out / "items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "question", "task", "item", "weight", "failure_kinds", "verdict"])
        w.writeheader()
        for it in items:
            w.writerow({"failure_kinds": "", **it})
    n1 = sum(i["question"] == "Q1" for i in items)
    print(f"Q1 {n1} tests, Q2 {len(items) - n1} pairs on {len(sel['tasks'])} tasks -> {out / 'sheet.md'}, {out / 'items.csv'}")
    return 0


REVIEW_PER_TASK, REVIEW_TAG = 10, "stage5-review"


def review_sample(rows: list[dict], label: str, seed: int, k: int = REVIEW_PER_TASK,
                  tag: str = REVIEW_TAG) -> list[dict]:
    """Random min(k, n) of a task's P-pass/H-fail programs (decisions 10.7): seeded per task, ids sorted first.
    ``tag`` separates the H versions' samples (v1.1: "stage5-review-v1.1", decisions 10.8)."""
    bad = sorted((r for r in rows if r["p_pass"] and not r["h_pass"]), key=lambda r: r["group_id"])
    rng = random.Random(int(hashlib.sha256(f"{seed}|{tag}|{label}".encode()).hexdigest()[:16], 16))
    return rng.sample(bad, min(k, len(bad)))


def review(cfg_path: Path, grading_path: Path, hidden: Path, audit_path: Path, out: Path, ungated: bool,
           tag: str = REVIEW_TAG) -> int:
    """Post-freeze validity review of Stage 5 (decisions 10.7): the cohort's P-pass/H-fail programs, Q2 verdicts."""
    cfg = ec.load_ext_config(cfg_path)
    tasks, _ = ec.load_tasks(cfg, ungated)
    grading = json.loads(grading_path.read_text(encoding="utf-8"))
    audit = set(json.loads(audit_path.read_text(encoding="utf-8"))["tasks"])
    rec = freeze_h.verify(hidden)                    # the bundle is the frozen one; its version picks the spec shown
    if grading.get("frozen_h_sha256") != rec["global_sha256"]:
        raise SystemExit(f"ERROR: {grading_path} was not graded on the frozen H in {hidden} ({rec['version']})")
    spec = json.loads((ec.PROTOCOL_DIR / freeze_h.SPECS[rec["version"]]).read_text(encoding="utf-8"))["tasks"]
    items, L = [], ["# Stage 5 validity review: P-pass/H-fail programs on the evaluation cohort (decisions 10.7)", "",
                    "Judge only against the **skeleton docstrings** and the contract, never the reference. Per program: "
                    "*true fault* (the completion breaks something the docstring states) / *erroneous rejection* (the "
                    "completion is acceptable; H asserts unspecified or reference-specific behaviour) / *unclear*.", "",
                    "Write the verdicts in `items.csv` (column `verdict`).", ""]
    for t in sorted(grading["tasks"], key=lambda t: t["task"]):
        lab = t["task"]
        if lab in audit:
            continue
        n_bad = [r for r in t["rows"] if r["p_pass"] and not r["h_pass"]]
        if not n_bad:
            continue
        chosen = review_sample(t["rows"], lab, cfg.extensions.seed, tag=tag)
        tests = {x["name"]: x for x in json.loads((hidden / lab / "a2.json").read_text(encoding="utf-8"))["final_tests"]}
        L += [f"## {lab}: {len(n_bad)} program(s) ({sum(len(r['members']) for r in n_bad)} completions); "
              f"{len(chosen)} sampled", "", "<details><summary>skeleton (what the models saw)</summary>", "",
              "```python", tasks[lab].prompt.strip(), "```", "", "</details>", "",
              f"R7 levels: `{json.dumps(spec.get(lab, {}).get('levels', {}))}`", ""]
        for r in chosen:
            iid = f"R-{len(items) + 1}"
            first = r["failing"][0]
            items.append({"id": iid, "question": "Q2", "task": lab, "item": f"{r['group_id']}:{first}",
                          "weight": len(n_bad) / len(chosen), "completions": len(r["members"]), "verdict": "",
                          "failure_kinds": ";".join(r.get("failure_kinds", []))})
            L += [f"### {iid}: program {r['group_id'][:12]} ({len(r['members'])} completions; {', '.join(r['models'])})",
                  "", f"Failing tests: {', '.join(r['failing'])}; failure kinds: {', '.join(r.get('failure_kinds', []))}", ""]
            tt = tests.get(first)
            if tt:
                L += [f"First failing test `{first}` (what H asserts):", "", "| step | asserted |", "|---|---|"]
                for k, st in enumerate(tt["steps"]):
                    exp = tt["expected"].get(f"api:s{k}")
                    L.append(f"| `{st['src'][:160]}` | {show_token(exp) if exp else '-'} |")
                L.append("")
            L += ["Differences on replay: " + "; ".join(r.get("differences", {}).get(first, [])[:3]), "",
                  "<details><summary>completion</summary>", "", "```python", r.get("code", ""), "```", "", "</details>",
                  "", "Verdict (true fault / erroneous rejection / unclear): ______", ""]
    out.mkdir(parents=True, exist_ok=True)
    (out / "sheet.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    with (out / "items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "question", "task", "item", "weight", "completions", "failure_kinds",
                                          "verdict"])
        w.writeheader()
        w.writerows(items)
    print(f"review: {len(items)} program(s) on {len({i['task'] for i in items})} task(s) -> {out / 'sheet.md'}")
    return 0


def ratio(rows: list[dict], hit) -> float | None:
    den = sum(r["w"] for r in rows)
    return sum(r["w"] for r in rows if hit(r["v"])) / den if den else None


def boot(rows: list[dict], hit) -> list | None:
    tasks = sorted({r["task"] for r in rows})
    if not tasks:
        return None
    by = {t: [r for r in rows if r["task"] == t] for t in tasks}
    rng, vals = random.Random(SEED_BOOT), []
    for _ in range(B):
        sample = [r for t in (rng.choice(tasks) for _ in tasks) for r in by[t]]
        v = ratio(sample, hit)
        if v is not None:
            vals.append(v)
    vals.sort()
    return [vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]]


def exact_ci(rows: list[dict], hit) -> dict | None:
    """Clopper-Pearson 95% interval on the unweighted item counts (reporting only; the acceptance rule keeps the
    pre-registered weighted bootstrap). Needed because the bootstrap collapses to [0, 0] when no item is a hit;
    it ignores task clustering, so it is a lower bound on the real uncertainty."""
    from scipy.stats import beta
    n, k = len(rows), sum(bool(hit(r["v"])) for r in rows)
    if not n:
        return None
    lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
    one_sided = 1.0 if k == n else float(beta.ppf(0.95, k + 1, n - k))
    return {"k": k, "n": n, "ci95": [lo, hi], "upper95_one_sided": one_sided}


def estimate(out: Path) -> int:
    with (out / "items.csv").open(encoding="utf-8") as f:
        items = list(csv.DictReader(f))
    bad = [i["id"] for i in items if i["verdict"].strip() not in (Q1 if i["question"] == "Q1" else Q2)]
    if bad:
        raise SystemExit(f"ERROR: missing or unknown verdicts: {bad[:10]}{' ...' if len(bad) > 10 else ''}")
    res = {}
    for q, hits in (("Q1", {"invalid": lambda v: v == "invalid", "over_specified": lambda v: v == "over-specified"}),
                    ("Q2", {"erroneous_unclear_as_fault": lambda v: v == "erroneous rejection",
                            "erroneous_unclear_as_erroneous": lambda v: v in ("erroneous rejection", "unclear")})):
        rows = [{"task": i["task"], "w": float(i["weight"]), "v": i["verdict"].strip()} for i in items if i["question"] == q]
        if q == "Q2" and items and "completions" in items[0]:      # Stage 5 review: also weighted by completions
            cw = [{"task": i["task"], "w": float(i["weight"]) * int(i["completions"]), "v": i["verdict"].strip()}
                  for i in items if i["question"] == q]
            res["Q2_completion_weighted"] = {k: {"point": ratio(cw, h), "ci95": boot(cw, h)} for k, h in hits.items()}
        res[q] = {"n_items": len(rows), "n_tasks": len({r["task"] for r in rows}),
                  "verdicts": dict(Counter(r["v"] for r in rows)),
                  **{k: {"point": ratio(rows, h), "ci95": boot(rows, h), "exact": exact_ci(rows, h)}
                     for k, h in hits.items()}}
    inv = res["Q1"]["invalid"]
    err = res["Q2"]["erroneous_unclear_as_erroneous"]          # conservative bound for the acceptance rule
    ok1 = inv["point"] is not None and inv["point"] <= 0.05 and inv["ci95"][1] <= 0.15
    ok2 = err["point"] is None or (err["point"] <= 0.10 and err["ci95"][1] <= 0.25)
    if res["Q1"]["n_items"] == 0:                     # Stage 5 review (10.7): Q2 only, read against section 6's limits
        res["acceptance"] = {"invalid_ok": None, "erroneous_ok": ok2, "accepted": None,
                             "note": "Q2-only review: erroneous_ok uses the section 6 limits (point <= 10%, upper <= 25%)"}
        (out / "estimates.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(json.dumps(res, indent=1))
        return 0
    res["acceptance"] = {"invalid_ok": ok1, "erroneous_ok": ok2, "accepted": ok1 and ok2,
                         "note": "Q2 with no P-pass/H-fail pair is vacuous (n = 0) and reported as such" if err["point"] is None else None}
    (out / "estimates.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["select", "sheet", "estimate", "review"])
    ap.add_argument("--config", type=Path)
    ap.add_argument("--a2", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ungated", action="store_true")
    ap.add_argument("--grading", type=Path, help="review: the Stage 5 grading.json")
    ap.add_argument("--hidden", type=Path, help="review: the frozen H bundle")
    ap.add_argument("--audit", type=Path, help="review: audit_reserved.json (excluded)")
    ap.add_argument("--review-tag", default=REVIEW_TAG,
                    help="review: seed tag (H v1: stage5-review; H v1.1: stage5-review-v1.1, decisions 10.8)")
    args = ap.parse_args(argv)
    if args.cmd == "review":
        return review(args.config, args.grading, args.hidden, args.audit, args.out, args.ungated, args.review_tag)
    if args.cmd == "select":
        return select(args.a2, args.out)
    if args.cmd == "sheet":
        return sheet(args.config, args.a2, args.out, args.ungated)
    return estimate(args.out)


if __name__ == "__main__":
    sys.exit(main())
