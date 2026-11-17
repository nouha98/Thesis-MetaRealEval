"""Freeze the extension protocol artifacts (plan rev. 9, D4-D5 and the RQ3 population).

    python scripts/freeze_protocol.py --config config/tier2_extensions.yaml [--ungated]
    python scripts/freeze_protocol.py --config config/tier2_extensions.yaml --check   # on freia

Writes (once; refuses to overwrite without --force) into config/extensions_protocol/:

  cohorts_v1.json         development tasks; the frozen audit ORDER over the other tasks (the
                          audit-reserved set = the first 20 tasks of this order that are H-ready
                          at gate G4); the evaluation candidates
  rq3_population_v1.json  the RQ3 task-level scoring population (the tau_div held-out split,
                          recomputed with the calibration script's own function), each task's
                          stored divergence score, the solution-level units, and the rules that
                          finish the population at G4 (minus audit-reserved, H-ready only)
  fault_split_v1.json     fault groups of every stored mutant record and their frozen
                          discovery / held-out side (decided from programs only, before any
                          Stage 2 outcome)
  protocol_manifest.json  sha256 of each artifact, input digests, git state, gated or not

Nothing here runs generated code or reads an outcome that the split or cohorts could depend on.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.analysis.calibration import stratified_calibration_split  # noqa: E402
from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.provenance import digest_files, git_state  # noqa: E402
from meta_real_eval.oracles import fault_groups as FG  # noqa: E402

AUDIT_RESERVED_N = 20
FILES = ("cohorts_v1.json", "rq3_population_v1.json", "fault_split_v1.json")


def sha_of(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def diff_paths(a, b, path="", out=None, limit=25) -> list[str]:
    """Where two JSON documents differ (first ``limit`` paths), for --check reports."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'recomputed' if k in b else 'frozen'}")
            elif a[k] != b[k]:
                diff_paths(a[k], b[k], f"{path}/{k}", out, limit)
            if len(out) >= limit:
                break
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                diff_paths(x, y, f"{path}[{i}]", out, limit)
            if len(out) >= limit:
                break
    else:
        out.append(f"{path}: frozen {json.dumps(a, default=str)[:120]} | recomputed {json.dumps(b, default=str)[:120]}")
    return out


def audit_order(labels: list[str], split_of: dict, seed: int) -> list[str]:
    """Seeded order, stratified: each prefix keeps the csn / post_cut-off shares as closely as possible."""
    by: dict[str, list[str]] = {}
    for lab in sorted(labels):
        by.setdefault(split_of[lab], []).append(lab)
    for s, lst in by.items():
        random.Random(f"{seed}:audit:{s}").shuffle(lst)
    n = len(labels)
    share = {s: len(v) / n for s, v in by.items()}
    taken = {s: 0 for s in by}
    order = []
    for pos in range(n):
        s = max((s for s in by if taken[s] < len(by[s])),
                key=lambda s: (share[s] * (pos + 1) - taken[s], s))
        order.append(by[s][taken[s]])
        taken[s] += 1
    return order


def cohorts(cfg, tasks: dict) -> dict:
    ext = cfg.extensions
    dev = list(ext.development_tasks)
    missing = sorted(set(dev) - set(tasks))
    if missing:
        raise SystemExit(f"ERROR: development tasks not among the loaded tasks: {missing}")
    rest = sorted(set(tasks) - set(dev))
    split_of = {lab: t.split for lab, t in tasks.items()}
    order = audit_order(rest, split_of, ext.seed)
    return {
        "format": 1, "seed": ext.seed,
        "development": {"labels": dev, "indices": ext.development_task_indices,
                        "rule": "all policy tuning (prompts, contracts, admission rules, canonical-H rule inputs)"},
        "audit_order": order,
        "audit_reserved_rule": (f"the first {AUDIT_RESERVED_N} tasks of audit_order that are H-ready at gate G4 "
                                "(H constructed and admitted); whole tasks; excluded from the Stage 5 and RQ5 "
                                "confirmatory cohorts"),
        "evaluation_candidates": rest,
        "evaluation_cohort_rule": "evaluation_candidates minus audit-reserved, H-ready only (materialised at G4)",
        "split_counts": {s: sum(split_of[x] == s for x in rest) for s in sorted(set(split_of.values()))},
    }


