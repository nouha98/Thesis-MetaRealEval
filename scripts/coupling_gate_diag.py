"""Gate GC diagnostics for a coupling run (read-only; computes no coupling value).

    python scripts/analyze_coupling.py --run <run> --technical      # writes <run>/technical.json
    python scripts/coupling_gate_diag.py <run>

Breaks down what the technical report only counts: the evaluation conditional population (development tasks
excluded, which `projected_conditional_population` is not), the historical P-pass mismatches, the perturbed
false-detection rate by task, the reference rows with problems, and the stratified spot-check sample.
"""
import collections, json, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import analyze_coupling as ac
import ext_common as ec
from meta_real_eval.oracles.coupling import exclusion_counts

run = Path(sys.argv[1])
dets = ac.load_run(run)
dev = set(ec.load_ext_config("config/tier2_extensions.yaml").extensions.development_tasks)
tech = json.loads((run / "technical.json").read_text(encoding="utf-8"))
sup = {d["task"]: d["support"]["supported"] for d in dets}

rows = [r for r in tech["per_task"] if r["task"] not in dev]
print("== 1. evaluation population (development tasks excluded)")
print("conditional population:", sum(r["excluded"] is None for r in rows), "| supported evaluation tasks:", sum(r["supported"] for r in rows))
print("exclusion reasons:", exclusion_counts(rows))
print("development tasks that contribute (not in the evaluation population):",
      [r["task"] for r in tech["per_task"] if r["task"] in dev and r["excluded"] is None])

print("== 2. historical P-pass mismatches (whole-suite timeouts already excepted)")
mm = []
for d in dets:
    for p in d["programs"]:
        if p["kind"] != "solution" or p.get("p_passed_all") is None or ac.whole_suite_timeout(p):
            continue
        outs = list((p.get("p_outcomes") or {}).values())
        for m in p["members"]:
            if m["stored_p_pass"] is not None and m["stored_p_pass"] != p["p_passed_all"]:
                mm.append((d["task"], p["id"][:10], "stored", m["stored_p_pass"], "now", p["p_passed_all"], sorted(set(outs))))
print(len(mm), "mismatches"); [print("  ", x) for x in mm]

print("== 3. perturbed false detection by task")
by = collections.defaultdict(lambda: [0, 0])
for d in dets:
    unstable = ac.reference_unstable(d, "perturbed")
    orig = [t for t in d["tests"]["perturbed"] or [] if "~p" not in t and t not in unstable]
    for p in d["programs"]:
        if p["kind"] == "solution" and not ac.whole_suite_timeout(p) and ac.p_pass(p) and p.get("perturbed"):
            by[d["task"]][1] += len(orig)
            by[d["task"]][0] += len(set(p["perturbed"]["detect"]) & set(orig))
num, den = sum(v[0] for v in by.values()), sum(v[1] for v in by.values())
print(f"overall {num}/{den} = {num / den:.4f} (technical report: {tech['perturbed_false_detection_on_p_passing']:.4f})")
top = sorted(by.items(), key=lambda kv: -kv[1][0])[:8]
for t, (a, b) in top:
    print(f"  {t}: {a}/{b} = {a / b:.2f} supported={sup[t]} dev={t in dev}")
rest_n, rest_d = num - sum(v[0] for _, v in top[:3]), den - sum(v[1] for _, v in top[:3])
print(f"top 3 tasks hold {sum(v[0] for _, v in top[:3]) / num:.0%} of the flagged cells; rate without them {rest_n / rest_d:.4f}")
print("tasks with any flagged cell:", sum(v[0] > 0 for v in by.values()), "of", len(by))

print("== 4. reference rows with problems")
for t, pr in tech["reference_rows"]["problems"].items():
    print("  ", t, "supported" if sup[t] else "unsupported", pr)

print("== 5. spot-check sample (10 rows, one per task where possible)")
for s in tech["spot_check_sample"]:
    print(json.dumps(s, ensure_ascii=False)[:700])
