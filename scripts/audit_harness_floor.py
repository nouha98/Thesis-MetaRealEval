"""Tier 2 harness floor/ceiling audit: score the reference, an empty module and the
bare skeleton for every task through the same run_suite the RQ2 evaluator uses.

The reference must score 1.0 everywhere (else the harness, not the model, sets a
ceiling). The empty module's score is the credit a completion gets without defining
the class at all: exception-oracle tests whose reference raises AttributeError are
also satisfied by ``module_0.Missing`` (found in the S8 run, csn_snippet_156/250).

    srun -p infosun -c 8 --mem 8G -t 01:00:00 .venv/bin/python scripts/audit_harness_floor.py

Read-only apart from the JSON it writes.
"""
import collections as C, json, sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, "src")
from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402

CFG = "config/tier2_runs/full_combined.yaml"
OUT = "results_tier2_runs/full/combined/harness_check.json"


def one(i):
    cfg = Config.from_yaml(CFG)
    bench = get_benchmark(cfg)
    t = bench.load_tasks([i])[0]
    rec = {"task": t.label, "task_index": i}
    for name, code in (("reference", t.reference_code), ("empty", ""), ("skeleton", t.prompt)):
        r = bench.run_suite(t, code, cfg.execution.timeout_s)
        rec[name] = r.primary
        rec[f"{name}_behavioural"] = r.scores.get("behavioural_pass_rate")
        rec[f"{name}_outcomes"] = dict(C.Counter(o.outcome for o in r.outcomes.values()))
    tests = t.meta["tests"]
    rec["validity"] = dict(C.Counter(v["validity"] for v in tests.values()))
    rec["exc_oracle_types"] = dict(C.Counter(v.get("ref_exc_type") for v in tests.values()
                                             if v["validity"] == "valid_exception_oracle"))
    return rec


if __name__ == "__main__":
    n = len(get_benchmark(Config.from_yaml(CFG)).load_tasks())
    with ProcessPoolExecutor(max_workers=8) as pool:
        recs = list(pool.map(one, range(n)))
    json.dump(recs, open(OUT, "w"), indent=1)
    print("tasks", len(recs))
    print("reference != 1.0:", [(r["task"], r["reference"], r["reference_outcomes"]) for r in recs if r["reference"] != 1.0])
    pos = [r for r in recs if (r["empty"] or 0) > 0]
    print("empty module scores > 0 on", len(pos), "tasks; = 1.0 on", sum(r["empty"] == 1.0 for r in recs))
    print("  mean empty score over all tasks %.4f" % (sum(r["empty"] or 0 for r in recs) / len(recs)))
    print("skeleton scores > 0 on", sum((r["skeleton"] or 0) > 0 for r in recs), "tasks")
    tot = C.Counter(); exc = C.Counter()
    for r in recs:
        tot.update(r["validity"]); exc.update(r["exc_oracle_types"])
    print("test validity totals:", dict(tot))
    print("exception-oracle types:", exc.most_common(12))
    print("written ->", OUT)
