"""RQ4c held-out detection: does a hidden suite H catch held-out faults that P misses? (plan rev. 9.3)

    python scripts/eval_heldout.py --config config/tier2_extensions.yaml \
        --witness results_tier2_ext/witness/dev_pilot_freia --hidden results_tier2_ext/a2/dev_pilot \
        --out results_tier2_ext/a2/dev_pilot/heldout.json [--workers 8]

For every task with ``<hidden>/<task>/hidden_tests.py`` (any arm: A2, A3, A2+A3) and every HELD-OUT
fault group of the frozen split, the group's representative program runs the hidden tests (real
pytest); H detects it when any hidden test does not pass. P detection is the stored historical
kill (RQ1 kill matrix). Groups are reported in two populations (circularity fix, rev. 9.3):

  primary          held-out groups with a primary witness (D3), split by confirmation origin
                   (``generated`` = found by our generator, ``p_scenario`` = found on a P scenario)
  stage0_nonequiv  held-out groups non-equivalent under the historical Stage 0 / Pynguin replay,
                   which does not depend on our generator

Per population: groups, detected by P / H / P or H, H-only (added by H), P-only, and the mean of
per-task detection rates. Descriptive here; on development tasks it is the input for tuning A2
(e.g. ``--cover-k``), never for evaluation-task decisions.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.oracles.admission import run_tests_isolated  # noqa: E402
from meta_real_eval.oracles.fault_groups import load_split  # noqa: E402

EQUIV = ("no_divergence", "no_testable_inputs", "ast_identical")


def is_primary(g):
    return (g["outcome"] == "distinguished" and g["level"] == "api_visible" and g["domain"] == "valid"
            and (g.get("replay") or {}).get("confirmed", False))


def stage0_nonequivalent(g):
    return any(m.get("equivalence") is not None and m.get("equivalence") not in EQUIV for m in g["members"])


def p_killed(g):
    ks = [m.get("killed") for m in g["members"] if m.get("killed") is not None]
    return any(ks) if ks else None


def hidden_names(code: str) -> list[str]:
    return re.findall(r"^def (test_h_\d+)\(\)", code, flags=re.M)


def populations(g) -> list[str]:
    out = []
    if is_primary(g):
        out.append(f"primary/{g['origin']}")
    if stage0_nonequivalent(g):
        out.append("stage0_nonequiv")
    return out


def aggregate(rows: list[dict]) -> dict:
    out = {}
    pops = sorted({p for r in rows for p in r["populations"]} | {"primary"})
    for pop in pops:
        sel = [r for r in rows if any(p == pop or p.startswith(pop + "/") for p in r["populations"])
               and r["p_killed"] is not None and r["h_detected"] is not None]
        per_task: dict = {}
        for r in sel:
            per_task.setdefault(r["task"], []).append(r)

        def mean_rate(key):
            rates = [sum(x[key] for x in v) / len(v) for v in per_task.values()]
            return sum(rates) / len(rates) if rates else None
        for r in sel:
            r["either"] = r["p_killed"] or r["h_detected"]
        out[pop] = {"tasks": len(per_task), "groups": len(sel),
                    "p_detected": sum(r["p_killed"] for r in sel), "h_detected": sum(r["h_detected"] for r in sel),
                    "p_or_h": sum(r["either"] for r in sel),
                    "h_only": sum(r["h_detected"] and not r["p_killed"] for r in sel),
                    "p_only": sum(r["p_killed"] and not r["h_detected"] for r in sel),
                    "mean_task_rate_p": mean_rate("p_killed"), "mean_task_rate_h": mean_rate("h_detected"),
                    "mean_task_rate_p_or_h": mean_rate("either")}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--witness", type=Path, required=True)
    ap.add_argument("--hidden", type=Path, required=True, help="directory with <task>/hidden_tests.py")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ungated", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--after-freeze", action="store_true",
                    help="allow evaluation tasks: only once canonical H v1 is frozen (tag tier2-hidden-v1)")
    args = ap.parse_args(argv)
    cfg = ec.load_ext_config(args.config)
    hidden_tasks = {p.parent.name for p in args.hidden.glob("*/hidden_tests.py")}
    if not args.after_freeze and hidden_tasks - set(cfg.extensions.development_tasks):
        raise SystemExit("ERROR: held-out detection on evaluation tasks only after H is frozen (--after-freeze); "
                         "before that it would invite tuning on evaluation tasks (plan D5)")
    if args.after_freeze:
        import freeze_h
        freeze_h.verify(args.hidden)          # only the committed frozen bundle unlocks evaluation tasks
    pins = ec.pins_ok(cfg)
    policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=False)   # grading
    policy.activate()
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    split_groups, _ = load_split(ec.PROTOCOL_DIR / "fault_split_v1.json")
    bench = get_benchmark(cfg)
    baseline = Path(cfg.extensions.baseline_scores)
    jobs = []
    for hf in sorted(args.hidden.glob("*/hidden_tests.py")):
        lab = hf.parent.name
        wit = json.loads((args.witness / lab / "witness.json").read_text(encoding="utf-8"))
        code_h = hf.read_text(encoding="utf-8")
        names = hidden_names(code_h)
        records = {r["record_id"]: r for r in ec.collect_fault_records(bench, tasks[lab], baseline)}
        for g in wit["groups"]:
            pops = populations(g)
            if g["side"] != "held_out" or not pops:
                continue
            rec = records.get(g["representative"])
            frozen = next(m["code_sha256"] for m in split_groups[lab][g["group_id"]]["members"]
                          if m["record_id"] == g["representative"])
            if rec is None or hashlib.sha256(rec["code"].encode()).hexdigest() != frozen:
                raise SystemExit(f"ERROR: {lab}/{g['representative']}: code differs from the frozen split")
            jobs.append({"task": lab, "group_id": g["group_id"], "source": g["source"], "populations": pops,
                         "p_killed": p_killed(g), "runnable": rec["runnable"],
                         "args": (tasks[lab].module_name, rec["code"], code_h, names)})

    def run(j):
        if not j["runnable"]:
            return {**j, "h_detected": None, "h_outcomes": None}
        return {**j, "h_outcomes": run_tests_isolated(*j["args"], timeout_s=cfg.execution.timeout_s)}  # (10.5)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        done = list(ex.map(run, jobs))
    for r in done:                      # timed-out tests once more, alone and sequentially (load, 10.5)
        timed = [n for n, o in (r["h_outcomes"] or {}).items() if o == "timeout"]
        if timed:
            r["timeout_rerun"] = run_tests_isolated(*r["args"][:3], timed, timeout_s=cfg.execution.timeout_s)
            r["h_outcomes"] = {**r["h_outcomes"], **r["timeout_rerun"]}
        if r["h_outcomes"] is not None:  # a timeout is never a detection (as the RQ1 suite veto)
            r["h_detected"] = any(o not in ("ordinary_pass", "timeout") for o in r["h_outcomes"].values())
    rows = [{k: v for k, v in r.items() if k != "args"} for r in done]
    res = {"authoritative": gated, "hidden": str(args.hidden), "witness": str(args.witness), "isolation": "per_test_process",
           "pins": pins, "populations": aggregate(rows), "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res["populations"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
