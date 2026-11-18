"""Stage 2b analysis (protocol_freeze_decisions.md section 9).

    python scripts/analyze_coupling.py --run results_tier2_ext/coupling/dev_pilot --technical
    python scripts/analyze_coupling.py --run results_tier2_ext/coupling/full --endpoints --config config/tier2_extensions.yaml

--technical  gate GC only: valid tests, run agreement, history reproduction, false detection,
             availability, redundancy, exclusion reasons, the projected conditional population.
             Never prints a coupling value (the pilot is blind to the LLM-vs-operator effect).
--endpoints  the frozen analysis. Refuses unless config/extensions_protocol/coupling_v1.json exists,
             matches the spec the run used, and the solution groups match the frozen digests.
             Development tasks are excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics as st
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.analysis.statistics import holm, paired_cluster_bootstrap, wilcoxon_test  # noqa: E402
from meta_real_eval.oracles.coupling import SOURCES, SPEC, exclusion_counts, task_analysis  # noqa: E402

FROZEN = ec.PROTOCOL_DIR / "coupling_v1.json"


def load_run(run: Path) -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(run.glob("*/detection.json"))]


def p_pass(prog: dict):
    """P verdict: the per-test run when available, else the stored RQ2 verdict (all members pass)."""
    if prog.get("p_passed_all") is not None:
        return bool(prog["p_passed_all"])
    if prog["kind"] == "solution":
        v = [m["stored_p_pass"] for m in prog["members"]]
        return None if None in v else all(v)
    return None if prog.get("historical_killed") is None else not prog["historical_killed"]


def inputs(det: dict, pool: str = "primary", gen_limit: int | None = None):
    """(tests, mutants, solutions) for coupling.task_analysis. A test masked for any program is
    dropped for the whole task (counted)."""
    if pool == "primary":
        tests = dict(det["tests"]["primary"])
        if gen_limit is not None:
            tests = {t: s for t, s in tests.items() if s != "gen" or int(t.rsplit("_", 1)[1]) < gen_limit}
    else:
        tests = {t: "x" for t in det["tests"]["perturbed"] or []}
    masked = set()
    for p in det["programs"]:
        if p.get(pool):
            masked |= set(p[pool]["masked"])
    tests = {t: s for t, s in tests.items() if t not in masked}
    muts, sols = [], []
    for p in det["programs"]:
        if p["kind"] == "reference" or p.get(f"{pool}_error"):   # errored: no cells, not "undetected"
            continue
        cells = p.get(pool) or {"detect": [], "import_error": True}
        detect = {t for t in cells["detect"] if t in tests}
        if p["kind"] == "mutant":
            muts.append({"id": p["id"], "source": p["source"], "models": p["models"], "detect": detect,
                         "p_live": p_pass(p)})
        else:
            sols.append({"id": p["id"], "models": p["models"], "detect": detect,
                         "invalid": bool(cells.get("import_error")), "p_pass": p_pass(p)})
    return tests, muts, sols, len(masked)


# ---------------------------------------------------------------------------
# Technical report (gate GC)
# ---------------------------------------------------------------------------

def stratified_sample(spot: list[dict], n: int) -> list[dict]:
    """Deterministic spot-check sample: round-robin over tasks, within a task one row per distinct
    (test, difference) first, so n rows are not all the same difference of the same task."""
    by_task: dict[str, list[dict]] = {}
    seen: set = set()
    for s in sorted(spot, key=lambda s: (s["task"], s["test"], s["solution"])):
        key = (s["task"], s["test"], s["difference"])
        if key not in seen:
            seen.add(key)
            by_task.setdefault(s["task"], []).append(s)
    out = []
    while len(out) < n and any(by_task.values()):
        for rows in by_task.values():
            if rows and len(out) < n:
                out.append(rows.pop(0))
    return out


def reference_problems(det: dict) -> Optional[list[str]]:
    """Gate GC 'reference rows are clean': the reference, run as a program, detects nothing and has
    no masked cell in either pool, and passes P. None for runs made before the reference row existed."""
    ref = next((p for p in det["programs"] if p["kind"] == "reference"), None)
    if ref is None:
        return None
    bad = [f"{pool}_error" for pool in ("primary", "perturbed") if ref.get(f"{pool}_error")]
    for pool in ("primary", "perturbed"):
        for cell in ("detect", "masked"):
            if (ref.get(pool) or {}).get(cell):
                bad.append(f"{pool}.{cell}: {len(ref[pool][cell])}")
    if ref.get("p_passed_all") is False:
        bad.append("fails P")
    return bad


def masked_share(det: dict, pool: str) -> Optional[float]:
    progs = [p for p in det["programs"] if p["kind"] != "reference"]
    n_cells = len(det["tests"][pool] or []) * len(progs)
    return sum(len((p.get(pool) or {}).get("masked", [])) for p in progs) / n_cells if n_cells else None


def technical(dets: list[dict]) -> dict:
    rows, hist_m, hist_s, fd_num, fd_den, spot, hist_timeouts = [], [0, 0], [0, 0], 0, 0, [], 0
    for det in dets:
        tests, muts, sols, n_masked = inputs(det)
        r = task_analysis(det["task"], tests, muts, sols, counts_only=True)
        rows.append({"task": det["task"], "supported": det["support"]["supported"], "valid_tests": r["n_tests"],
                     "by_stratum": r["n_tests_by_stratum"], "masked_tests": n_masked,
                     "masked_cell_share": masked_share(det, "primary"),
                     "perturbed_masked_cell_share": masked_share(det, "perturbed"),
                     "reference_problems": reference_problems(det),
                     "contract_status": (det.get("contract") or {}).get("status"),
                     "runner_errors": {pl: sum(bool(p.get(f"{pl}_error")) for p in det["programs"])
                                       for pl in ("primary", "perturbed")},
                     "perturbed_pool_error": det.get("perturbed_error"),
                     "programs": len(det["programs"]), "seconds": det["seconds"],
                     "mutants": r["mutants"], "goals": r.get("goals"), "solution_categories": r["solution_categories"],
                     "excluded": r["excluded"]})
        for p in det["programs"]:
            outs = list((p.get("p_outcomes") or {}).values())
            if outs and all(o == "timeout" for o in outs):  # whole-suite timeout: machine, not program
                hist_timeouts += 1
                continue
            if p.get("p_passed_all") is not None:          # history reproduction needs the per-test run
                if p["kind"] == "mutant" and p.get("historical_killed") is not None:
                    hist_m[0] += (not p["p_passed_all"]) == p["historical_killed"]
                    hist_m[1] += 1
                if p["kind"] == "solution":
                    for m in p["members"]:
                        if m["stored_p_pass"] is not None:
                            hist_s[0] += m["stored_p_pass"] == p["p_passed_all"]
                            hist_s[1] += 1
            if p["kind"] == "solution" and p_pass(p) and p.get("perturbed"):
                orig = [t for t in det["tests"]["perturbed"] or [] if "~p" not in t]
                fd_den += len(orig)
                fd_num += len(set(p["perturbed"]["detect"]) & set(orig))
        for p in det["programs"]:
            if p["kind"] == "solution" and p_pass(p):
                for t, d in (p["primary"] or {}).get("p_details", {}).items():
                    spot.append({"task": det["task"], "solution": p["id"], "test": t, "difference": d})
    valid = [r["valid_tests"] for r in rows if r["supported"]]

    def agreement(key):
        shares = [r[key] for r in rows if r[key] is not None]
        return 1 - (sum(shares) / len(shares)) if shares else None

    return {
        "tasks": len(rows), "supported_tasks": len(valid),
        "median_valid_tests_supported": st.median(valid) if valid else None,
        "cell_agreement": agreement("masked_cell_share"),
        "perturbed_cell_agreement": agreement("perturbed_masked_cell_share"),
        "reference_rows": {"clean": sum(r["reference_problems"] == [] for r in rows),
                           "not_checked": [r["task"] for r in rows if r["reference_problems"] is None],
                           "problems": {r["task"]: r["reference_problems"] for r in rows if r["reference_problems"]}},
        "contract_status": {r["task"]: r["contract_status"] for r in rows if r["supported"]},
        "history_mutants_killed_reproduced": f"{hist_m[0]}/{hist_m[1]}",
        "history_solutions_p_pass_reproduced": f"{hist_s[0]}/{hist_s[1]}",
        "p_whole_suite_timeouts_excluded": hist_timeouts,
        "runner_errors_excluded": {pl: sum(r["runner_errors"][pl] for r in rows) for pl in ("primary", "perturbed")},
        "perturbed_pool_unavailable": [r["task"] for r in rows if r["perturbed_pool_error"]],
        "perturbed_false_detection_on_p_passing": (fd_num / fd_den) if fd_den else None,
        "primary_p_scenario_detections_on_p_passing_solutions": len(spot),
        "spot_check_by_task": {t: sum(s["task"] == t for s in spot) for t in sorted({s["task"] for s in spot})},
        "spot_check_sample": stratified_sample(spot, 10),
        "exclusion_reasons": exclusion_counts(rows),
        "projected_conditional_population": sum(r["excluded"] is None for r in rows),
        "seconds_total": sum(r["seconds"] for r in rows), "per_task": rows,
        "note": "technical only: no coupling value is computed or shown",
    }


# ---------------------------------------------------------------------------
# Endpoints (frozen analysis)
# ---------------------------------------------------------------------------

def _row_set(dets, dev, **kw) -> list[dict]:
    pool, gen_limit = kw.pop("pool", "primary"), kw.pop("gen_limit", None)
    out = []
    for det in dets:
        if det["task"] in dev:
            continue
        tests, muts, sols, _ = inputs(det, pool, gen_limit)
        out.append(task_analysis(det["task"], tests, muts, sols, B=SPEC["null_permutations"], seed=SPEC["version"], **kw))
    return out


def compare(rows: list[dict], key: str) -> dict:
    rows = [r for r in rows if r["excluded"] is None]
    llm = [r["means"]["llm_whole"][key] for r in rows]
    op = [r["means"]["operator"][key] for r in rows]
    if len(rows) < 2:
        return {"n_tasks": len(rows), "note": "fewer than 2 contributing tasks"}
    return {"n_tasks": len(rows), "mean_llm": st.mean(llm), "mean_operator": st.mean(op),
            "delta": paired_cluster_bootstrap({r["task"]: [a - b] for r, a, b in zip(rows, llm, op)}),
            "wilcoxon": wilcoxon_test(llm, op), "n_zero_delta": sum(a == b for a, b in zip(llm, op))}


def endpoints(dets: list[dict], dev: set) -> dict:
    main = _row_set(dets, dev)
    n = sum(r["excluded"] is None for r in main)
    hidden = _row_set(dets, dev, fault_filter=lambda s: s["p_pass"] is True,
                      mutant_filter=lambda m: m["p_live"] is True)
    secondary = {"strict_share": compare(main, "strict"), "fault_coverage": compare(main, "fc"),
                 "hidden_fault_strict_share_p_live": compare(hidden, "strict")}
    pv = {k: v["wilcoxon"]["p_value"] for k, v in secondary.items() if "wilcoxon" in v}
    contributing = [r for r in main if r["excluded"] is None]
    same = [c["llm_same_model_max_pc"] for r in contributing for c in r["classes"] if c["llm_same_model_max_pc"] is not None]
    cross = [c["llm_whole"]["max_pc_unequalised"] for r in contributing for c in r["classes"] if c["llm_same_model_max_pc"] is not None]
    sens = {"perturbed_pool": compare(_row_set(dets, dev, pool="perturbed"), "lift"),
            "pool_size_40": compare(_row_set(dets, dev, gen_limit=SPEC["pool_size_check_n_generated"]), "lift"),
            "total_failures_included": compare(_row_set(dets, dev, include_total_failures=True), "lift"),
            "unstratified_null": compare(_row_set(dets, dev, stratified_null=False), "lift"),
            "no_deduplication": compare(_row_set(dets, dev, deduplicate=False), "lift"),
            "unequalised_max": compare(_row_set(dets, dev, equalise=False), "lift")}
    return {
        "power_rule": {"conditional_population": n, "min_tasks": SPEC["power_rule_min_tasks"],
                       "confirmatory": n >= SPEC["power_rule_min_tasks"]},
        "exclusion_reasons": exclusion_counts(main),
        "primary_delta_lift": compare(main, "lift"),
        "secondary": secondary, "secondary_holm": holm(pv) if pv else None,
        "descriptive": {k: compare(main, k) for k in ("pc", "mean_pc", "max_pc_unequalised", "null_pc")}
                       | {"availability": {src: [sum(r["mutants"][src]["detected"] for r in main),
                                                 sum(r["mutants"][src]["groups"] for r in main)]
                                           for src in (*SOURCES, "mixed")},
                          "goals_vs_detected_groups": {src: [sum((r.get("goals") or {}).get(src, 0) for r in main),
                                                             sum(r["mutants"][src]["detected"] for r in main)]
                                                       for src in SOURCES},
                          "same_vs_cross_model_max_pc": {"n_classes": len(same),
                                                          "same_model": st.mean(same) if same else None,
                                                          "cross_model": st.mean(cross) if cross else None}},
        "sensitivity": sens,
        "per_task": [{k: v for k, v in r.items() if k != "classes"} for r in main],
    }


def frozen_ok(dets: list[dict]) -> list[str]:
    if not FROZEN.exists():
        return ["coupling_v1.json is not frozen yet"]
    fz = json.loads(FROZEN.read_text(encoding="utf-8"))
    problems = []
    if fz["spec_sha256"] != hashlib.sha256(json.dumps(SPEC, sort_keys=True).encode()).hexdigest():
        problems.append("code SPEC differs from the frozen spec")
    for d in dets:
        if d.get("spec_sha256") != fz["spec_sha256"]:
            problems.append(f"{d['task']}: run used a different spec")
        if fz["solution_groups"].get(d["task"]) != d["solution_groups_digest"]:
            problems.append(f"{d['task']}: solution groups differ from the frozen digest")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", type=Path, required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--technical", action="store_true")
    mode.add_argument("--endpoints", action="store_true")
    ap.add_argument("--config", type=Path, default=Path("config/tier2_extensions.yaml"))
    args = ap.parse_args(argv)
    dets = load_run(args.run)
    if not dets:
        raise SystemExit(f"ERROR: no detection.json under {args.run}")
    if args.technical:
        res = technical(dets)
        out = args.run / "technical.json"
    else:
        problems = frozen_ok(dets)
        if problems:
            raise SystemExit("ERROR: endpoints refused:\n  " + "\n  ".join(problems[:20]))
        dev = set(ec.load_ext_config(args.config).extensions.development_tasks)
        res = endpoints(dets, dev)
        out = args.run / "endpoints.json"
    out.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("per_task", "spot_check_sample")}, indent=1, default=str))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
