#!/usr/bin/env python
"""Audit the Stage 0 / RQ1 results on disk by recomputing what they claim.

Everything here is a *verification*, not an analysis: each check re-derives a
recorded fact and reports where the record and the recomputation disagree.
scripts/analyze_results.py aggregates results and trusts them; this script is
what earns that trust.

Checks
------
1. verdicts     Re-execute every kill_matrix.json row against the task's own
                suite and diff against the recorded is_killed.
2. invariant    Run the suite against every mutant excluded as *equivalent*.
                A kill is a contradiction: a mutant that behaves identically to
                the canonical solution cannot fail the tests canonical passes.
                Found 10 such mutants before equivalence.py grew its suite veto.
3. corpus       LLM mutant quality, no execution needed: AST-normalised
                duplication (siblings that are the same fault reworded),
                echoes of the canonical solution, and the distribution of edit
                sites per mutant as a check on "exactly ONE fault".
4. structure    Missing verdicts, orphan kill_matrix rows, and
                kill_rate_summary.json disagreeing with kill_matrix.json.
                An LLM mutant listed in llm_invalid_mutants.json was dropped
                by rq1/runner.py before evaluation (it cannot define the
                entry point even after repair) and correctly has no verdict
                and no kill_matrix row -- that is counted separately, not
                reported as a structural issue.
5. fuzz-power   (--fuzz-power, opt-in) How much discriminating power each
                task's fuzz set actually has: distinct canonical outputs, and
                the split between inputs captured from the benchmark's own
                check() and randomly generated padding. "500 inputs" overstates
                the evidence when the canonical solution returns the same value
                on nearly all of them. Costs ~n_fuzz_inputs x n_tasks
                subprocess spawns, so it is off by default.

Outputs
-------
results/audit/rq1_audit.json, plus a printed report. Exits non-zero when check
1 or 2 finds anything, so it can gate a re-run rather than be read by eye.

Usage
-----
    .venv/Scripts/python.exe scripts/audit_rq1.py
    .venv/Scripts/python.exe scripts/audit_rq1.py --tasks 38 50 61 119
    .venv/Scripts/python.exe scripts/audit_rq1.py --fuzz-power
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.config import Config                       # noqa: E402
from meta_real_eval.core.data_loader import load_humaneval, task_label  # noqa: E402
from meta_real_eval.core.sandbox import execute                     # noqa: E402
# The same normalisation the generator dedups with, imported rather than
# restated: if the two ever drifted, the audit would report a duplication rate
# the generator does not act on.
from meta_real_eval.rq1.llm_mutator import _normalise, repair_mutant_code  # noqa: E402
from meta_real_eval.stage0.equivalence import (                     # noqa: E402
    _capture_test_inputs,
    _generate_inputs,
    _run_one,
)

RESULTS = REPO_ROOT / "results"
TRADITIONAL_OPS = {"AOR", "ROR", "SDL"}


def load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Module level so ProcessPoolExecutor can pickle them on Windows.

def _kill_job(args: tuple) -> tuple:
    """Return (key, killed) for one mutant against its task's suite."""
    key, code, test_code, entry_point, timeout_s = args
    result = execute(code, f"{test_code}\ncheck({entry_point})\n", timeout_s)
    return key, not result.passed


def _canon_job(args: tuple) -> tuple:
    """Return (task_label, outputs) for the canonical solution over the fuzz set."""
    label, code, entry_point, inputs, timeout_s = args
    return label, [_run_one(code, entry_point, a, timeout_s) for a in inputs]


