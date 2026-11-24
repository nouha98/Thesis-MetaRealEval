"""Stage 4 A2: build, admit and control-check the reference-differential hidden tests (plan rev. 9.3).

    # development pilot (after G2; reads the pilot's witness results)
    python scripts/build_a2.py --config config/tier2_extensions.yaml \
        --witness results_tier2_ext/witness/dev_pilot_freia --tasks dev --out results_tier2_ext/a2/dev_pilot
    # evaluation tasks (after the full witness run), SLURM array shards
    python scripts/build_a2.py --config config/tier2_extensions.yaml \
        --witness results_tier2_ext/witness/full --tasks eval --out results_tier2_ext/a2/full --shard 0 --shards 8
    python scripts/build_a2.py --config config/tier2_extensions.yaml --out results_tier2_ext/a2/full --summarise

Per task (supported, reviewed contract):
  1. discovery groups = primary-confirmed groups (D3) on the frozen discovery side; their representative
     code is re-collected and hash-checked against fault_split_v1;
  2. build_a2: disjoint-seed pool -> reference baseline -> kills -> greedy (<= max_tests) -> emit;
  3. admission: every test passes on the reference 3x together and once alone;
  4. private-rename control: validated against the reference on the A2 pool, then every admitted
     test must pass on it (a failing test is over-specified and dropped);
  5. the final suite is re-emitted from the kept tests -> <out>/<task>/hidden_tests.py + a2.json.
A task is H-ready (A2) when at least one test is kept. Construction never sees held-out groups,
RQ2 completions or any final outcome (plan D5).
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.benchmarks.contracts import load_contract  # noqa: E402
from meta_real_eval.benchmarks.witness import WitnessSettings  # noqa: E402
from meta_real_eval.core import canary  # noqa: E402
from meta_real_eval.core.provenance import write_run_manifest  # noqa: E402
from meta_real_eval.oracles.admission import admit, private_rename, run_tests, validate_control  # noqa: E402
from meta_real_eval.oracles.fault_groups import load_split  # noqa: E402
from meta_real_eval.oracles.regression import A2Settings, build_a2, emit, reference_entries  # noqa: E402

RUN_ONLY = ("tasks", "gated", "workers")
OUTPUT_SPEC = ec.PROTOCOL_DIR / "output_spec_v1.json"


def output_levels(spec: dict, label: str, dev: bool) -> tuple:
    """(levels, reason-if-not-usable) from the R7 output specification. Evaluation tasks need a
    reviewed entry; development tasks may use a draft (tuning)."""
    entry = spec.get("tasks", {}).get(label)
    if entry is None:
        return None, "no output specification (R7)"
    if entry.get("status") != "reviewed" and not dev:
        return None, "output specification not reviewed (R7)"
    return entry["levels"], None


def is_primary(g: dict) -> bool:
    return (g["outcome"] == "distinguished" and g["level"] == "api_visible" and g["domain"] == "valid"
            and (g.get("replay") or {}).get("confirmed", False))


def discovery_codes(wit: dict, task, bench, baseline: Path, split_groups: dict) -> dict:
    """{group_id: representative code} of the task's primary-confirmed discovery groups (hash-checked)."""
    records = {r["record_id"]: r for r in ec.collect_fault_records(bench, task, baseline)}
    out = {}
    for g in wit["groups"]:
        if g["side"] != "discovery" or not is_primary(g):
            continue
        rec = records.get(g["representative"])
        frozen = next(m["code_sha256"] for m in split_groups[wit["task"]][g["group_id"]]["members"]
                      if m["record_id"] == g["representative"])
        if rec is None or hashlib.sha256(rec["code"].encode()).hexdigest() != frozen:
            raise SystemExit(f"ERROR: {wit['task']}/{g['representative']}: code differs from the frozen split")
        out[g["group_id"]] = rec["code"] if rec["runnable"] else None
    return out


