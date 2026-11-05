"""Tier 2 harness floor/ceiling audit: score the reference, an empty module and the
bare skeleton for every task through the same run_suite the RQ2 evaluator uses.

The reference must score 1.0 everywhere (else the harness, not the model, sets a
ceiling). The empty module's score is the credit a completion gets without defining
the class at all: exception-oracle tests whose reference raises AttributeError are
also satisfied by ``module_0.Missing`` (found in the S8 run, csn_snippet_156/250).

Runs in the evaluation's environment: like scripts/slurm/_common.sh it points HOME
(when unusable: /home is not mounted on the compute nodes), MPLCONFIGDIR,
XDG_CACHE_HOME and HF_HOME into the repo, and it uses the config's cpu_workers. The
first version ran without that and timed out every matplotlib/spacy/seaborn
reference (font cache rebuilt per run) and failed post_snippet_29 (writes to ~).

    srun -p infosun --exclude=hydra -c 4 --mem 8G -t 02:00:00 \
        .venv/bin/python scripts/audit_harness_floor.py [--tasks LABEL,...]

Read-only apart from the JSON it writes.
"""
import argparse, collections as C, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402

CFG = "config/tier2_runs/full_combined.yaml"
OUT = "results_tier2_runs/full/combined/harness_check.json"


def _evaluation_env() -> None:
    home = os.environ.get("HOME", "")
    if not home or not os.path.isdir(home) or not os.access(home, os.W_OK):
        os.environ["HOME"] = str(REPO / ".slurm_home")
    for var, sub in (("HF_HOME", "huggingface"), ("XDG_CACHE_HOME", "xdg"), ("MPLCONFIGDIR", "matplotlib")):
        os.environ[var] = str(REPO / ".cache" / sub)
    for var in ("HOME", "HF_HOME", "XDG_CACHE_HOME", "MPLCONFIGDIR"):
        Path(os.environ[var]).mkdir(parents=True, exist_ok=True)


def one(i):
    cfg = Config.from_yaml(CFG)
    bench = get_benchmark(cfg)
    t = bench.load_tasks([i])[0]
    rec = {"task": t.label, "task_index": i}
    for name, code in (("reference", t.reference_code), ("empty", ""), ("skeleton", t.prompt)):
        t0 = time.monotonic()
        r = bench.run_suite(t, code, cfg.execution.timeout_s)
        rec[f"{name}_seconds"] = round(time.monotonic() - t0, 1)
        rec[name] = r.primary
        rec[f"{name}_behavioural"] = r.scores.get("behavioural_pass_rate")
        rec[f"{name}_outcomes"] = dict(C.Counter(o.outcome for o in r.outcomes.values()))
    tests = t.meta["tests"]
    rec["validity"] = dict(C.Counter(v["validity"] for v in tests.values()))
    rec["exc_oracle_types"] = dict(C.Counter(v.get("ref_exc_type") for v in tests.values()
                                             if v["validity"] == "valid_exception_oracle"))
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", help="comma-separated task labels (default: all)")
    args = ap.parse_args()
    _evaluation_env()
    cfg = Config.from_yaml(CFG)
    tasks = get_benchmark(cfg).load_tasks()
    idx = [i for i, t in enumerate(tasks) if not args.tasks or t.label in args.tasks.split(",")]
    with ProcessPoolExecutor(max_workers=cfg.execution.cpu_workers) as pool:
        recs = list(pool.map(one, idx))
    out = OUT if not args.tasks else OUT.replace(".json", ".subset.json")
    json.dump(recs, open(out, "w"), indent=1)
    print("tasks", len(recs), "| HOME", os.environ["HOME"], "| workers", cfg.execution.cpu_workers)
    print("reference != 1.0:", [(r["task"], r["reference"], r["reference_outcomes"], r["reference_seconds"])
                                for r in recs if r["reference"] != 1.0])
    print("slowest references (s):", sorted(((r["reference_seconds"], r["task"]) for r in recs), reverse=True)[:8])
    pos = [r for r in recs if (r["empty"] or 0) > 0]
    print("empty module scores > 0 on", len(pos), "tasks; = 1.0 on", sum(r["empty"] == 1.0 for r in recs))
    print("  mean empty score over all tasks %.4f" % (sum(r["empty"] or 0 for r in recs) / len(recs)))
    print("  empty = 1.0:", sorted(r["task"] for r in recs if r["empty"] == 1.0))
    print("skeleton scores > 0 on", sum((r["skeleton"] or 0) > 0 for r in recs), "tasks")
    tot = C.Counter(); exc = C.Counter()
    for r in recs:
        tot.update(r["validity"]); exc.update(r["exc_oracle_types"])
    print("test validity totals:", dict(tot))
    print("exception-oracle types:", exc.most_common(12))
    print("written ->", out)