def rq3_population(cfg, tasks: dict, baseline: Path, coh: dict) -> dict:
    """Recompute the tau_div calibration / held-out split exactly as scripts/calibrate_tau_div_tier2.py."""
    scores, solutions, split_of = {}, {}, {}
    for lab, t in tasks.items():
        dv = ec.read_json(baseline / "rq3" / "execute" / lab / "divergence.json", None)
        if not dv:
            continue
        sols = [s for s in dv.get("solutions", []) if "passes_benchmark" in s]
        if dv.get("pairwise_disagreement_rate") is None or not sols:
            continue
        scores[t.task_id] = {"label": lab, "pairwise_disagreement_rate": dv["pairwise_disagreement_rate"],
                             "n_solutions": dv["n_solutions"], "n_comparable_pairs": dv["n_comparable_pairs"],
                             "n_inputs": dv["n_inputs"], "selected_relations": dv["selected_relations"]}
        solutions[t.task_id] = [{"relation": s["relation"], "model": s["model"], "passes_P": s["passes_benchmark"]}
                                for s in sols]
        split_of[t.task_id] = t.split or "unknown"
    ids = sorted(scores)
    forced = [tasks[lab].task_id for lab in cfg.extensions.development_tasks]
    cal, held = stratified_calibration_split(ids, [split_of[i] for i in ids], seed=cfg.project.seed,
                                             force_calibration=forced)
    record = ec.read_json(ec.REPO / "data" / "realclasseval" / "tau_div_calibration.json", None)
    record_check = None
    if record is not None:
        rec_held = record.get("holdout_task_ids") or record.get("heldout_task_ids") or record.get("holdout_ids")
        record_check = {"record_found": True, "holdout_matches": sorted(rec_held or []) == sorted(held),
                        "record_holdout_n": len(rec_held or [])}
    held_labels = [scores[i]["label"] for i in held]
    return {
        "format": 1,
        "tau_div": cfg.rq3.divergence_threshold,
        "split": {"seed": cfg.project.seed, "forced_calibration": forced, "n_calibration": len(cal),
                  "n_held_out": len(held), "recomputed_with": "analysis.calibration.stratified_calibration_split",
                  "calibration_record_check": record_check or {"record_found": False,
                                                               "note": "verify with --check on freia"}},
        "task_level": {
            "unit": "task",
            "score": "RQ3 pairwise_disagreement_rate (stored divergence.json, full_v4)",
            "label_primary": "1 if >=1 RQ3-scored solution passes P and fails canonical H (operational "
                             "disagreement with the validated hidden oracle), else 0",
            "label_secondary": "1 if >=1 RQ3-scored solution fails P-and-H combined",
            "metrics": "AUC on the continuous score; sensitivity/specificity/J only at the frozen tau_div",
            "population_rule": "held-out split tasks, minus audit-reserved tasks, H-ready only (applied at G4); "
                               "development tasks are all in the calibration half",
            "tasks": {scores[i]["label"]: {k: v for k, v in scores[i].items() if k != "label"} for i in held},
        },
        "solution_level": {
            "unit": "an RQ3-scored representative solution (relation x model) that passes P",
            "score": "that solution's disagreement rate with the other scored solutions of its task on the RQ3 "
                     "shared pool (recomputed in Stage 5 from re-executed traces, same pool seed and size)",
            "label": "1 if it fails canonical H",
            "metrics": "AUC with task-cluster bootstrap; the task-level tau_div is never applied",
            "units": {scores[i]["label"]: [s for s in solutions[i] if s["passes_P"]] for i in held},
        },
        "sensitivity": "label-independent representative (first completion of each relation x model)",
        "held_out_labels": held_labels,
        "development_in_calibration": all(f in cal for f in forced),
    }