def run_task(wit: dict, task, bench, baseline, split_groups, settings: A2Settings, ext_seed: int,
             wsettings: WitnessSettings, timeout_s: float, spec: dict, dev: bool) -> dict:
    base = {"task": wit["task"], "contract": wit["contract"], "ready": False}
    if not wit["support"]["supported"]:
        return {**base, "reason": "unsupported task (Stage 2)"}
    levels, why = output_levels(spec, wit["task"], dev)
    if why:
        return {**base, "reason": why}
    base["output_spec_status"] = spec["tasks"][wit["task"]].get("status")
    contract = load_contract(ec.REPO / wit["contract"]["path"])
    disc = discovery_codes(wit, task, bench, baseline, split_groups)
    if not disc:
        return {**base, "reason": "no primary-confirmed discovery group"}
    t0 = time.monotonic()
    b = build_a2(task.label, task.module_name, task.reference_code, contract, disc, settings, ext_seed, wsettings,
                 levels)
    rec = {**base, **b}
    tests = b["tests"]
    if not tests:
        return {**rec, "reason": "no pool scenario kills a discovery group", "seconds": round(time.monotonic() - t0, 1)}
    code = emit(task.task_id, task.module_name, contract, tests)
    adm = admit(task.module_name, task.reference_code, code, [t["name"] for t in tests], timeout_s)
    kept = [t for t in tests if adm[t["name"]]["admitted"]]
    # control: validated private rename; admitted tests must pass on it
    control = {"kind": "private_rename", "applicable": False}
    variant = private_rename(task.reference_code, contract["class_name"])
    if variant is not None and kept:
        entries = reference_entries(task.module_name, task.reference_code, contract,
                                    [{"scenario_id": t["scenario_id"], "steps": t["steps"], "api_flags": t["api_flags"]}
                                     for t in kept], settings.witness_settings())
        val = validate_control(task.module_name, variant, contract, entries, settings.witness_settings())
        control = {"kind": "private_rename", "applicable": True, **val}
        if val["valid"]:
            kc = emit(task.task_id, task.module_name, contract, kept)
            names = [f"test_h_{i}" for i in range(len(kept))]
            outs = run_tests(task.module_name, variant, kc, names, timeout_s)
            over = [kept[i]["scenario_id"] for i, n in enumerate(names) if outs[n] != "ordinary_pass"]
            control["over_specified"] = over
            kept = [t for t in kept if t["scenario_id"] not in over]
        else:
            control["transform_defect"] = True
    for i, t in enumerate(kept):
        t["name"] = f"test_h_{i}"
    final = emit(task.task_id, task.module_name, contract, kept) if kept else ""
    return {**rec, "admission": adm, "control": control, "kept": [t["scenario_id"] for t in kept],
            "final_tests": kept, "final_code": final, "ready": bool(kept),
            "covered_final": sorted(set().union(*(set(t["kills"]) for t in kept)) if kept else set()),
            "reason": None if kept else "no test admitted", "seconds": round(time.monotonic() - t0, 1)}