def _edit_sites(canonical: str, mutant: str) -> int:
    """Number of distinct AST-normalised hunks between canonical and mutant."""
    a, b = _normalise(canonical).splitlines(), _normalise(mutant).splitlines()
    return sum(1 for line in difflib.unified_diff(a, b, lineterm="", n=0)
               if line.startswith("@@"))


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def collect(tasks, cfg) -> dict:
    """Read every on-disk record once, and build the job lists from it."""
    kill_jobs, equiv_jobs = [], []
    recorded_kill, structure, corpus = {}, [], []
    n_excluded_invalid = 0

    for task in tasks:
        label = task_label(task)
        s0, gen, ev = (RESULTS / "stage0" / label,
                       RESULTS / "rq1" / "generate" / label,
                       RESULTS / "rq1" / "evaluate" / label)
        if not (s0 / "mutants.json").exists() or not (ev / "kill_matrix.json").exists():
            structure.append({"task": label, "issue": "missing stage0 or evaluate output"})
            continue

        trad = load(s0 / "mutants.json")
        trad_eq = {r["mutant_id"]: r for r in load(s0 / "equiv_filter.json")}
        llm = load(gen / "llm_mutants.json") if (gen / "llm_mutants.json").exists() else []
        llm_eq = ({r["mutant_id"]: r for r in load(ev / "llm_equiv_filter.json")}
                  if (ev / "llm_equiv_filter.json").exists() else {})
        km = load(ev / "kill_matrix.json")
        summary = load(ev / "kill_rate_summary.json") if (ev / "kill_rate_summary.json").exists() else {}

        # rq1/runner.py::run_evaluate_one repairs each LLM mutant's code in
        # memory (re-attaching prompt imports/helpers via repair_mutant_code)
        # before it is ever equivalence-checked or run against the suite, and
        # never writes the repaired source back to llm_mutants.json. A mutant
        # that needed repair to run at all is listed here so its stored (raw,
        # unrepaired) code is never mistaken for what was actually evaluated --
        # auditing the raw version instead reproduces nothing, because it is a
        # different, usually broken, program.
        invalid_path = ev / "llm_invalid_mutants.json"
        invalid_ids: set[str] = (
            set(load(invalid_path)["mutant_ids"]) if invalid_path.exists() else set()
        )

        code_of = {m["mutant_id"]: m["code"] for m in trad}
        for m in llm:
            mid = m["mutant_id"]
            if mid in invalid_ids:
                continue  # dropped before evaluation -- never had code to audit
            repaired = repair_mutant_code(m["code"], task.prompt, task.entry_point)
            # Should never be None here -- that is exactly what invalid_ids
            # already covers -- but if the two ever disagree, auditing the
            # stored code is closer to "what happened" than silently skipping
            # a mutant the pipeline actually did evaluate.
            code_of[mid] = repaired if repaired is not None else m["code"]
        km_ids = {r["mutant_id"] for r in km}

        # --- check 1 jobs: every recorded kill verdict ---
        for row in km:
            key = (label, row["mutant_id"])
            recorded_kill[key] = bool(row["is_killed"])
            if row["mutant_id"] in code_of:
                kill_jobs.append((key, code_of[row["mutant_id"]], task.test,
                                  task.entry_point, cfg.execution.timeout_s))
            else:
                structure.append({"task": label, "mutant": row["mutant_id"],
                                  "issue": "kill_matrix row has no source mutant"})

        # --- check 2 jobs: every mutant excluded as equivalent ---
        for mid, verdict in list(trad_eq.items()) + list(llm_eq.items()):
            if verdict.get("is_equivalent") and mid in code_of:
                equiv_jobs.append(((label, mid), code_of[mid], task.test,
                                   task.entry_point, cfg.execution.timeout_s))

        # --- check 4: structure ---
        # Mutants in invalid_ids were dropped before evaluation on purpose (see
        # above); they correctly have no equivalence verdict and no kill_matrix
        # row, so they are counted, not flagged as a structural issue.
        n_excluded_invalid += len(invalid_ids)
        for m in llm:
            mid = m["mutant_id"]
            if mid in invalid_ids:
                continue
            if mid not in llm_eq:
                structure.append({"task": label, "mutant": mid,
                                  "issue": "LLM mutant has no equivalence verdict"})
        for m in trad + llm:
            mid = m["mutant_id"]
            if mid in invalid_ids:
                continue
            eq = trad_eq.get(mid) or llm_eq.get(mid) or {}
            if not eq.get("is_equivalent") and mid not in km_ids:
                structure.append({"task": label, "mutant": mid,
                                  "issue": "non-equivalent mutant missing from kill_matrix"})
        recomputed = {}
        for row in km:
            slot = recomputed.setdefault(row["operator"], {"total": 0, "killed": 0})
            slot["total"] += 1
            slot["killed"] += int(row["is_killed"])
        for op, counts in recomputed.items():
            rec = summary.get(op)
            if not rec or rec["total"] != counts["total"] or rec["killed"] != counts["killed"]:
                structure.append({"task": label, "operator": op,
                                  "issue": "kill_rate_summary disagrees with kill_matrix",
                                  "kill_matrix": counts, "summary": rec})

        # --- check 3: corpus quality ---
        canonical = task.prompt + task.canonical_solution
        canon_norm = _normalise(canonical)
        norms = [_normalise(m["code"]) for m in llm]
        corpus.append({
            "task": label,
            "n_mutants": len(llm),
            "n_unique": len(set(norms)),
            "n_echo": sum(1 for n in norms if n == canon_norm),
            "edit_sites": [_edit_sites(canonical, m["code"]) for m in llm],
            "by_model": Counter(m.get("source_model", "?") for m in llm),
        })

    return {"kill_jobs": kill_jobs, "equiv_jobs": equiv_jobs,
            "recorded_kill": recorded_kill, "structure": structure, "corpus": corpus,
            "n_excluded_invalid": n_excluded_invalid}


