"""Gate G2 (plan rev. 9.3, Stage 2): decide whether the witness engine may run on the evaluation tasks.

    python scripts/gate_g2.py --config config/tier2_extensions.yaml \
        --pilot results_tier2_ext/witness/dev_pilot_freia

Checks (all must hold; recorded in <pilot>/G2.json and G2.md):
  fixtures            the G2 fixture tests pass (state-dependent fault -> replayed API witness,
                      private-only -> private_state_only, reference exception -> domain_uncertain,
                      mutant-only exception -> api_exception, own-class contract equality,
                      contract-valid generation, never "equivalent", canary/tree-kill)
  authoritative       the pilot ran with the gate manifest
  all_dev_tasks       one witness.json per development task, no failed task
  reviewed_contracts  every supported task used a reviewed contract
  taxonomy            outcomes only from the frozen set; every unresolved says "not an equivalence certificate"
  canary              the pilot's canary verdict was ok
  replay_stored       every distinguished group was replay-confirmed in the run
  replay_independent  every witness reproduces NOW, in fresh processes (reference twice, mutant twice),
                      from the stored witness and the frozen mutant code (hash-checked)

Reported, not gated: support coverage and witness yield (they decide the scale). The full run
(run_witness.py --tasks eval --g2 <pilot>/G2.json) refuses to start unless this record passed and
its witness settings equal the full run's.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.benchmarks.contracts import api_rules, load_contract  # noqa: E402
from meta_real_eval.benchmarks.witness import GEN_ALIAS, WitnessSettings, _p_pool, _replay  # noqa: E402
from meta_real_eval.core.provenance import git_state  # noqa: E402
from meta_real_eval.oracles.fault_groups import load_split  # noqa: E402

FIXTURE_TESTS = ["tests/test_witness/test_witness_engine.py", "tests/test_witness/test_api_observe.py",
                 "tests/test_witness/test_contracts_and_groups.py", "tests/test_ext/test_exec_protection.py"]
OUTCOMES = {"distinguished", "unresolved", "unsupported", "timeout", "invalid_artifact"}
RUN_ONLY = ("tasks", "gated", "workers")


def run_fixtures() -> dict:
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *FIXTURE_TESTS],
                       cwd=ec.REPO, capture_output=True, text=True)
    return {"ok": p.returncode == 0, "returncode": p.returncode, "tail": (p.stdout + p.stderr).strip().splitlines()[-5:]}


def static_checks(results: list[dict], manifest: dict, development: list[str], failed: list[str]) -> dict:
    """Every check that needs only the stored pilot files."""
    groups = [(r, g) for r in results for g in r["groups"]]
    outcomes = Counter(g["outcome"] for _, g in groups)
    bad_unresolved = [f"{r['task']}/{g['group_id']}" for r, g in groups
                      if g["outcome"] == "unresolved" and "not an equivalence certificate" not in (g.get("reason") or "")]
    unreviewed = [r["task"] for r in results if r["support"]["supported"] and r["contract"]["status"] != "reviewed"]
    not_replayed = [f"{r['task']}/{g['group_id']}" for r, g in groups
                    if g["outcome"] == "distinguished" and not (g.get("replay") or {}).get("confirmed")]
    canary_ok = ((manifest.get("checks") or {}).get("canary") or {}).get("verdict", {}).get("ok", False)
    seen = {r["task"] for r in results}
    return {
        "authoritative": {"ok": bool(manifest.get("settings", {}).get("gated"))},
        "all_dev_tasks": {"ok": seen == set(development) and not failed,
                          "missing": sorted(set(development) - seen), "failed": failed},
        "reviewed_contracts": {"ok": not unreviewed, "unreviewed": unreviewed},
        "taxonomy": {"ok": set(outcomes) <= OUTCOMES and not bad_unresolved, "outcomes": dict(outcomes),
                     "unknown": sorted(set(outcomes) - OUTCOMES), "unresolved_without_disclaimer": bad_unresolved},
        "canary": {"ok": bool(canary_ok)},
        "replay_stored": {"ok": not not_replayed, "not_replayed": not_replayed},
    }


def replay_target(g: dict) -> tuple[str, str]:
    """The (level, domain) the engine searched for: nontermination is stored as level api_visible + kind."""
    return ("nontermination" if g.get("kind") == "nontermination" else g["level"]), g["domain"]


def independent_replays(results: list[dict], tasks: dict, cfg, settings: WitnessSettings) -> dict:
    bench = get_benchmark(cfg)
    baseline = Path(cfg.extensions.baseline_scores)
    split_groups, _ = load_split(ec.PROTOCOL_DIR / "fault_split_v1.json")
    rows = []
    for r in results:
        wits = [g for g in r["groups"] if g["outcome"] == "distinguished"]
        if not wits:
            continue
        task = tasks[r["task"]]
        contract = load_contract(ec.REPO / r["contract"]["path"])
        excluded = set(task.meta.get("scenarios", {}).get("excluded", {})) if r["gated"] else set()
        p_header, p_alias, _ = _p_pool(task, contract, excluded)
        ctx = {"module": task.module_name, "reference": task.reference_code, "contract": contract,
               "rules": api_rules(contract),
               "pools": {"p": {"header": p_header, "alias": p_alias},
                         "gen": {"header": f"import {task.module_name} as {GEN_ALIAS}\n", "alias": GEN_ALIAS}}}
        records = {x["record_id"]: x for x in ec.collect_fault_records(bench, task, baseline)}
        for g in wits:
            rec = records.get(g["representative"])
            frozen = next((m["code_sha256"] for m in split_groups[r["task"]][g["group_id"]]["members"]
                           if m["record_id"] == g["representative"]), None)
            if rec is None or hashlib.sha256(rec["code"].encode()).hexdigest() != frozen:
                rows.append({"task": r["task"], "group_id": g["group_id"], "confirmed": False,
                             "reason": "mutant code differs from the frozen split"})
                continue
            w = g["witness"]
            sc = {"scenario_id": w["scenario_id"], "steps": w["steps"], "api_flags": w["api_flags"]}
            pool = "p" if g["origin"] == "p_scenario" else "gen"
            rep = _replay(ctx, pool, sc, replay_target(g), rec["code"], settings)
            rows.append({"task": r["task"], "group_id": g["group_id"], "level": g["level"], "kind": g.get("kind"),
                         "domain": g["domain"], **rep})
    bad = [f"{x['task']}/{x['group_id']}" for x in rows if not x["confirmed"]]
    return {"ok": not bad, "replayed": len(rows), "not_reproduced": bad, "rows": rows}


def report(results: list[dict]) -> dict:
    sup = [r for r in results if r["support"]["supported"]]
    prim = lambda g: (g["outcome"] == "distinguished" and g["level"] == "api_visible"  # noqa: E731
                      and g["domain"] == "valid" and (g.get("replay") or {}).get("confirmed"))
    per_task = {r["task"]: {"groups": len(r["groups"]), "primary": sum(prim(g) for g in r["groups"])} for r in sup}
    n_groups = sum(v["groups"] for v in per_task.values())
    n_prim = sum(v["primary"] for v in per_task.values())
    return {"tasks": len(results), "tasks_supported": len(sup), "groups_on_supported": n_groups,
            "primary_confirmed": n_prim, "primary_yield": (n_prim / n_groups if n_groups else None),
            "per_supported_task": per_task,
            "unsupported_reasons": dict(Counter("; ".join(r["support"]["reasons"]) for r in results
                                                if not r["support"]["supported"]))}


def write_md(rec: dict, path: Path) -> None:
    L = [f"# Gate G2: {'PASSED' if rec['passed'] else 'NOT PASSED'}", "",
         f"Pilot `{rec['pilot']}` (summary sha256 `{rec['pilot_summary_sha256'][:12]}`), {rec['created_utc']}, "
         f"git `{rec['git'].get('commit') or '?'}`.", "",
         "| check | ok |", "|---|---|"]
    L += [f"| {k} | {'yes' if v['ok'] else '**NO**'} |" for k, v in rec["checks"].items()]
    r = rec["report"]
    L += ["", "## Scale (reported, not gated)", "",
          f"- Supported development tasks: {r['tasks_supported']}/{r['tasks']}.",
          f"- Primary confirmed groups: {r['primary_confirmed']} of {r['groups_on_supported']} on supported tasks "
          f"(yield {r['primary_yield'] if r['primary_yield'] is None else round(r['primary_yield'], 3)}).",
          f"- Independent replays: {rec['checks']['replay_independent'].get('replayed', 0)}.", ""]
    if rec["failed_checks"]:
        L += ["## Failed checks", ""] + [f"- {k}: {json.dumps({x: y for x, y in rec['checks'][k].items() if x != 'rows'})}"
                                         for k in rec["failed_checks"]]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--pilot", type=Path, required=True)
    ap.add_argument("--ungated", action="store_true", help="local dry run: the record can never pass")
    args = ap.parse_args(argv)
    cfg = ec.load_ext_config(args.config)
    manifest = json.loads((args.pilot / "run_manifest.json").read_text(encoding="utf-8"))
    summary_raw = (args.pilot / "summary.json").read_bytes()
    results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.pilot.glob("*/witness.json"))]
    failed = sorted(p.parent.name for p in args.pilot.glob("*/error.txt"))
    settings_d = {k: v for k, v in manifest["settings"].items() if k not in RUN_ONLY}
    settings = WitnessSettings(**settings_d)
    policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=True)
    policy.activate()
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    checks = {"fixtures": run_fixtures(), **static_checks(results, manifest, list(cfg.extensions.development_tasks), failed),
              "replay_independent": independent_replays(results, tasks, cfg, settings)}
    failed_checks = [k for k, v in checks.items() if not v["ok"]]
    rec = {"gate": "G2", "passed": not failed_checks and gated, "gated": gated, "failed_checks": failed_checks,
           "pilot": str(args.pilot), "pilot_summary_sha256": hashlib.sha256(summary_raw).hexdigest(),
           "witness_settings": dataclasses.asdict(settings), "checks": checks, "report": report(results),
           "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git": git_state()}
    (args.pilot / "G2.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    write_md(rec, args.pilot / "G2.md")
    print((args.pilot / "G2.md").read_text(encoding="utf-8"))
    return 0 if rec["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
