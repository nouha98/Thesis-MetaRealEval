#!/usr/bin/env python
"""M0: the RealClassEval validity gate (Tier 2).

Validates every staged task (``benchmarks.validate.validate_task``: D1-D6 plus
amendments A3/A4) and writes:

``<manifest>``              e.g. data/realclasseval/manifest_v1.json -- what
                            ``RealClassEvalBenchmark.load_tasks`` reads:
                            accepted tasks with contiguous ``task_index``,
                            per-test D2 verdicts, scenario exclusions/masks.
``gate_report.md``          next to the manifest: the sample description
                            for the thesis (D2 mandatory reporting, A4b
                            kept-vs-dropped complexity comparison).

    # on the cluster, in the pinned Python 3.11 environment (authoritative):
    .venv/bin/python scripts/validate_realclasseval.py --config config/tier2_realclasseval.yaml --require-python 3.11

    # anywhere else, a dry run to a scratch location:
    python scripts/validate_realclasseval.py --config config/tier2_realclasseval.yaml --output /tmp/m0/manifest.json

A manifest is marked ``"authoritative": true`` only when produced under
Python 3.11 (amendment A4: Pynguin's suites were generated there, and some
assert on interpreter details). Per-task results are checkpointed, keyed by
the corpus hash, gate version, timeouts and interpreter, so an interrupted
run resumes and a changed gate never reuses stale records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import traceback
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.benchmarks.forkserver import PYTHONHASHSEED, default_mode  # noqa: E402
from meta_real_eval.benchmarks.realclasseval import RealClassEvalBenchmark  # noqa: E402
from meta_real_eval.benchmarks.validate import (  # noqa: E402
    GATE_VERSION,
    METRIC_KEYS,
    summarise_tests,
    validate_task,
)
from meta_real_eval.core.config import Config  # noqa: E402

AUTHORITATIVE_PYTHON = (3, 11)


GATE_TIMEOUT = "gate_timeout"

# A task that hangs indefinitely despite every internal timeout
# (execute_pytest's, run_scenarios') is not hypothetical: a class whose own
# behaviour spawns a subprocess (multiprocessing.Manager(), say) can wedge the
# subprocess *subprocess.run()* itself waits on, which no timeout inside this
# codebase can see. Found live, on the real corpus: RealClassEval/csn/snippet_123
# (MultiprocessingStringIO) hung the whole gate for hours on Windows. The fix
# is not "find and silence that one task" -- it is making the gate itself
# survive ANY task that does this, whatever the cause, which is what the stall
# detector below (main()) and this forced-kill exist for.
STALL_TIMEOUT_S = 600.0


def _kill_pool_workers(pool: ProcessPoolExecutor) -> list[int]:
    """Forcibly terminate every live worker process.

    ProcessPoolExecutor has no public "abandon this worker, it's stuck" API --
    future.cancel() only works on work that has not started, and the `with`
    statement's __exit__ calls shutdown(wait=True), which blocks forever on a
    genuinely hung worker. Reaching into the (private, but stable in practice
    across 3.9-3.13) ``_processes`` map is the only way to actually get the
    interpreter to exit when one task has wedged a worker.
    """
    import signal

    killed = []
    for pid, proc in list(getattr(pool, "_processes", {}).items()):
        try:
            if proc.is_alive():
                os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
                killed.append(pid)
        except (ProcessLookupError, OSError):
            pass
    return killed


def _worker(task, suite_timeout, scenario_timeout, seed, pool_sizes) -> dict:
    try:
        return validate_task(task, suite_timeout, scenario_timeout, seed, pool_sizes)
    except Exception:
        return {"task_id": task.task_id, "split": task.split, "label": task.label,
                "status": "excluded", "exclusion_reason": "gate_error",
                "detail": traceback.format_exc(), "metrics": {}, "tests": {}, "scenarios": {}}


def _fmt(x) -> str:
    return "–" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))


def write_report(path: Path, manifest: dict) -> None:
    tasks = manifest["tasks"]
    splits = sorted({t["split"] for t in tasks})
    h = manifest["header"]
    lines = [
        "# RealClassEval M0 gate report", "",
        f"- authoritative: **{h['authoritative']}** (Python {h['python']}, pytest {h['pytest']}, {h['platform']})",
        f"- corpus: commit `{h['corpus_commit']}`, sha256 `{h['corpus_sha256'][:16]}…`",
        f"- gate v{h['gate_version']}, suite timeout {h['suite_timeout_s']} s, scenario timeout "
        f"{h['scenario_timeout_s']} s, scenario mode `{h['scenario_mode']}`, PYTHONHASHSEED={h['pythonhashseed']}",
        f"- generated {h['generated_utc']}", "",
        "## Tasks", "",
        "| | " + " | ".join(splits) + " | total |", "|---|" + "---|" * (len(splits) + 1),
    ]
    reasons = sorted({t["exclusion_reason"] for t in tasks if t["status"] != "accepted"})
    rows = [("staged", lambda t: True), ("**accepted**", lambda t: t["status"] == "accepted")]
    rows += [(f"excluded: {r}", lambda t, r=r: t["exclusion_reason"] == r) for r in reasons]
    for label, pred in rows:
        counts = [sum(1 for t in tasks if t["split"] == s and pred(t)) for s in splits]
        lines.append(f"| {label} | " + " | ".join(map(str, counts)) + f" | {sum(counts)} |")

    lines += ["", "## Tests (D2 mandatory reporting)", "",
              "Counted over tasks that reached the D2 stage. The primary metric is the pass rate over "
              "deterministic, order-independent tests validated against the reference implementation -- "
              "not the original Pynguin suite.", "",
              "| | " + " | ".join(splits) + " |", "|---|" + "---|" * len(splits)]
    reached = defaultdict(list)
    for t in tasks:
        if t.get("tests"):
            reached[t["split"]].append(t)
    per_split = {s: Counter() for s in splits}
    validity = {s: Counter() for s in splits}
    for s in splits:
        for t in reached[s]:
            per_split[s].update(summarise_tests(t))
            validity[s].update(v["validity"] for v in t["tests"].values())
    for key in ("original", "valid", "valid_behavioural", "valid_exception_explicit_raises",
                "valid_exception_reference_xfail", "trivial", "xfail"):
        lines.append(f"| {key} | " + " | ".join(str(per_split[s][key]) for s in splits) + " |")
    lines.append("| non-trivial valid | " + " | ".join(
        str(per_split[s]["valid"] - per_split[s]["trivial"]) for s in splits) + " |")
    for v in sorted({v for c in validity.values() for v in c if v.startswith("invalid")}):
        lines.append(f"| {v} | " + " | ".join(str(validity[s][v]) for s in splits) + " |")
    lines.append("| tasks whose skeleton baseline failed to import (trivial undetectable) | " + " | ".join(
        str(sum(1 for t in reached[s] if t.get("skeleton_baseline") == "import_error")) for s in splits) + " |")

    lines += ["", "## Scenarios (D4/D5)", "", "| | " + " | ".join(splits) + " |", "|---|" + "---|" * len(splits)]
    scen = {s: Counter() for s in splits}
    low = Counter()
    for t in tasks:
        sc = t.get("scenarios") or {}
        if not sc:
            continue
        for k in ("n_original", "n_usable", "n_tokens", "n_masked_tokens", "n_opaque_tokens", "env_observations_dropped"):
            scen[t["split"]][k] += sc.get(k, 0)
        if t["status"] == "accepted" and sc.get("pools", {}).get("500", {}).get("low_scenario_diversity"):
            low[t["split"]] += 1
    for k in ("n_original", "n_usable", "env_observations_dropped"):
        lines.append(f"| {k} | " + " | ".join(str(scen[s][k]) for s in splits) + " |")
    for k, label in (("n_masked_tokens", "masked share"), ("n_opaque_tokens", "OPAQUE share")):
        lines.append(f"| {label} | " + " | ".join(
            f"{scen[s][k] / scen[s]['n_tokens']:.3f}" if scen[s]["n_tokens"] else "–" for s in splits) + " |")
    lines.append("| accepted tasks with <3 original scenarios | " + " | ".join(str(low[s]) for s in splits) + " |")

    lines += ["", "## Kept vs dropped (threat A4b: selection by the gate)", "",
              "Mean of each complexity metric; a large gap means the gate changed the population.", "",
              "| metric | " + " | ".join(f"{s} kept | {s} dropped" for s in splits) + " |",
              "|---|" + "---|" * (2 * len(splits))]
    for m in METRIC_KEYS:
        cells = []
        for s in splits:
            for status in ("accepted", "excluded"):
                vals = [t["metrics"].get(m) for t in tasks if t["split"] == s and t["status"] == status]
                vals = [v for v in vals if isinstance(v, (int, float))]
                cells.append(_fmt(statistics.fmean(vals)) if vals else "–")
        lines.append(f"| {m} | " + " | ".join(cells) + " |")

    errors = [t for t in tasks if t["exclusion_reason"] == "gate_error"]
    lines += ["", f"## Gate errors: {len(errors)}", ""]
    lines += [f"- `{t['task_id']}`: {t['detail'].strip().splitlines()[-1]}" for t in errors]
    if errors:
        lines.append("\nA valid run has zero gate errors: these are harness bugs, not task properties.")

    stalls = [t for t in tasks if t["exclusion_reason"] == GATE_TIMEOUT]
    lines += ["", f"## Gate timeouts: {len(stalls)}", ""]
    lines += [f"- `{t['task_id']}`" for t in stalls]
    if stalls:
        lines.append(
            "\nThese tasks wedged a worker in a way no internal timeout could see (e.g. a "
            "class whose own behaviour spawns a subprocess). Re-run them alone with "
            "--force to see whether it reproduces, with --stall-timeout raised if it is "
            "just slow rather than truly stuck."
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/tier2_realclasseval.yaml")
    parser.add_argument("--output", type=Path, default=None, help="manifest path (default: benchmark.manifest_path)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None, help="only the first N tasks per split (dry runs)")
    parser.add_argument("--scenario-timeout", type=float, default=10.0)
    parser.add_argument("--stall-timeout", type=float, default=STALL_TIMEOUT_S,
                        help="give up on all still-pending tasks if NONE finish within this "
                             "many seconds (a task can wedge a worker in a way no internal "
                             "timeout can see, e.g. a class that itself spawns a subprocess); "
                             "they are recorded excluded/gate_timeout rather than hanging the run")
    parser.add_argument("--require-python", default=None, help="e.g. 3.11: refuse to run under any other version")
    parser.add_argument("--force", action="store_true", help="ignore per-task checkpoints")
    args = parser.parse_args()

    py = ".".join(map(str, sys.version_info[:2]))
    if args.require_python and py != args.require_python:
        print(f"ERROR: running under Python {py}, --require-python {args.require_python}", file=sys.stderr)
        return 2
    authoritative = sys.version_info[:2] == AUTHORITATIVE_PYTHON
    if not authoritative:
        print(f"WARNING: Python {py} is not 3.11 -- this manifest is NOT authoritative (dry run).")

    cfg = Config.from_yaml(args.config)
    bench = RealClassEvalBenchmark(cfg)
    output = Path(args.output or bench.manifest_path)
    source = json.loads((bench.corpus_path.parent / "source.json").read_text(encoding="utf-8"))
    suite_timeout = float(cfg.execution.timeout_s)
    pool_sizes = (cfg.stage0.n_fuzz_inputs, cfg.rq3.n_shared_inputs)

    tasks = bench.corpus_tasks()
    if args.limit:
        per_split: Counter = Counter()
        kept = []
        for t in tasks:
            if per_split[t.split] < args.limit:
                kept.append(t)
                per_split[t.split] += 1
        tasks = kept

    key = hashlib.sha256(json.dumps([source["corpus_sha256"], GATE_VERSION, suite_timeout,
                                     args.scenario_timeout, py, list(pool_sizes), cfg.project.seed]).encode()).hexdigest()[:16]
    ckpt_dir = output.parent / f"gate_cache_{key}"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    records: dict[str, dict] = {}
    todo = []
    for t in tasks:
        ck = ckpt_dir / f"{t.label}.json"
        if ck.exists() and not args.force:
            records[t.task_id] = json.loads(ck.read_text(encoding="utf-8"))
        else:
            todo.append(t)
    print(f"{len(tasks)} task(s): {len(records)} from checkpoint, {len(todo)} to validate "
          f"({args.workers} workers, scenario mode {default_mode()})")

    pool = ProcessPoolExecutor(max_workers=args.workers)
    try:
        futures = {pool.submit(_worker, t, suite_timeout, args.scenario_timeout, cfg.project.seed, pool_sizes): t
                   for t in todo}
        pending = set(futures)
        i = 0
        while pending:
            done, pending = wait(pending, timeout=args.stall_timeout, return_when=FIRST_COMPLETED)
            if not done:
                stuck = sorted(futures[f].label for f in pending)
                print(f"STALL: no task finished in {args.stall_timeout:.0f}s -- "
                      f"{len(stuck)} task(s) presumed wedged ({', '.join(stuck[:5])}"
                      f"{', ...' if len(stuck) > 5 else ''}). Recording gate_timeout and "
                      "force-killing workers so the run can still finish.")
                for f in pending:
                    t = futures[f]
                    rec = {"task_id": t.task_id, "split": t.split, "label": t.label,
                          "status": "excluded", "exclusion_reason": GATE_TIMEOUT,
                          "detail": f"no result within the {args.stall_timeout:.0f}s gate stall budget",
                          "metrics": {}, "tests": {}, "scenarios": {}}
                    (ckpt_dir / f"{t.label}.json").write_text(json.dumps(rec), encoding="utf-8")
                    records[t.task_id] = rec
                killed = _kill_pool_workers(pool)
                print(f"  killed worker PID(s): {killed}")
                break
            for fut in done:
                i += 1
                t = futures[fut]
                try:
                    rec = fut.result()
                except Exception:
                    rec = {"task_id": t.task_id, "split": t.split, "label": t.label,
                          "status": "excluded", "exclusion_reason": "gate_error",
                          "detail": traceback.format_exc(), "metrics": {}, "tests": {}, "scenarios": {}}
                (ckpt_dir / f"{t.label}.json").write_text(json.dumps(rec), encoding="utf-8")
                records[t.task_id] = rec
                if i % 25 == 0 or not pending:
                    print(f"  {i}/{len(todo)} validated")
    finally:
        # shutdown(wait=True) (what `with` would do) hangs forever if a worker
        # was already killed out from under it on some platforms; wait=False
        # plus the explicit kill above is what actually lets the script exit.
        pool.shutdown(wait=False)

    ordered = [records[t.task_id] for t in tasks]
    index = 0
    for rec in ordered:
        if rec["status"] == "accepted":
            rec["task_index"] = index
            index += 1

    manifest = {
        "header": {
            "manifest_version": 1,
            "authoritative": authoritative and not args.limit,
            "gate_version": GATE_VERSION,
            "python": platform.python_version(),
            "pytest": metadata.version("pytest"),
            "platform": platform.platform(),
            "scenario_mode": default_mode(),
            "pythonhashseed": PYTHONHASHSEED,
            "suite_timeout_s": suite_timeout,
            "scenario_timeout_s": args.scenario_timeout,
            "pool_sizes": list(pool_sizes),
            "seed": cfg.project.seed,
            "corpus_commit": source["commit"],
            "corpus_sha256": source["corpus_sha256"],
            "limit_per_split": args.limit,
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_accepted": index,
        },
        "tasks": ordered,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    report = output.with_name("gate_report.md")
    write_report(report, manifest)

    reasons = Counter(r["exclusion_reason"] for r in ordered if r["status"] != "accepted")
    print(f"accepted {index}/{len(ordered)}; excluded: {dict(reasons)}")
    print(f"manifest -> {output}\nreport   -> {report}")
    return 1 if (reasons.get("gate_error") or reasons.get(GATE_TIMEOUT)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
