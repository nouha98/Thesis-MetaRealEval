"""Stage 2b: detection matrices for mutant-fault coupling (protocol_freeze_decisions.md section 9).

    python scripts/run_coupling.py --config config/tier2_extensions.yaml --tasks dev \
        --out results_tier2_ext/coupling/dev_pilot [--ungated] [--workers 6] [--no-perturbed]

Per task, every mutant group of the frozen fault split and every RQ2 solution group runs on:
  * the primary pool (P + 120 generated contract-valid scenarios; API-visible, valid domain), twice;
  * the perturbed-P pool (Stage 0 / RQ3 pool, observable builtin values only), twice;
  * the P suite with per-test D1 outcomes (needs the gate manifest; skipped with --ungated).
Writes <out>/<task>/detection.json and <out>/run_manifest.json. No coupling value is computed here.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402
from run_witness import contract_for  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.benchmarks.contracts import contract_sha  # noqa: E402
from meta_real_eval.benchmarks.detection import (  # noqa: E402
    perturbed_cells, prepare_perturbed, prepare_primary, primary_cells)
from meta_real_eval.core import canary  # noqa: E402
from meta_real_eval.core.provenance import write_run_manifest  # noqa: E402
from meta_real_eval.oracles.coupling import SPEC  # noqa: E402
from meta_real_eval.oracles.fault_groups import load_split  # noqa: E402
from meta_real_eval.oracles.solution_groups import build_solution_groups, digest  # noqa: E402
from meta_real_eval.rq2.evaluator import _warm_up  # noqa: E402

_W: dict = {}


def _init(cfg, task, ctx, pctx, p_timeout):
    _W.update(bench=get_benchmark(cfg), task=task, ctx=ctx, pctx=pctx, p_timeout=p_timeout)


def _err(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[-500:]


def _job(code):
    """Cells for one program. A runner-level failure (the fork runner timed out as a whole or
    died without traces -- e.g. heavy imports under a loaded node) is recorded per pool as
    ``<pool>_error`` with the cells set to None; it never fails the task."""
    t0 = time.monotonic()
    rec = {}
    try:
        rec["primary"] = primary_cells(_W["ctx"], code)
    except Exception as exc:
        rec["primary"], rec["primary_error"] = None, _err(exc)
    try:
        rec["perturbed"] = (perturbed_cells(_W["bench"], _W["task"], _W["pctx"], code)
                            if _W["pctx"] is not None else None)
    except Exception as exc:
        rec["perturbed"], rec["perturbed_error"] = None, _err(exc)
    rec["p_outcomes"] = rec["p_passed_all"] = None
    if code is not None and _W["p_timeout"]:
        try:
            r = _W["bench"].run_suite(_W["task"], code, _W["p_timeout"])
            rec["p_outcomes"] = {n: o.outcome for n, o in r.outcomes.items()}
            rec["p_passed_all"] = r.passed_all
        except Exception as exc:                        # ungated tasks have no gate verdicts
            rec["p_error"] = f"{type(exc).__name__}: {exc}"[:200]
    rec["seconds"] = round(time.monotonic() - t0, 2)
    return rec


def mutant_programs(label, task, bench, groups, baseline):
    records = {r["record_id"]: r for r in ec.collect_fault_records(bench, task, baseline)}
    hist = ec.historical_status(label, baseline)
    out = []
    for gid, g in sorted(groups.get(label, {}).items()):
        rep = next((m for m in g["members"] if records.get(m["record_id"], {}).get("runnable")), g["members"][0])
        rec = records.get(rep["record_id"])
        if rec is None:
            raise SystemExit(f"ERROR: {label}/{rep['record_id']}: no stored record under {baseline} (wrong baseline path?)")
        if hashlib.sha256(rec["code"].encode()).hexdigest() != rep["code_sha256"]:
            raise SystemExit(f"ERROR: {label}/{rep['record_id']}: code differs from the frozen split")
        models = sorted({m.get("model") for m in g["members"] if m.get("model")})
        out.append(({"kind": "mutant", "id": gid, "source": g["source"], "models": models,
                     "representative": rep["record_id"],
                     "historical_killed": hist.get(rep["record_id"], {}).get("killed")},
                    rec["code"] if rec["runnable"] else None))
    return out


def solution_programs(label, task, bench, baseline):
    comps = ec.read_json(baseline / "rq2" / "generate" / label / "completions.json", {})
    rates = ec.read_json(baseline / "rq2" / "evaluate" / label / "pass_rates.json", {})
    groups = build_solution_groups(label, comps, rates, lambda c: bench.build_solution(task, c))
    out = []
    for gid, g in groups.items():
        r = g["representative"]
        code = bench.build_solution(task, comps[r["relation"]][r["model"]][r["index"]])
        assert hashlib.sha256(code.encode()).hexdigest() == g["code_sha256"]
        out.append(({"kind": "solution", "id": gid, "models": g["models"], "members": g["members"]}, code))
    return out, digest(groups)


def run_task(label, task, cfg, bench, groups, baseline, gated, workers, perturbed) -> dict:
    t0 = time.monotonic()
    sp = SPEC["primary_pool"]
    try:
        contract, cpath = contract_for(label)
        crec = {"path": str(cpath.relative_to(ec.REPO)), "status": contract["review"]["status"],
                "sha256": contract_sha(contract)}
    except SystemExit:
        contract, crec = None, {"path": None, "status": "missing"}
    excluded = set(task.meta.get("scenarios", {}).get("excluded", {})) if gated else set()
    p_timeout = cfg.execution.timeout_s if gated else None
    if p_timeout:          # warm the import cache before the reference pools run (cold-node timeouts)
        _warm_up(bench, task, p_timeout, label)
    if contract is not None:
        ctx = prepare_primary(task, contract, sp["n_generated"], cfg.extensions.seed + sp["seed_offset"],
                              excluded, gated, sp["timeout_s"], sp["max_calls"])
    else:
        ctx = {"support": {"supported": False, "reasons": ["no contract"]}, "tests": {}}
    pctx, perturbed_error = None, None
    if perturbed:
        try:
            pctx = prepare_perturbed(bench, task, SPEC["perturbed_pool"]["n_items"], cfg.extensions.seed,
                                     sp["timeout_s"])
        except Exception as exc:                    # reference pool unrunnable: task has no perturbed tests
            perturbed_error = _err(exc)
            print(f"[{label}] perturbed pool unavailable: {perturbed_error[:200]}", flush=True)
    # the reference itself is the first program: gate GC requires its row to be clean in every pool
    progs = [({"kind": "reference", "id": "reference"}, task.reference_code)]
    progs += mutant_programs(label, task, bench, groups, baseline)
    sols, sol_digest = solution_programs(label, task, bench, baseline)
    progs += sols
    codes = [c for _, c in progs]
    while True:
        if workers > 1 and len(codes) > 1:
            try:
                with ProcessPoolExecutor(max_workers=workers, initializer=_init,
                                         initargs=(cfg, task, ctx, pctx, p_timeout)) as ex:
                    results = list(ex.map(_job, codes))
                break
            except BrokenProcessPool:                    # a worker died (e.g. memory: heavy imports x workers)
                print(f"[{label}] worker pool broke with {workers} workers; retrying with {max(1, workers // 4)}",
                      flush=True)
                workers = max(1, workers // 4)
                continue
        _init(cfg, task, ctx, pctx, p_timeout)
        results = [_job(c) for c in codes]
        break
    # runner-level failures under a loaded pool are as likely the machine as the program: re-run
    # each such program once, alone (same policy as RQ2's whole-suite-timeout re-run)
    rerun = [i for i, r in enumerate(results) if "primary_error" in r or "perturbed_error" in r]
    if rerun:
        print(f"[{label}] runner error on {len(rerun)} program(s); re-running them serially", flush=True)
        _init(cfg, task, ctx, pctx, p_timeout)
        for i in rerun:
            results[i] = {**_job(codes[i]), "runner_rerun": True}
    still = [progs[i][0]["id"] for i in rerun if "primary_error" in results[i] or "perturbed_error" in results[i]]
    if still:
        print(f"[{label}] {len(still)} program(s) still fail in the runner (recorded, excluded from "
              f"that pool's analysis): {still[:5]}", flush=True)
    return {"task": label, "gated": gated, "contract": crec, "support": ctx["support"], "workers_used": workers,
            "runtime": ctx.get("runtime"), "solution_groups_digest": sol_digest,
            "perturbed_error": perturbed_error, "runner_reruns": len(rerun), "runner_errors": still,
            "tests": {"primary": ctx["tests"],
                      "perturbed": sorted(pctx["tests"]) if pctx is not None else None},
            "programs": [{**meta, **res} for (meta, _), res in zip(progs, results)],
            "seconds": round(time.monotonic() - t0, 1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--tasks", nargs="+", default=["dev"], help="dev | all | task labels")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ungated", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--no-perturbed", action="store_true")
    ap.add_argument("--force", action="store_true", help="recompute tasks that already have detection.json")
    ap.add_argument("--shard", type=int, default=0, help="SLURM array: process labels[shard::shards]")
    ap.add_argument("--shards", type=int, default=1)
    args = ap.parse_args(argv)
    cfg = ec.load_ext_config(args.config)
    pins = ec.pins_ok(cfg)
    policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=True)
    policy.activate()
    report = canary.require_canary(policy=policy, timeout_s=cfg.execution.timeout_s, warmup=True)
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    ec.check_development_mapping(cfg, tasks, gated)
    groups, _ = load_split(ec.PROTOCOL_DIR / "fault_split_v1.json")
    labels = (list(cfg.extensions.development_tasks) if args.tasks == ["dev"]
              else sorted(tasks) if args.tasks == ["all"] else args.tasks)[args.shard::args.shards]
    bench = get_benchmark(cfg)
    baseline = Path(cfg.extensions.baseline_scores)
    missing = [d for d in ("stage0", "rq1/generate", "rq2/generate", "rq2/evaluate") if not (baseline / d).is_dir()]
    if missing:
        raise SystemExit(f"ERROR: baseline {baseline.resolve()} lacks {missing}; point extensions.baseline_scores "
                         "(or a symlink at that path) at the frozen Tier 2 results")
    args.out.mkdir(parents=True, exist_ok=True)
    spec_sha = hashlib.sha256(json.dumps(SPEC, sort_keys=True).encode()).hexdigest()
    failed = []
    for lab in labels:
        f = args.out / lab / "detection.json"
        if f.exists() and not args.force:
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        try:
            res = run_task(lab, tasks[lab], cfg, bench, groups, baseline, gated, args.workers, not args.no_perturbed)
        except Exception:                                  # one task must not stop the others; rerun it later
            (f.parent / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            print(f"[{lab}] FAILED: see {f.parent / 'error.txt'}", flush=True)
            failed.append(lab)
            continue
        (f.parent / "error.txt").unlink(missing_ok=True)
        res["spec_sha256"] = spec_sha
        f.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        print(f"[{lab}] supported={res['support']['supported']} tests={len(res['tests']['primary'])} "
              f"programs={len(res['programs'])} ({res['seconds']:.0f}s)", flush=True)
    write_run_manifest(
        args.out if args.shards == 1 else args.out / "_manifests" / f"shard_{args.shard}",
        stage="stage2b_coupling", config_path=args.config,
        inputs={"fault_split": ec.PROTOCOL_DIR / "fault_split_v1.json",
                "rq2": [baseline / "rq2" / ph / lab for ph in ("generate", "evaluate") for lab in labels],
                "benchmark_data": [cfg.benchmark.data_path]},
        seeds={"extension_seed": cfg.extensions.seed}, settings={"spec": SPEC, "spec_sha256": spec_sha,
                                                                  "tasks": labels, "gated": gated, "workers": args.workers},
        checks={"pins": pins, "canary": report, "failed_tasks": failed}, argv=sys.argv if argv is None else argv)
    if failed:
        print(f"{len(failed)} task(s) failed (rerun the same command; finished tasks are skipped): {failed}")
    return int(bool(failed))


if __name__ == "__main__":
    sys.exit(main())
