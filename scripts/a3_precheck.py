"""A3 pre-check (development tasks only): can a docstring-property test catch the faults A2 misses?

    python scripts/a3_precheck.py --config config/tier2_extensions.yaml \
        --heldout results_tier2_ext/a2/dev_k5_r7b/heldout.json \
        --witness results_tier2_ext/witness/dev_pilot_reviewed \
        --out results_tier2_ext/a3/precheck.md

Lists every primary-confirmed held-out development group that no A2 test detects (the groups A3 needs for
section 7 condition 3), with the fault's diff against the reference, the stored witness and the skeleton.
Per group, the researcher judges: does the fault break a property the docstring STATES (quote it), or only
behaviour the docstring leaves open?

Decision rule (fixed before judging, mirrors condition 3): the A3 pilot runs only if at least 3 development
tasks have >= 1 group judged "breaks a stated property". Otherwise A3 cannot meet condition 3 with docstring
properties, and H = A2 is frozen.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402


def missed_groups(rows: list[dict], development: set) -> list[dict]:
    """Primary held-out development groups that no A2 test detects (the condition-3 candidates)."""
    return [r for r in rows if r["task"] in development and r["h_detected"] is False
            and any(p.startswith("primary") for p in r["populations"])]


def diff(ref: str, code: str, name: str) -> str:
    return "".join(difflib.unified_diff(ref.splitlines(True), code.splitlines(True), "reference", name, n=2))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--heldout", type=Path, required=True)
    ap.add_argument("--witness", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ungated", action="store_true")
    args = ap.parse_args(argv)
    cfg = ec.load_ext_config(args.config)
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    bench = get_benchmark(cfg)
    baseline = Path(cfg.extensions.baseline_scores)
    rows = missed_groups(json.loads(args.heldout.read_text(encoding="utf-8"))["rows"],
                         set(cfg.extensions.development_tasks))
    by_task: dict[str, list] = {}
    for r in rows:
        by_task.setdefault(r["task"], []).append(r)
    L = ["# A3 pre-check: faults A2 misses on the development tasks", "",
         f"*{'authoritative' if gated else 'NOT authoritative'}; {len(rows)} groups on {len(by_task)} tasks; "
         f"held-out file `{args.heldout}`.*", "",
         "Per group: **stated** (the fault breaks a property the docstring states: quote it) / **open** (only "
         "behaviour the docstring leaves open) / **unclear**. Judge against the skeleton, not the reference.", "",
         "Rule (fixed before judging): the A3 pilot runs only if >= 3 tasks have >= 1 group judged *stated*.", ""]
    for lab, rs in sorted(by_task.items()):
        task = tasks[lab]
        wit = {g["group_id"]: g for g in json.loads((args.witness / lab / "witness.json")
                                                     .read_text(encoding="utf-8"))["groups"]}
        records = {x["record_id"]: x for x in ec.collect_fault_records(bench, task, baseline)}
        L += [f"## {lab} ({len(rs)} group(s))", "", "<details><summary>skeleton (what the models saw)</summary>", "",
              "```python", task.prompt.strip(), "```", "", "</details>", ""]
        for r in rs:
            g = wit[r["group_id"]]
            w = g.get("witness") or {}
            L += [f"### {lab} / {r['group_id']}", "",
                  f"- source {r['source']}; P kills it: **{r['p_killed']}**; witness level {g.get('level')}, "
                  f"kind {g.get('kind')}, origin {g.get('origin')}",
                  f"- witness steps: " + "; ".join(f"`{s['src'][:140]}`" for s in w.get("steps", [])),
                  f"- API difference: {w.get('difference')}", "", "```diff",
                  diff(task.reference_code, records[g["representative"]]["code"], g["representative"]).strip(),
                  "```", "", "Verdict (stated / open / unclear), with the docstring quote: ______", ""]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{len(rows)} A2-missed group(s) on {len(by_task)} task(s): "
          f"{ {k: len(v) for k, v in sorted(by_task.items())} } -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
