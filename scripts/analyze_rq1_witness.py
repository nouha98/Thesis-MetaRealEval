"""RQ1 robustness under witness-based fault confirmation (plan rev. 9, Stage 2.8).

    python scripts/analyze_rq1_witness.py --witness results_tier2_ext/witness/dev_pilot_local

Reads the witness results (one witness.json per task) and reports kill rates of operator and
whole-source LLM faults under five populations, at GROUP level (a fault group = one fault; a
mixed group counts for both sources; its kill outcome is the members' stored outcome, and any
disagreement between members is reported):

  historical          groups non-equivalent in the stored Stage 0 / RQ1 files (all tasks)
  supported_hist      the same, restricted to supported tasks
  primary             groups with a replayed, API-visible, valid-domain witness (D3)
  full_trace          primary + private-state-only + domain-uncertain witnesses (sensitivity)
  bound_unresolved    primary, with unresolved groups counted as survivors

The historical analyze_rq1 is untouched. On a development pilot the numbers are descriptive
(small n, draft contracts); the paired test is reported only from the confirmatory run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meta_real_eval.analysis.statistics import wilcoxon_test  # noqa: E402

EQUIV = ("no_divergence", "no_testable_inputs", "ast_identical")


def group_killed(g: dict):
    ks = [m.get("killed") for m in g["members"] if m.get("killed") is not None]
    if not ks:
        return None, False
    return any(ks), len(set(ks)) > 1


def hist_nonequivalent(g: dict) -> bool:
    return any(m.get("equivalence") not in EQUIV and m.get("equivalence") is not None for m in g["members"])


def sources_of(g: dict) -> list[str]:
    if g["source"] == "mixed":
        return ["operator", "llm_whole"]
    return [g["source"]]


def is_primary(g):
    return (g["outcome"] == "distinguished" and g["level"] == "api_visible" and g["domain"] == "valid"
            and (g.get("replay") or {}).get("confirmed", False))


def in_full_trace(g):
    return g["outcome"] == "distinguished" and (g.get("replay") or {}).get("confirmed", False)


POPULATIONS = {
    "historical": lambda g, sup: hist_nonequivalent(g),
    "supported_hist": lambda g, sup: sup and hist_nonequivalent(g),
    "primary": lambda g, sup: sup and is_primary(g),
    "full_trace": lambda g, sup: sup and in_full_trace(g),
    "bound_unresolved": lambda g, sup: sup and (is_primary(g) or g["outcome"] == "unresolved"),
}


def analyse(results: list[dict]) -> dict:
    out = {"populations": {}, "member_kill_disagreements": 0, "per_task": {}}
    for r in results:
        for g in r["groups"]:
            out["member_kill_disagreements"] += group_killed(g)[1]
    for name, member in POPULATIONS.items():
        rows = {"operator": [0, 0], "llm_whole": [0, 0]}
        per_task = {}
        for r in results:
            sup = r["support"]["supported"]
            for g in r["groups"]:
                if not member(g, sup):
                    continue
                killed, _ = group_killed(g)
                if name == "bound_unresolved" and g["outcome"] == "unresolved":
                    killed = False
                if killed is None:
                    continue
                for s in sources_of(g):
                    rows[s][0] += killed
                    rows[s][1] += 1
                    per_task.setdefault(r["task"], {}).setdefault(s, []).append(killed)
        paired = [(sum(v["llm_whole"]) / len(v["llm_whole"]), sum(v["operator"]) / len(v["operator"]))
                  for v in per_task.values() if v.get("llm_whole") and v.get("operator")]
        test = wilcoxon_test([a for a, _ in paired], [b for _, b in paired]) if len(paired) >= 6 else None
        out["populations"][name] = {
            s: {"killed": k, "groups": n, "kill_rate": (k / n if n else None)} for s, (k, n) in rows.items()}
        out["populations"][name]["paired_tasks"] = len(paired)
        out["populations"][name]["gap_llm_minus_operator"] = (
            None if not rows["llm_whole"][1] or not rows["operator"][1]
            else rows["llm_whole"][0] / rows["llm_whole"][1] - rows["operator"][0] / rows["operator"][1])
        out["populations"][name]["wilcoxon_paired_task_rates"] = test
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--witness", type=Path, required=True)
    args = ap.parse_args(argv)
    results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.witness.glob("*/witness.json"))]
    res = analyse(results)
    res["authoritative"] = all(r["gated"] for r in results)
    res["contracts"] = sorted({r["contract"]["status"] for r in results})
    (args.witness / "rq1_robustness.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    L = ["# RQ1 robustness (witness-confirmed faults, group level)", "",
         f"*{'authoritative' if res['authoritative'] else 'NON-AUTHORITATIVE local run'}; contracts {res['contracts']}; "
         f"member kill disagreements {res['member_kill_disagreements']}. Descriptive on a development pilot.*", "",
         "| population | operator killed/groups | rate | LLM killed/groups | rate | gap (LLM - op) | paired tasks |",
         "|---|---|---|---|---|---|---|"]
    for name, p in res["populations"].items():
        o, l = p["operator"], p["llm_whole"]
        fr = lambda x: "n/a" if x is None else f"{x:.3f}"  # noqa: E731
        L.append(f"| {name} | {o['killed']}/{o['groups']} | {fr(o['kill_rate'])} | {l['killed']}/{l['groups']} | "
                 f"{fr(l['kill_rate'])} | {fr(p['gap_llm_minus_operator'])} | {p['paired_tasks']} |")
    (args.witness / "rq1_robustness.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
