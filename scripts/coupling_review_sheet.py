"""Qualitative review sheet for 50 uncoupled fault classes (protocol 9.5, frozen guide; read-only).

    python scripts/coupling_review_sheet.py --config config/tier2_extensions.yaml --run results_tier2_ext/coupling/full

Population: contributing fault classes with no strictly coupled goal from either source (un-equalised
max pc < 1 for operator goals and for cross-model-eligible LLM goals). Strata: provenance pattern
(one per single model, one for classes written by several models); proportional allocation, largest
remainder; within a stratum the order is sha256(extension seed | "qualitative" | task | class id).

Writes <run>/qualitative/: sheet.md (one case per class: the solution's diff against the reference,
a detecting scenario, the nearest operator and LLM mutant with pc and diff), sample.json, and
classification.csv to fill in. Also prints the hidden-fault tasks of secondary (c). Regenerates the
primary pools of the sampled tasks (runs the reference under the execution policy); computes no
coupling value and changes no frozen number.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import difflib
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_coupling as ac  # noqa: E402
import ext_common as ec  # noqa: E402
from run_coupling import mutant_programs, solution_programs  # noqa: E402
from run_witness import contract_for  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.benchmarks.detection import prepare_primary  # noqa: E402
from meta_real_eval.core import canary  # noqa: E402
from meta_real_eval.oracles.coupling import SOURCES, SPEC, bits, dedup, eligible, fault_category, pc  # noqa: E402
from meta_real_eval.oracles.fault_groups import load_split  # noqa: E402

N_SAMPLE = 50
GUIDE = """**Guide (frozen 2026-11-22, protocol 9.5).** Pick ONE category; when two could apply, take the first in this order:
1. **reference-specific / not a real fault**: the detected difference is on an output that the docstring or contract leaves unspecified, or where the reference contradicts the docstring;
2. **no applicable operator**: no mutation operator could produce this fault;
3. **missing operator**: an operator could exist but the operator set lacks it;
4. **weak operator**: an applicable operator exists, but its mutants are not coupled (nearest pc < 1);
5. **unclear**: the evidence is not enough to decide."""


def classes_of(det: dict) -> tuple[list[dict], int]:
    """(uncoupled classes, number of contributing classes) for one task, as in 9.2 / 9.4."""
    tests, muts, sols, _ = ac.inputs(det)
    ids = sorted(tests)
    index, n = {t: i for i, t in enumerate(ids)}, len(ids)
    if n == 0:
        return [], 0
    for x in muts + sols:
        x["bits"] = bits(x["detect"], index)
    classes = dedup([s for s in sols if fault_category(s["bits"], n, s["invalid"]) == "near_miss"])
    found = {src: [m for m in muts if m["source"] == src and m["bits"]] for src in SOURCES}
    if not classes or not found["operator"] or not found["llm_whole"]:
        return [], 0
    out, n_contrib = [], 0
    for c in classes:
        pools = {"operator": found["operator"], "llm_whole": eligible(found["llm_whole"], c["models"])}
        if not pools["llm_whole"]:
            continue
        n_contrib += 1
        near = {src: min(ms, key=lambda m: (-pc(m["bits"], c["bits"]), -(m["bits"] & c["bits"]).bit_count(),
                                            m["bits"].bit_count(), m["id"]))
                for src, ms in pools.items()}
        if all(pc(near[s]["bits"], c["bits"]) < 1.0 for s in SOURCES):
            out.append({"task": det["task"], "class_id": min(c["ids"]), "ids": sorted(c["ids"]),
                        "models": sorted(c["models"]), "n_detecting": c["bits"].bit_count(), "n_tests": n,
                        "detecting_tests": [t for t in ids if c["bits"] >> index[t] & 1],
                        "nearest": {s: {"id": near[s]["id"], "pc": pc(near[s]["bits"], c["bits"]),
                                        "n_kill": near[s]["bits"].bit_count(),
                                        "n_overlap": (near[s]["bits"] & c["bits"]).bit_count()} for s in SOURCES}})
    return out, n_contrib


def hash_key(c: dict, seed: int) -> str:
    return hashlib.sha256(f"{seed}|qualitative|{c['task']}|{c['class_id']}".encode()).hexdigest()


def capped_pool(pop: list[dict], seed: int) -> tuple[list[dict], int]:
    """Amendment 2026-11-22: the smallest per-task cap that still leaves N_SAMPLE classes; within a task
    the first `cap` classes in hash order are kept. Each class records its inclusion probability."""
    by_task = defaultdict(list)
    for c in pop:
        by_task[c["task"]].append(c)
    cap = next(k for k in range(1, len(pop) + 1) if sum(min(len(v), k) for v in by_task.values()) >= N_SAMPLE)
    pool = []
    for v in by_task.values():
        for c in sorted(v, key=lambda c: hash_key(c, seed))[:cap]:
            c["p_pool"] = min(len(v), cap) / len(v)
            pool.append(c)
    return pool, cap


def sample(pop: list[dict], seed: int) -> list[dict]:
    strata = defaultdict(list)
    for c in pop:
        c["stratum"] = c["models"][0] if len(c["models"]) == 1 else "multi"
        strata[c["stratum"]].append(c)
    quota = {s: N_SAMPLE * len(v) / len(pop) for s, v in strata.items()}
    alloc = {s: int(q) for s, q in quota.items()}
    for s in sorted(quota, key=lambda s: (-(quota[s] - alloc[s]), s))[:N_SAMPLE - sum(alloc.values())]:
        alloc[s] += 1                                     # largest remainder
    out = [c for s in sorted(strata) for c in sorted(strata[s], key=lambda c: hash_key(c, seed))[:alloc[s]]]
    for c in out:   # inclusion probability and design weight (for estimates re-weighted to the population)
        c["p_inclusion"] = c.get("p_pool", 1.0) * alloc[c["stratum"]] / len(strata[c["stratum"]])
        c["weight"] = 1.0 / c["p_inclusion"]
    return out


def diff(a: str, b: str, limit: int) -> str:
    lines = list(difflib.unified_diff(a.splitlines(), b.splitlines(), "reference", "program", n=2, lineterm=""))
    return "\n".join(lines[:limit] + ([f"... ({len(lines) - limit} more lines)"] if len(lines) > limit else []))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=Path("config/tier2_extensions.yaml"))
    ap.add_argument("--run", type=Path, default=Path("results_tier2_ext/coupling/full"))
    ap.add_argument("--ungated", action="store_true")
    ap.add_argument("--no-cap", action="store_true", help="the first design (no per-task cap), written to qualitative_v1/")
    args = ap.parse_args()
    cfg = ec.load_ext_config(args.config)
    dev = set(cfg.extensions.development_tasks)
    dets = {d["task"]: d for d in ac.load_run(args.run) if d["task"] not in dev}

    hidden = ac._row_set(list(dets.values()), dev, fault_filter=lambda s: s["p_pass"] is True,
                         mutant_filter=lambda m: m["p_live"] is True, counts_only=True)
    print("secondary (c) hidden-fault tasks:", sorted(r["task"] for r in hidden if r["excluded"] is None))

    pop, n_contrib = [], 0
    for det in dets.values():
        u, n = classes_of(det)
        pop += u
        n_contrib += n
    print(f"contributing fault classes {n_contrib}; uncoupled {len(pop)} (endpoints: 215 and 215 - 117 = 98)")
    per_task = defaultdict(int)
    for c in pop:
        per_task[c["task"]] += 1
        c["stratum"] = c["models"][0] if len(c["models"]) == 1 else "multi"   # for every class, not only the pool
    print("uncoupled classes per task:", dict(sorted(per_task.items(), key=lambda kv: -kv[1])))
    if args.no_cap:          # the first (frozen) design, kept for reproducibility
        picked = sample(pop, cfg.extensions.seed)
    else:
        pool, cap = capped_pool(pop, cfg.extensions.seed)
        print(f"per-task cap {cap}: {len(pool)} classes in the capped pool")
        picked = sample(pool, cfg.extensions.seed)
    print("cases per task:", dict(sorted(defaultdict(int, {t: sum(c['task'] == t for c in picked)
                                                          for t in {c['task'] for c in picked}}).items(),
                                         key=lambda kv: -kv[1])))
    print("strata (sampled/population):", {s: f"{sum(c['stratum'] == s for c in picked)}/"
                                              f"{sum(c['stratum'] == s for c in pop)}"
                                           for s in sorted({c['stratum'] for c in pop})})

    policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=True)
    policy.activate()
    canary.require_canary(policy=policy, timeout_s=cfg.execution.timeout_s, warmup=True)
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    bench, baseline = get_benchmark(cfg), Path(cfg.extensions.baseline_scores)
    groups, _ = load_split(ec.PROTOCOL_DIR / "fault_split_v1.json")
    sp = SPEC["primary_pool"]
    out_dir = args.run / ("qualitative_v1" if args.no_cap else "qualitative")
    out_dir.mkdir(parents=True, exist_ok=True)
    md = ["# Coupling: qualitative review of uncoupled fault classes (protocol 9.5)", "",
          f"{len(picked)} of {len(pop)} uncoupled classes (of {n_contrib} contributing). Classify in "
          "`classification.csv`.", "", GUIDE, ""]
    by_task = defaultdict(list)
    for i, c in enumerate(picked, 1):
        c["case"] = i
        by_task[c["task"]].append(c)
    for label in sorted(by_task):
        task = tasks[label]
        contract, _ = contract_for(label)
        excluded = set(task.meta.get("scenarios", {}).get("excluded", {})) if gated else set()
        ctx = prepare_primary(task, contract, sp["n_generated"], cfg.extensions.seed + sp["seed_offset"],
                              excluded, gated, sp["timeout_s"], sp["max_calls"])
        steps = {f"{pool}:{e['scenario']['scenario_id']}": [s["src"] for s in e["scenario"]["steps"]]
                 for pool, p in ctx["pools"].items() for e in p["entries"]}
        code = {m["id"]: src for m, src in solution_programs(label, task, bench, baseline)[0]}
        code |= {m["id"]: src for m, src in mutant_programs(label, task, bench, groups, baseline)}
        progs = {p["id"]: p for p in dets[label]["programs"]}
        for c in by_task[label]:
            t = next((x for x in c["detecting_tests"] if x.startswith("p:")), c["detecting_tests"][0])
            detail = ((progs[c["class_id"]].get("primary") or {}).get("p_details") or {}).get(t)
            md += [f"## Case {c['case']}: {label}, class {c['class_id']}", "",
                   f"Written by: {', '.join(c['models'])} ({len(c['ids'])} solution group(s)); stratum {c['stratum']}. "
                   f"Detected by {c['n_detecting']} of {c['n_tests']} valid tests.", "",
                   f"**Detecting scenario** `{t}`" + (f" (difference: {detail})" if detail else ""), "",
                   "```python", *steps.get(t, ["(scenario not found)"]), "```", "",
                   "**Fault (solution vs reference)**", "", "```diff",
                   diff(task.reference_code, code.get(c["class_id"], ""), 80), "```", ""]
            for s in SOURCES:
                nm = c["nearest"][s]
                md += [f"**Nearest {s} mutant** `{nm['id']}`: pc = {nm['pc']:.3f} "
                       f"(kills {nm['n_kill']} tests, {nm['n_overlap']} of them also detect the fault)", "",
                       "```diff", diff(task.reference_code, code.get(nm["id"], "") or "", 40), "```", ""]
            md += ["Category: ______   Note: ______", "", "---", ""]
    (out_dir / "sheet.md").write_text("\n".join(md), encoding="utf-8")
    (out_dir / "sample.json").write_text(json.dumps(picked, indent=1), encoding="utf-8")
    with open(out_dir / "classification.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case", "task", "class_id", "stratum", "weight", "category", "note"])
        for c in picked:
            w.writerow([c["case"], c["task"], c["class_id"], c["stratum"], f"{c['weight']:.4f}", "", ""])
    print(f"wrote {out_dir}/sheet.md, sample.json, classification.csv ({len(picked)} cases, {len(by_task)} tasks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