def fault_split(cfg, tasks: dict, baseline: Path) -> dict:
    bench = get_benchmark(cfg)
    records = []
    for lab in sorted(tasks):
        records += ec.collect_fault_records(bench, tasks[lab], baseline)
    groups = FG.build_groups(records)
    split = FG.freeze_split(groups, cfg.extensions.seed)
    prov = {"n_records": len(records), "n_unrunnable_records": sum(not r["runnable"] for r in records),
            "normalisation": "ast.unparse after docstring stripping (fault_groups.normalise_program)"}
    return FG.split_document(groups, split, cfg.extensions.seed, prov)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--ungated", action="store_true", help="no gate manifest available (local machine)")
    ap.add_argument("--check", action="store_true", help="recompute and compare with the frozen files; write nothing")
    ap.add_argument("--force", action="store_true", help="overwrite frozen files (never after Stage 2 starts)")
    args = ap.parse_args(argv)
    cfg = ec.load_ext_config(args.config)
    pins = ec.pins_ok(cfg)
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    ec.check_development_mapping(cfg, tasks, gated)
    baseline = Path(cfg.extensions.baseline_scores)
    coh = cohorts(cfg, tasks)
    docs = {"cohorts_v1.json": coh, "rq3_population_v1.json": rq3_population(cfg, tasks, baseline, coh),
            "fault_split_v1.json": fault_split(cfg, tasks, baseline)}
    if args.check:
        bad = []
        for name, doc in docs.items():
            frozen = ec.read_json(ec.PROTOCOL_DIR / name, None)
            if frozen is None:
                bad.append(f"{name}: not frozen yet")
            elif sha_of(frozen) != sha_of(doc):
                # round-trip the recomputation through JSON so tuples/ints compare like the frozen file
                d = diff_paths(frozen, json.loads(json.dumps(doc, sort_keys=True)))
                bad.append(f"{name}: recomputation differs from the frozen file; first differences: {d}")
        rc = docs["rq3_population_v1.json"]["split"]["calibration_record_check"]
        print(json.dumps({"gated": gated, "pins": pins, "calibration_record": rc, "problems": bad}, indent=1))
        return 1 if bad or (rc.get("record_found") and not rc.get("holdout_matches")) else 0
    ec.PROTOCOL_DIR.mkdir(parents=True, exist_ok=True)
    existing = [n for n in FILES if (ec.PROTOCOL_DIR / n).exists()]
    if existing and not args.force:
        raise SystemExit(f"ERROR: frozen artifacts already exist: {existing} (use --check to verify)")
    for name, doc in docs.items():
        (ec.PROTOCOL_DIR / name).write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    manifest = {
        "format": 1, "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gated": gated, "git": git_state(), "pins": pins, "config": str(args.config),
        "artifacts": {n: {"sha256_canonical": sha_of(docs[n]),
                          "file_sha256": hashlib.sha256((ec.PROTOCOL_DIR / n).read_bytes()).hexdigest()} for n in FILES},
        "inputs": {k: {kk: vv for kk, vv in digest_files([baseline / k]).items() if kk != "files"}
                   for k in ("stage0", "rq1/generate", "rq3/execute")},
        "note": ("frozen without the gate manifest (local); confirm with --check on freia before Stage 2 results "
                 "are reported" if not gated else "frozen with the gate manifest"),
    }
    (ec.PROTOCOL_DIR / "protocol_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    fs, rq = docs["fault_split_v1.json"], docs["rq3_population_v1.json"]
    print(f"cohorts: {len(coh['development']['labels'])} development, {len(coh['evaluation_candidates'])} evaluation "
          f"candidates {coh['split_counts']}")
    print(f"rq3: calibration {rq['split']['n_calibration']} / held-out {rq['split']['n_held_out']}; "
          f"development in calibration: {rq['development_in_calibration']}")
    print(f"fault split: {fs['provenance']['n_records']} records -> "
          f"{sum(len(g) for g in fs['tasks'].values())} groups; counts {fs['counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
