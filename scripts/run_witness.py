"""Stage 2 witness search (plan rev. 9) -- development pilot first.

    python scripts/run_witness.py --config config/tier2_extensions.yaml --tasks dev \
        --out results_tier2_ext/witness/dev_pilot [--ungated] [--workers 6]

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
import json
import os
import sys
import time
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


def _search(args):
    ctx, gid, code = args
    return search_group(ctx, gid, code)


def run_task(label, task, bench, groups, split, baseline, settings, gated, workers) -> dict:
    contract, cpath = contract_for(label)
    excluded = set(task.meta.get("scenarios", {}).get("excluded", {})) if gated else set()
    t0 = time.monotonic()
    ctx = prepare_task(task, contract, settings, excluded, gated)
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--tasks", nargs="+", default=["dev"], help="dev | task labels (full runs come after gate G2)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ungated", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--pool-size", type=int, default=40)
    ap.add_argument("--max-calls", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--budget", type=float, default=300.0)
    args = ap.parse_args(argv)
    cfg = ec.load_ext_config(args.config)
    pins = ec.pins_ok(cfg)
    if args.tasks != ["dev"] and not set(args.tasks) <= set(cfg.extensions.development_tasks):
        raise SystemExit("ERROR: only development tasks before gate G2 (no full run yet)")
    policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=True)
    policy.activate()
    report = canary.require_canary(policy=policy)            # aborts on a leak (and on POSIX a survivor)
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    ec.check_development_mapping(cfg, tasks, gated)
    groups, split = load_split(ec.PROTOCOL_DIR / "fault_split_v1.json")
    settings = WitnessSettings(pool_size=args.pool_size, max_calls=args.max_calls, timeout_s=args.timeout,
                               mutant_budget_s=args.budget, seed=cfg.extensions.seed)
    labels = list(cfg.extensions.development_tasks) if args.tasks == ["dev"] else args.tasks
    bench = get_benchmark(cfg)
    baseline = Path(cfg.extensions.baseline_scores)
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    for lab in labels:
        t = time.monotonic()
        res = run_task(lab, tasks[lab], bench, groups, split, baseline, settings, gated, args.workers)
        (args.out / lab).mkdir(parents=True, exist_ok=True)
        (args.out / lab / "witness.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        results.append(res)
        print(f"[{lab}] supported={res['support']['supported']} groups={len(res['groups'])} "
              f"primary={sum(primary(g) for g in res['groups'])} ({time.monotonic() - t:.0f}s)", flush=True)
    summary = summarise(results)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    write_md(summary, results, args.out / "summary.md")
    write_run_manifest(
        args.out, stage="stage2_witness", config_path=args.config,
        inputs={"fault_split": ec.PROTOCOL_DIR / "fault_split_v1.json",
                "contracts": [p for p in (REVIEWED, DRAFTS) if p.exists()],
                "stage0": [baseline / "stage0" / lab for lab in labels],
                "rq1": [baseline / "rq1" / ph / lab for ph in ("generate", "evaluate") for lab in labels],
                "benchmark_data": [cfg.benchmark.data_path]},
        seeds={"extension_seed": cfg.extensions.seed}, settings={**dataclasses.asdict(settings), "tasks": labels,
                                                                  "gated": gated, "workers": args.workers},
        checks={"pins": pins, "canary": report}, argv=sys.argv if argv is None else argv)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
