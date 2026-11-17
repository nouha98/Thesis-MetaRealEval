"""Freeze the Stage 2b coupling specification (protocol_freeze_decisions.md section 9).

    python scripts/freeze_coupling.py --config config/tier2_extensions.yaml [--ungated]
    python scripts/freeze_coupling.py --config config/tier2_extensions.yaml --check

Writes config/extensions_protocol/coupling_v1.json once: the SPEC from oracles/coupling.py, its
sha256, and the per-task digest of the solution groups (built from the stored RQ2 completions).
Run after the technical pilot and before any endpoint is computed. Refuses to overwrite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.provenance import git_state  # noqa: E402
from meta_real_eval.oracles.coupling import SPEC  # noqa: E402
from meta_real_eval.oracles.solution_groups import build_solution_groups, digest  # noqa: E402

OUT = ec.PROTOCOL_DIR / "coupling_v1.json"


def document(cfg, tasks: dict) -> dict:
    bench = get_benchmark(cfg)
    base = Path(cfg.extensions.baseline_scores)
    digests, counts = {}, {}
    for lab in sorted(tasks):
        comps = ec.read_json(base / "rq2" / "generate" / lab / "completions.json", {})
        rates = ec.read_json(base / "rq2" / "evaluate" / lab / "pass_rates.json", {})
        g = build_solution_groups(lab, comps, rates, lambda c, t=tasks[lab]: bench.build_solution(t, c))
        digests[lab], counts[lab] = digest(g), len(g)
    return {"format": 1, "spec": SPEC, "spec_sha256": hashlib.sha256(json.dumps(SPEC, sort_keys=True).encode()).hexdigest(),
            "solution_groups": digests, "solution_group_counts": counts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--ungated", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    cfg = ec.load_ext_config(args.config)
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    doc = document(cfg, tasks)
    if args.check:
        fz = ec.read_json(OUT, None)
        bad = ["not frozen"] if fz is None else [k for k in ("spec_sha256", "solution_groups") if fz[k] != doc[k]]
        print(json.dumps({"gated": gated, "problems": bad}))
        return int(bool(bad))
    if OUT.exists():
        raise SystemExit(f"ERROR: {OUT} is already frozen (use --check)")
    doc.update(created_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), gated=gated, git=git_state())
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    print(f"froze {OUT}: spec {doc['spec_sha256'][:12]}, {len(doc['solution_groups'])} tasks, "
          f"{sum(doc['solution_group_counts'].values())} solution groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
