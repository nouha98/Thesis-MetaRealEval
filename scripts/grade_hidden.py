"""Grade stored RQ2 completions on P and a hidden suite H, separately (plan rev. 9.3, Stage 5 core).

    # development tasks (tuning / erroneous-rejection checks; allowed by plan D5)
    python scripts/grade_hidden.py --config config/tier2_extensions.yaml \
        --hidden results_tier2_ext/a2/dev_k5 --out results_tier2_ext/a2/dev_k5/grading.json
    # compare two hidden suites on the same completions: completions that fail only the larger one
    python scripts/grade_hidden.py --compare results_tier2_ext/a2/dev_k3/grading.json \
        results_tier2_ext/a2/dev_k5/grading.json --out results_tier2_ext/a2/k3_vs_k5.md

P is the stored, frozen RQ2 verdict (``pass_rates.json`` ``per_completion``: all valid P tests pass).
H is run (real pytest) on every distinct completion program (solution groups, Stage 2b rule) and
expanded to its members. H passes when every hidden test passes. For each P-pass/H-fail program the
API differences are recomputed (failing test's scenario on the completion vs the expected reference
tokens) so a person can judge "true fault" vs "erroneous rejection" (audit question 2).

Evaluation tasks are refused unless ``--after-freeze`` (canonical H v1 frozen): before that, H
outcomes on RQ2 completions must never be seen (plan D5).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.benchmarks.contracts import api_rules, load_contract  # noqa: E402
from meta_real_eval.benchmarks.witness import GEN_ALIAS, WitnessSettings, _run  # noqa: E402
from meta_real_eval.oracles.admission import run_tests_isolated  # noqa: E402
from meta_real_eval.oracles.spec import spec_diff  # noqa: E402
from meta_real_eval.oracles.solution_groups import build_solution_groups  # noqa: E402


def failure_kind(exp, cand) -> str:
    """Why one expected token is not met (decisions 10.2: the exception rule is measured separately)."""
    if cand is None:
        return "stopped_earlier"
    if cand[0] == "exc" and exp[0] != "exc":
        return "unexpected_exception"        # raised where the reference returns on a contract-valid input
    if exp[0] == "exc":
        return "missing_documented_exception" if cand[0] != "exc" else "other_exception_type"
    return "type" if exp[0] == "@type" else "value"


def exception_caused(t: dict, tr: dict, rules: dict) -> bool:
    """Cluster C sensitivity (decisions 10.8): the test fails only because the candidate raised at a step where
    the reference did not (no failing assertion before that step)."""
    first = next((i for i in range(len(t["steps"])) if str(tr["tokens"].get(f"s{i}", "")).startswith("EXC:")
                  and (t["expected"].get(f"api:s{i}") or [None])[0] != "exc"), None)
    if first is None:
        return False
    return not any(spec_diff(v, tr["tokens"].get(k), rules, k) for k, v in t["expected"].items()
                   if int(k.rsplit("s", 1)[1]) < first)


def differences(module, code, contract, tests: list[dict], failing: list[str]) -> tuple[dict, list[str], bool]:
    """({test name: [api differences]}, sorted failure kinds, whether every failing A2 test is exception-caused)
    for the failing hidden tests, replayed."""
    rules = api_rules(contract)
    sel = [t for t in tests if t["name"] in failing]
    if not sel:
        return {}, [], False
    scs = [{"scenario_id": t["scenario_id"], "steps": t["steps"], "api_flags": t["api_flags"]} for t in sel]
    traces = _run(module, code, f"import {module} as {GEN_ALIAS}\n", scs, WitnessSettings(), rules)
    out, kinds = {}, set()
    caused = all(exception_caused(t, tr, rules) for t, tr in zip(sel, traces))
    for t, tr in zip(sel, traces):
        diffs = []
        for k, v in t["expected"].items():
            cand = tr["tokens"].get(k)
            if d := spec_diff(v, cand, rules, k):
                diffs.append(d)
                kinds.add(failure_kind(v, cand))
        if not diffs:
            kinds.add(f"replay_{tr['status']}")
        out[t["name"]] = diffs or [f"no API difference on replay (status {tr['status']})"]
    return out, sorted(kinds - {"stopped_earlier"} or kinds), caused


def grade_task(lab, task, bench, baseline, hidden_dir: Path, timeout_s: float, workers: int) -> dict:
    a2 = json.loads((hidden_dir / lab / "a2.json").read_text(encoding="utf-8"))
    h_code = (hidden_dir / lab / "hidden_tests.py").read_text(encoding="utf-8")
    tests = a2["final_tests"]                              # A2 scenario tests (replayable for the differences)
    names = re.findall(r"^def (test_h_\d+)\(\)", h_code, flags=re.M)   # every hidden test, A3 ones included
    contract = load_contract(ec.REPO / a2["contract"]["path"])
    comps = ec.read_json(baseline / "rq2" / "generate" / lab / "completions.json", {})
    rates = ec.read_json(baseline / "rq2" / "evaluate" / lab / "pass_rates.json", {})
    groups = build_solution_groups(lab, comps, rates, lambda c: bench.build_solution(task, c))

    codes = {}

    def finish(row, outs):
        failing = [n for n, o in outs.items() if o != "ordinary_pass"]
        row.update(h_pass=not failing, failing=failing, h_outcomes={n: outs[n] for n in failing})
        return row

    def one(item):
        gid, g = item
        r = g["representative"]
        code = codes[gid] = bench.build_solution(task, comps[r["relation"]][r["model"]][r["index"]])
        outs = run_tests_isolated(task.module_name, code, h_code, names, timeout_s)   # one process per test (10.5)
        p_pass = {m["stored_p_pass"] for m in g["members"]}
        return finish({"group_id": gid, "members": g["members"], "models": g["models"],
                       "p_pass": p_pass.pop() if len(p_pass) == 1 else None}, outs)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(one, groups.items()))
    # a timeout under parallel load is a runner limit: re-run each timed-out test once, alone and sequentially
    # (as the RQ2 evaluator does); a timeout that persists is an H failure, counted separately (10.5)
    for row in rows:
        timed = [n for n, o in row["h_outcomes"].items() if o == "timeout"]
        if timed:
            again = run_tests_isolated(task.module_name, codes[row["group_id"]], h_code, timed, timeout_s)
            row["timeout_rerun"] = again
            finish(row, {**{n: "ordinary_pass" for n in names}, **row["h_outcomes"], **again})

    def explain(row):
        if row["p_pass"] and row["failing"]:
            code = codes[row["group_id"]]
            row["differences"], row["failure_kinds"], caused = differences(task.module_name, code, contract, tests,
                                                                            row["failing"])
            a3_failing = sorted(set(row["failing"]) - {t["name"] for t in tests})
            row["exception_caused"] = caused and not a3_failing
            if a3_failing:                                 # free-form A3 property tests: no scenario to replay
                row["differences"].update({n: ["A3 property test failed"] for n in a3_failing})
                row["failure_kinds"] = sorted(set(row["failure_kinds"]) | {"a3_property"})
            row["code"] = code
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(explain, rows))
    members = [(m, r) for r in rows for m in r["members"]]
    c = Counter()
    for m, r in members:
        p = m["stored_p_pass"]
        c["completions"] += 1
        c["p_pass"] += bool(p)
        c["h_pass"] += r["h_pass"]
        c["p_and_h"] += bool(p) and r["h_pass"]
        c["p_pass_h_fail"] += bool(p) and not r["h_pass"]
        c["timeout_reruns"] += "timeout_rerun" in r
        if not r["h_pass"] and set(r["h_outcomes"].values()) == {"timeout"}:
            c["h_fail_timeout_only"] += 1                   # a runner limit, not a verdict: reported separately
            c["p_pass_h_fail_timeout_only"] += bool(p)
        if p and not r["h_pass"]:
            for k in r.get("failure_kinds", []):
                c[f"p_pass_h_fail:{k}"] += 1
            if r.get("failure_kinds") == ["unexpected_exception"]:
                c["p_pass_h_fail:exception_only"] += 1      # would pass if exceptions were not asserted
            c["p_pass_h_fail:exception_caused"] += bool(r.get("exception_caused"))   # cluster C (10.8)
    return {"task": lab, "hidden": str(hidden_dir / lab), "n_tests": len(names), "counts": dict(c),
            "programs": len(rows), "p_pass_h_fail_programs": sum(bool(r["p_pass"]) and not r["h_pass"] for r in rows),
            "rows": rows}


def annotate(cfg_path: Path, grading_path: Path, out: Path) -> int:
    """Add the cluster C flag (``exception_caused``) to an existing grading: replays only the failing A2 tests of
    its P-pass/H-fail programs (their code is stored); nothing else is re-run (decisions 10.8)."""
    cfg = ec.load_ext_config(cfg_path)
    policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=False)
    policy.activate()
    doc = json.loads(grading_path.read_text(encoding="utf-8"))
    hidden = Path(doc["hidden"])
    n = 0
    for t in doc["tasks"]:
        a2 = json.loads((hidden / t["task"] / "a2.json").read_text(encoding="utf-8"))
        contract = load_contract(ec.REPO / a2["contract"]["path"])
        names = {x["name"] for x in a2["final_tests"]}
        for r in t["rows"]:
            if r["p_pass"] and not r["h_pass"]:
                _, _, caused = differences(contract["module_name"], r["code"], contract, a2["final_tests"], r["failing"])
                r["exception_caused"] = caused and not (set(r["failing"]) - names)
                n += 1
    doc["annotated_exception_caused"] = True
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"annotated {n} P-pass/H-fail program(s); exception-caused: "
          f"{sum(bool(r.get('exception_caused')) for t in doc['tasks'] for r in t['rows'])} -> {out}")
    return 0


def compare(a_path: Path, b_path: Path, out: Path) -> int:
    """Programs that pass P and the smaller suite A but fail the larger suite B: the extra rejections of B."""
    a = {t["task"]: t for t in json.loads(a_path.read_text(encoding="utf-8"))["tasks"]}
    b = {t["task"]: t for t in json.loads(b_path.read_text(encoding="utf-8"))["tasks"]}
    L = [f"# Extra rejections of `{b_path.parent.name}` over `{a_path.parent.name}`", "",
         "Each case passes P and the smaller suite but fails the larger one. Judge each against the docstrings and "
         "the contract: **true fault** / **erroneous rejection** (the assertion is on unspecified or reference-specific "
         "behaviour) / **unclear**.", ""]
    n = 0
    for lab in sorted(set(a) & set(b)):
        a_ok = {r["group_id"] for r in a[lab]["rows"] if r["h_pass"]}
        for r in b[lab]["rows"]:
            if r["p_pass"] and not r["h_pass"] and r["group_id"] in a_ok:
                n += 1
                L += [f"## Case {n}: {lab}, program {r['group_id'][:12]} ({len(r['members'])} completions; "
                      f"models {', '.join(r['models'])})", "", "Failing hidden tests and API differences:", ""]
                for t, ds in r.get("differences", {}).items():
                    L += [f"- `{t}`: " + "; ".join(ds[:3])]
                L += ["", "<details><summary>completion</summary>", "", "```python", r.get("code", ""), "```", "",
                      "</details>", "", "Verdict: ______", ""]
    L.insert(2, f"**{n} case(s).**\n")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{n} extra rejection(s) -> {out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path)
    ap.add_argument("--hidden", type=Path, help="directory with <task>/hidden_tests.py and a2.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--compare", nargs=2, type=Path, metavar=("SMALLER", "LARGER"))
    ap.add_argument("--ungated", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--after-freeze", action="store_true",
                    help="allow evaluation tasks: only once canonical H v1 is frozen (tag tier2-hidden-v1)")
    ap.add_argument("--arm-of", type=Path, default=None,
                    help="with --after-freeze: --hidden is a comparison arm (A3, decisions 10.6) of this frozen bundle")
    ap.add_argument("--audit-reserved", type=Path, default=None,
                    help="audit_reserved.json (scripts/audit_h.py select): grade exactly the audit-reserved tasks "
                         "(allowed before the freeze, decisions 6); the selection is recomputed and must match")
    ap.add_argument("--annotate", type=Path, default=None,
                    help="existing grading.json: add the cluster C flag to its P-pass/H-fail programs (10.8)")
    args = ap.parse_args(argv)
    if args.compare:
        return compare(*args.compare, args.out)
    if args.annotate:
        if args.config is None:
            raise SystemExit("ERROR: --annotate needs --config")
        return annotate(args.config, args.annotate, args.out)
    if args.config is None or args.hidden is None:
        raise SystemExit("ERROR: --config and --hidden are required (or use --compare)")
    cfg = ec.load_ext_config(args.config)
    labels = sorted(p.parent.name for p in args.hidden.glob("*/hidden_tests.py"))
    if args.audit_reserved is not None:
        import audit_h
        listed = json.loads(args.audit_reserved.read_text(encoding="utf-8"))["tasks"]
        cohorts = json.loads((ec.PROTOCOL_DIR / "cohorts_v1.json").read_text(encoding="utf-8"))
        ready = audit_h.ready_tasks(args.hidden)
        recomputed = [t for t in cohorts["audit_order"] if t in ready][:audit_h.N_TASKS]
        if listed != recomputed:
            raise SystemExit("ERROR: the audit-reserved list differs from the frozen rule (first 20 H-ready tasks of "
                             "audit_order); rerun audit_h.py select")
        labels = [lab for lab in labels if lab in set(listed)]
    elif not args.after_freeze and set(labels) - set(cfg.extensions.development_tasks):
        raise SystemExit("ERROR: grading evaluation-task completions on H only after H is frozen (--after-freeze); "
                         "before that, H outcomes on RQ2 completions must not be seen (plan D5)")
    unlocked = {"frozen_h_sha256": None}
    if args.after_freeze and args.audit_reserved is None:
        import freeze_h                                  # only a committed frozen bundle unlocks them (or an arm of it)
        unlocked = freeze_h.unlock(args.hidden, args.arm_of)
    pins = ec.pins_ok(cfg)
    policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=False)   # grading
    policy.activate()
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    bench = get_benchmark(cfg)
    baseline = Path(cfg.extensions.baseline_scores)
    res = [grade_task(lab, tasks[lab], bench, baseline, args.hidden, cfg.execution.timeout_s, args.workers)
           for lab in labels]
    total = Counter()
    for r in res:
        total.update(r["counts"])
    doc = {"authoritative": gated, "hidden": str(args.hidden), **unlocked,
           "isolation": "per_test_process", "pins": pins,
           "totals": dict(total), "tasks": res}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"totals": dict(total), "per_task": {r["task"]: r["counts"] for r in res}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
