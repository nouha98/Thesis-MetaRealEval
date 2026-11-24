"""Stage 2 witness search (plan rev. 9.3) -- development pilot first, full run after gate G2.

    # development pilot (gate G2 input)
    python scripts/run_witness.py --config config/tier2_extensions.yaml --tasks dev \
        --out results_tier2_ext/witness/dev_pilot_freia [--ungated] [--workers 6]
    # full run on the 351 evaluation tasks (needs the passed G2 record; SLURM array shards)
    python scripts/run_witness.py --config config/tier2_extensions.yaml --tasks eval \
        --g2 results_tier2_ext/witness/dev_pilot_freia/G2.json --out results_tier2_ext/witness/full \
        --shard 0 --shards 8
    # merge the shards
    python scripts/run_witness.py --config config/tier2_extensions.yaml --out results_tier2_ext/witness/full --summarise

Only REVIEWED contracts count (plan D2): a supported draft is treated as unsupported ("contract
not reviewed"); a rejected contract is stored as reviewed + unsupported. A full run uses exactly
the witness settings of the G2 pilot. Finished tasks are skipped (rerun the same command to resume).

Per task: load the contract (reviewed if present, else the draft, recorded), build the P and
generated pools, run the reference twice, then search every fault group of the FROZEN split
(config/extensions_protocol/fault_split_v1.json; the representative program is re-collected from
the frozen baseline and must match the frozen code hash). Writes <out>/<task>/witness.json,
<out>/summary.json, <out>/summary.md and <out>/run_manifest.json (with the execution canary,
pins and every setting).

Without the gate manifest (--ungated, local) gate-excluded P scenarios cannot be removed: the
run is marked non-authoritative. The canary requires credential scrubbing everywhere and, on
POSIX, descendant cleanup on every execution path.
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
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.benchmarks.contracts import contract_sha, load_contract  # noqa: E402
from meta_real_eval.benchmarks.witness import WitnessSettings, prepare_task, search_group  # noqa: E402
from meta_real_eval.core import canary  # noqa: E402
from meta_real_eval.core.provenance import write_run_manifest  # noqa: E402
from meta_real_eval.oracles.fault_groups import load_split  # noqa: E402

DRAFTS = ec.PROTOCOL_DIR / "contracts_v1" / "drafts"
REVIEWED = ec.PROTOCOL_DIR / "contracts_v1" / "reviewed"


def contract_for(label: str) -> tuple[dict, Path]:
    for d in (REVIEWED, DRAFTS):
        p = d / f"{label}.json"
        if p.exists():
            return load_contract(p), p
    raise SystemExit(f"ERROR: no contract for {label}; run scripts/draft_contracts.py first")


def reviewed_only(contract: dict) -> dict:
    """Only reviewed contracts count (plan D2): a supported draft becomes unsupported. Returns a copy."""
    if contract["review"]["status"] == "reviewed" or not contract["support"]["supported"]:
        return contract
    sup = contract["support"]
    return {**contract, "support": {**sup, "supported": False,
                                    "reasons": list(sup["reasons"]) + ["contract not reviewed (only reviewed contracts count)"]}}


def require_g2(path, settings: WitnessSettings, gated: bool) -> dict:
    """The full run needs a passed, authoritative G2 record with the same witness settings."""
    if path is None:
        raise SystemExit("ERROR: non-development tasks need --g2 <pilot>/G2.json (scripts/gate_g2.py) -- gate G2 first")
    if not gated:
        raise SystemExit("ERROR: a full run must be authoritative (gate manifest); --ungated is for development tasks")
    raw = Path(path).read_bytes()
    rec = json.loads(raw)
    if not (rec.get("passed") and rec.get("gated")):
        raise SystemExit(f"ERROR: {path}: G2 did not pass (or was not authoritative): {rec.get('failed_checks')}")
    if rec.get("witness_settings") != dataclasses.asdict(settings):
        raise SystemExit(f"ERROR: witness settings differ from the G2 pilot:\n  G2   {rec.get('witness_settings')}\n"
                         f"  now  {dataclasses.asdict(settings)}")
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def select_labels(spec: list[str], all_labels, development) -> list[str]:
    if spec == ["dev"]:
        return list(development)
    if spec == ["eval"]:
        return sorted(set(all_labels) - set(development))
    return list(spec)


def _search(args):
    ctx, gid, code = args
    return search_group(ctx, gid, code)


def run_task(label, task, bench, groups, split, baseline, settings, gated, workers) -> dict:
    contract, cpath = contract_for(label)
    excluded = set(task.meta.get("scenarios", {}).get("excluded", {})) if gated else set()
    t0 = time.monotonic()
    ctx = prepare_task(task, reviewed_only(contract), settings, excluded, gated)
    prep_s = time.monotonic() - t0
    records = {r["record_id"]: r for r in ec.collect_fault_records(bench, task, baseline)}
    hist = ec.historical_status(label, baseline)
    jobs, meta = [], []
    for gid, g in sorted(groups.get(label, {}).items()):
        rep = next((m for m in g["members"] if records.get(m["record_id"], {}).get("runnable")), g["members"][0])
        rec = records.get(rep["record_id"])
        if rec is None or __import__("hashlib").sha256(rec["code"].encode()).hexdigest() != rep["code_sha256"]:
            raise SystemExit(f"ERROR: {label}/{rep['record_id']}: code differs from the frozen split")
        jobs.append((ctx, gid, rec["code"] if rec["runnable"] else None))
        meta.append({"group_id": gid, "side": split[label][gid], "source": g["source"],
                     "representative": rep["record_id"],
                     "members": [{"record_id": m["record_id"], **hist.get(m["record_id"], {})} for m in g["members"]]})
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_search, jobs))
    else:
        results = [_search(j) for j in jobs]
    contract_rec = {"path": str(cpath.relative_to(ec.REPO)), "sha256": contract_sha(contract),
                    "status": contract["review"]["status"]}
    return {"task": label, "gated": gated, "contract": contract_rec, "support": ctx["support"],
            "runtime": ctx.get("runtime"), "prepare_seconds": round(prep_s, 1),
            "groups": [{**m, **r} for m, r in zip(meta, results)]}


def primary(g: dict) -> bool:
    return (g["outcome"] == "distinguished" and g["level"] == "api_visible" and g["domain"] == "valid"
            and (g.get("replay") or {}).get("confirmed", False))


def summarise(results: list[dict]) -> dict:
    groups = [g for r in results for g in r["groups"]]
    sup = [r for r in results if r["support"]["supported"]]
    by = lambda gs, key: dict(Counter(key(g) for g in gs))  # noqa: E731

    def cat(g):
        if g["outcome"] != "distinguished":
            return g["outcome"]
        return f"distinguished/{g['level']}/{g['domain']}" + (f"/{g['kind']}" if g.get("kind") else "")
    hist_eq = [g for g in groups if g["members"] and all(m.get("equivalence") in ("no_divergence", "no_testable_inputs")
                                                          for m in g["members"])]
    replays = [g for g in groups if g["outcome"] == "distinguished"]
    return {
        "tasks": len(results), "tasks_supported": len(sup),
        "unsupported_reasons": by([r for r in results if not r["support"]["supported"]],
                                  lambda r: "; ".join(r["support"]["reasons"])),
        "groups": len(groups), "groups_on_supported_tasks": sum(len(r["groups"]) for r in sup),
        "outcomes": by(groups, cat),
        "outcomes_by_source": {s: by([g for g in groups if g["source"] == s], cat)
                               for s in sorted({g["source"] for g in groups})},
        "primary_confirmed_groups": sum(primary(g) for g in groups),
        "historically_equivalent_groups_on_supported_tasks": sum(1 for g in hist_eq if g["outcome"] != "unsupported"),
        "of_which_primary_witness": sum(primary(g) for g in hist_eq),
        "of_which_unresolved": sum(g["outcome"] == "unresolved" for g in hist_eq),
        "witnesses_replayed": f"{sum((g.get('replay') or {}).get('confirmed', False) for g in replays)}/{len(replays)}",
        "witness_origin": by([g for g in groups if primary(g)], lambda g: g["origin"]),
        "contracts": by(results, lambda r: r["contract"]["status"]),
        "gated": all(r["gated"] for r in results),
        "seconds_total": round(sum(g.get("seconds") or 0 for g in groups) + sum(r["prepare_seconds"] for r in results), 1),
    }


def write_md(summary: dict, results: list[dict], path: Path) -> None:
    L = ["# Stage 2 witness pilot", "",
         f"*{'Authoritative (gate manifest)' if summary['gated'] else 'NON-AUTHORITATIVE local run (no gate manifest)'}; "
         f"contracts: {summary['contracts']}. No witness never means equivalent.*", "",
         f"- Tasks: {summary['tasks']}, supported {summary['tasks_supported']}. Unsupported: {summary['unsupported_reasons']}",
         f"- Fault groups: {summary['groups']} ({summary['groups_on_supported_tasks']} on supported tasks).",
         f"- Primary confirmed (API-visible, valid domain, replayed): **{summary['primary_confirmed_groups']}**; "
         f"origin {summary['witness_origin']}.",
         f"- Historically 'equivalent' groups on supported tasks: {summary['historically_equivalent_groups_on_supported_tasks']}, "
         f"of which primary witness {summary['of_which_primary_witness']}, unresolved {summary['of_which_unresolved']}.",
         f"- Witness replay: {summary['witnesses_replayed']}.", "", "## Outcomes", ""]
    for k, v in sorted(summary["outcomes"].items()):
        L.append(f"- {k}: {v}")
    L += ["", "## Per task", "", "| task | supported | groups | primary | unresolved | runtime | contract |",
          "|---|---|---|---|---|---|---|"]
    for r in results:
        gs = r["groups"]
        L.append(f"| {r['task']} | {r['support']['supported']} | {len(gs)} | {sum(primary(g) for g in gs)} | "
                 f"{sum(g['outcome'] == 'unresolved' for g in gs)} | {json.dumps(r['runtime']) if r['runtime'] else '-'} | "
                 f"{r['contract']['status']} |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_summary(out: Path) -> dict:
    """Merge every <out>/*/witness.json (all shards) into summary.json / summary.md."""
    results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out.glob("*/witness.json"))]
    summary = summarise(results)
    summary["failed_tasks"] = sorted(p.parent.name for p in out.glob("*/error.txt"))
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    write_md(summary, results, out / "summary.md")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--tasks", nargs="+", default=["dev"],
                    help="dev | eval (the 351 non-development tasks; needs --g2) | task labels")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--g2", type=Path, default=None, help="passed G2 record (scripts/gate_g2.py), for non-dev tasks")
    ap.add_argument("--ungated", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--pool-size", type=int, default=40)
    ap.add_argument("--max-calls", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--budget", type=float, default=300.0)
    ap.add_argument("--shard", type=int, default=0, help="SLURM array: process labels[shard::shards]")
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--force", action="store_true", help="recompute tasks that already have witness.json")
    ap.add_argument("--summarise", action="store_true", help="only merge <out>/*/witness.json into the summary")
    args = ap.parse_args(argv)
    if args.summarise:
        print(json.dumps(write_summary(args.out), indent=1))
        return 0
    cfg = ec.load_ext_config(args.config)
    pins = ec.pins_ok(cfg)
    dev = cfg.extensions.development_tasks
    settings = WitnessSettings(pool_size=args.pool_size, max_calls=args.max_calls, timeout_s=args.timeout,
                               mutant_budget_s=args.budget, seed=cfg.extensions.seed)
    policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=True)
    policy.activate()
    # aborts on a leak (and on POSIX a surviving descendant); suite timeout + warm-up for cold cluster nodes
    report = canary.require_canary(policy=policy, timeout_s=cfg.execution.timeout_s, warmup=True)
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    ec.check_development_mapping(cfg, tasks, gated)
    all_labels = select_labels(args.tasks, tasks, dev)
    g2 = None if set(all_labels) <= set(dev) else require_g2(args.g2, settings, gated)
    labels = all_labels[args.shard::args.shards]
    groups, split = load_split(ec.PROTOCOL_DIR / "fault_split_v1.json")
    bench = get_benchmark(cfg)
    baseline = Path(cfg.extensions.baseline_scores)
    args.out.mkdir(parents=True, exist_ok=True)
    failed = []
    for lab in labels:
        f = args.out / lab / "witness.json"
        if f.exists() and not args.force:
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        t = time.monotonic()
        try:
            res = run_task(lab, tasks[lab], bench, groups, split, baseline, settings, gated, args.workers)
        except Exception:                                  # one task must not stop the others; rerun it later
            (f.parent / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            print(f"[{lab}] FAILED: see {f.parent / 'error.txt'}", flush=True)
            failed.append(lab)
            continue
        (f.parent / "error.txt").unlink(missing_ok=True)
        f.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        print(f"[{lab}] supported={res['support']['supported']} groups={len(res['groups'])} "
              f"primary={sum(primary(g) for g in res['groups'])} ({time.monotonic() - t:.0f}s)", flush=True)
    write_run_manifest(
        args.out if args.shards == 1 else args.out / "_manifests" / f"shard_{args.shard}",
        stage="stage2_witness", config_path=args.config,
        inputs={"fault_split": ec.PROTOCOL_DIR / "fault_split_v1.json",
                "contracts": [p for p in (REVIEWED, DRAFTS) if p.exists()],
                "stage0": [baseline / "stage0" / lab for lab in labels],
                "rq1": [baseline / "rq1" / ph / lab for ph in ("generate", "evaluate") for lab in labels],
                "benchmark_data": [cfg.benchmark.data_path]},
        seeds={"extension_seed": cfg.extensions.seed}, settings={**dataclasses.asdict(settings), "tasks": labels,
                                                                  "gated": gated, "workers": args.workers},
        checks={"pins": pins, "canary": report, "g2": g2, "failed_tasks": failed},
        argv=sys.argv if argv is None else argv)
    if args.shards == 1:
        print(json.dumps(write_summary(args.out), indent=1))
    if failed:
        print(f"{len(failed)} task(s) failed (rerun the same command; finished tasks are skipped): {failed}")
    return int(bool(failed))


if __name__ == "__main__":
    sys.exit(main())