def run_jobs(jobs, workers: int, desc: str) -> dict:
    if not jobs:
        return {}
    out = {}
    print(f"  {desc}: {len(jobs)} execution(s)...", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_kill_job, j) for j in jobs]
        for fut in as_completed(futures):
            key, killed = fut.result()
            out[key] = killed
    return out


def measure_fuzz_power(tasks, cfg) -> list[dict]:
    """Distinct canonical outputs per task -- the real size of the evidence."""
    jobs = []
    for task in tasks:
        inputs = _generate_inputs(task, cfg.stage0.n_fuzz_inputs, cfg.project.seed)
        captured = len(_capture_test_inputs(task, cfg.project.seed))
        jobs.append((task_label(task), task.prompt + task.canonical_solution,
                     task.entry_point, inputs, cfg.execution.timeout_s, captured))
    rows = []
    print(f"  fuzz power: {sum(len(j[3]) for j in jobs)} execution(s)...", flush=True)
    with ProcessPoolExecutor(max_workers=cfg.execution.cpu_workers) as pool:
        futures = {pool.submit(_canon_job, j[:5]): j for j in jobs}
        for fut in as_completed(futures):
            label, outs = fut.result()
            job = futures[fut]
            counts = Counter(map(repr, outs))
            rows.append({
                "task": label,
                "n_inputs": len(outs),
                "n_captured_from_tests": job[5],
                "n_random_padding": len(outs) - job[5],
                "n_distinct_outputs": len(counts),
                "most_common_share": counts.most_common(1)[0][1] / len(outs) if outs else 0.0,
            })
    return sorted(rows, key=lambda r: r["n_distinct_outputs"])


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(out: dict) -> None:
    v, inv, corp, struct = (out["verdicts"], out["invariant"],
                            out["corpus_quality"], out["structure"])

    print("\n" + "=" * 78)
    print("CHECK 1 - verdict reproduction")
    print("=" * 78)
    print(f"  re-executed {v['n_checked']} recorded kill verdict(s)")
    print(f"  mismatches : {len(v['mismatches'])}")
    for m in v["mismatches"][:20]:
        print(f"    ** {m['task']:16s} {m['mutant']:36s} recorded={m['recorded']} live={m['live']}")

    print("\n" + "=" * 78)
    print("CHECK 2 - equivalence invariant (a truly equivalent mutant cannot be killed)")
    print("=" * 78)
    print(f"  re-tested {inv['n_checked']} equivalence exclusion(s)")
    print(f"  contradictions : {len(inv['contradictions'])}")
    for c in inv["contradictions"][:20]:
        print(f"    ** {c['task']:16s} {c['mutant']:36s} excluded as equivalent, but the suite kills it")

    print("\n" + "=" * 78)
    print("CHECK 3 - LLM corpus quality")
    print("=" * 78)
    print(f"  mutants            : {corp['n_mutants']}")
    print(f"  unique (AST-norm)  : {corp['n_unique']}  -> redundancy {corp['redundancy_pct']:.1f}%")
    print(f"  echoes of canonical: {corp['n_echo']}")
    print(f"  tasks with duplicates: {corp['n_tasks_with_duplicates']} / {corp['n_tasks']}")
    print("  edit sites per mutant (a first-order fault should be 1):")
    for sites, n in sorted(corp["edit_site_hist"].items()):
        print(f"    {sites:>2} site(s): {n:5d}")

    print("\n" + "=" * 78)
    print("CHECK 4 - structural integrity")
    print("=" * 78)
    print(f"  correctly excluded before evaluation (llm_invalid_mutants.json): "
          f"{out.get('n_excluded_invalid', 0)}")
    print(f"  issues : {len(struct)}")
    for s in struct[:20]:
        print(f"    ** {s}")

    if out.get("fuzz_power"):
        print("\n" + "=" * 78)
        print("CHECK 5 - fuzz-set discriminating power (weakest 15 tasks)")
        print("=" * 78)
        print(f"  {'task':16s} {'inputs':>7s} {'captured':>9s} {'distinct':>9s} {'top output share':>17s}")
        for r in out["fuzz_power"][:15]:
            print(f"  {r['task']:16s} {r['n_inputs']:7d} {r['n_captured_from_tests']:9d} "
                  f"{r['n_distinct_outputs']:9d} {r['most_common_share']*100:16.1f}%")

    ok = not v["mismatches"] and not inv["contradictions"]
    print("\n" + "=" * 78)
    print("PASS - every recorded verdict reproduces and the invariant holds" if ok
          else "FAIL - see CHECK 1 / CHECK 2 above")
    print("=" * 78)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(REPO_ROOT / "config" / "default.yaml"))
    parser.add_argument("--tasks", type=int, nargs="+", default=None,
                        help="task indices to audit (default: all)")
    parser.add_argument("--fuzz-power", action="store_true",
                        help="also measure per-task fuzz-set discriminating power (slow)")
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    tasks = load_humaneval(tasks=args.tasks)
    workers = cfg.execution.cpu_workers
    print(f"Auditing {len(tasks)} task(s) in {RESULTS}")

    data = collect(tasks, cfg)
    killed = run_jobs(data["kill_jobs"], workers, "check 1, verdict reproduction")
    equiv_killed = run_jobs(data["equiv_jobs"], workers, "check 2, equivalence invariant")

    mismatches = [{"task": k[0], "mutant": k[1], "recorded": data["recorded_kill"][k], "live": live}
                  for k, live in killed.items() if live != data["recorded_kill"][k]]
    contradictions = [{"task": k[0], "mutant": k[1]} for k, live in equiv_killed.items() if live]

    corpus = data["corpus"]
    n_mutants = sum(c["n_mutants"] for c in corpus)
    n_unique = sum(c["n_unique"] for c in corpus)
    hist = Counter()
    for c in corpus:
        hist.update(c["edit_sites"])

    out = {
        "n_tasks": len(tasks),
        "verdicts": {"n_checked": len(killed), "mismatches": mismatches},
        "invariant": {"n_checked": len(equiv_killed), "contradictions": contradictions},
        "corpus_quality": {
            "n_tasks": len(corpus),
            "n_mutants": n_mutants,
            "n_unique": n_unique,
            "redundancy_pct": (1 - n_unique / n_mutants) * 100 if n_mutants else 0.0,
            "n_echo": sum(c["n_echo"] for c in corpus),
            "n_tasks_with_duplicates": sum(1 for c in corpus if c["n_unique"] < c["n_mutants"]),
            "edit_site_hist": dict(sorted(hist.items())),
            "per_task": [{k: v for k, v in c.items() if k != "by_model"} for c in corpus],
        },
        "structure": data["structure"],
        "n_excluded_invalid": data["n_excluded_invalid"],
    }
    if args.fuzz_power:
        out["fuzz_power"] = measure_fuzz_power(tasks, cfg)

    out_path = RESULTS / "audit" / "rq1_audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    report(out)
    print(f"\nWrote {out_path}")
    if mismatches or contradictions:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