def summarise(out: Path) -> dict:
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out.glob("*/a2.json"))]
    ready = [r for r in recs if r["ready"]]
    disc = sum(len(r.get("discovery_groups", [])) for r in ready)
    cov = sum(len(r.get("covered_final", [])) for r in ready)
    s = {"tasks": len(recs), "ready": len(ready), "not_ready": dict(Counter(r["reason"] for r in recs if not r["ready"])),
         "tests_kept": sum(len(r["final_tests"]) for r in ready),
         "admission_rejected": sum(sum(not a["admitted"] for a in r.get("admission", {}).values()) for r in recs),
         "over_specified": sum(len(r.get("control", {}).get("over_specified", [])) for r in recs),
         "control_transform_defects": sum(bool(r.get("control", {}).get("transform_defect")) for r in recs),
         "discovery_groups_on_ready": disc, "discovery_covered_on_ready": cov,
         "failed_tasks": sorted(p.parent.name for p in out.glob("*/error.txt"))}
    (out / "summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--witness", type=Path, help="Stage 2 results directory (dev pilot or full)")
    ap.add_argument("--tasks", nargs="+", default=["dev"], help="dev | eval | task labels")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ungated", action="store_true")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--summarise", action="store_true")
    ap.add_argument("--cover-k", type=int, default=1,
                    help="kill each discovery group with up to k tests (tune on dev tasks only, then freeze)")
    args = ap.parse_args(argv)
    if args.summarise:
        print(json.dumps(summarise(args.out), indent=1))
        return 0
    if args.witness is None:
        raise SystemExit("ERROR: --witness <Stage 2 results> is required")
    cfg = ec.load_ext_config(args.config)
    pins = ec.pins_ok(cfg)
    wman = json.loads((args.witness / "run_manifest.json").read_text(encoding="utf-8")) \
        if (args.witness / "run_manifest.json").exists() else \
        json.loads(sorted((args.witness / "_manifests").glob("shard_*/run_manifest.json"))[0].read_text(encoding="utf-8"))
    wsettings = WitnessSettings(**{k: v for k, v in wman["settings"].items() if k not in RUN_ONLY})
    settings = A2Settings(cover_k=args.cover_k)
    policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=True)
    policy.activate()
    report = canary.require_canary(policy=policy, timeout_s=cfg.execution.timeout_s, warmup=True)
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    dev = list(cfg.extensions.development_tasks)
    labels = (dev if args.tasks == ["dev"] else sorted(set(tasks) - set(dev)) if args.tasks == ["eval"]
              else args.tasks)[args.shard::args.shards]
    split_groups, _ = load_split(ec.PROTOCOL_DIR / "fault_split_v1.json")
    spec = json.loads(OUTPUT_SPEC.read_text(encoding="utf-8")) if OUTPUT_SPEC.exists() else {"tasks": {}}
    bench = get_benchmark(cfg)
    baseline = Path(cfg.extensions.baseline_scores)
    args.out.mkdir(parents=True, exist_ok=True)
    failed = []
    for lab in labels:
        f = args.out / lab / "a2.json"
        wf = args.witness / lab / "witness.json"
        if (f.exists() and not args.force) or not wf.exists():
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        try:
            res = run_task(json.loads(wf.read_text(encoding="utf-8")), tasks[lab], bench, baseline, split_groups,
                           settings, cfg.extensions.seed, wsettings, cfg.execution.timeout_s, spec, lab in dev)
        except Exception:
            (f.parent / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            print(f"[{lab}] FAILED: see {f.parent / 'error.txt'}", flush=True)
            failed.append(lab)
            continue
        (f.parent / "error.txt").unlink(missing_ok=True)
        if res.get("final_code"):
            (f.parent / "hidden_tests.py").write_text(res["final_code"], encoding="utf-8")
        f.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        print(f"[{lab}] ready={res['ready']} tests={len(res.get('final_tests', []))} "
              f"discovery={len(res.get('discovery_groups', []))} reason={res.get('reason')}", flush=True)
    write_run_manifest(
        args.out if args.shards == 1 else args.out / "_manifests" / f"shard_{args.shard}",
        stage="stage4_a2", config_path=args.config,
        inputs={"fault_split": ec.PROTOCOL_DIR / "fault_split_v1.json", "output_spec": [OUTPUT_SPEC],
                "witness": [args.witness / lab / "witness.json" for lab in labels if (args.witness / lab / "witness.json").exists()],
                "contracts": [ec.PROTOCOL_DIR / "contracts_v1" / "reviewed"],
                "benchmark_data": [cfg.benchmark.data_path]},
        seeds={"extension_seed": cfg.extensions.seed}, settings={"a2": dataclasses.asdict(settings),
                                                                  "witness": dataclasses.asdict(wsettings),
                                                                  "tasks": labels, "gated": gated},
        checks={"pins": pins, "canary": report, "failed_tasks": failed}, argv=sys.argv if argv is None else argv)
    if args.shards == 1:
        print(json.dumps(summarise(args.out), indent=1))
    return int(bool(failed))


if __name__ == "__main__":
    sys.exit(main())
