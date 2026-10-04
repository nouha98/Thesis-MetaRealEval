#!/usr/bin/env python
"""M1(c): generation audit for stored RQ2 completions.

Per (relation, model), counts how each completion classifies under the D7
extraction (fenced / raw / trimmed / failed). ``trimmed`` means the raw output
yielded a class only after it was cut back to the part that parses, the usual
signature of a truncated completion; ``failed`` means no top-level class was
found. Finish reasons are not stored, so truncation is inferred from the text.

    .venv/bin/python scripts/audit_rq2_generation.py --config config/tier2_m1_pilot.yaml
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.benchmarks.realclasseval import build_solution_with_report  # noqa: E402
from meta_real_eval.core.checkpoint import read_json, task_dir  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/tier2_m1_pilot.yaml")
    args = parser.parse_args()

    cfg = Config.from_yaml(args.config)
    tasks = get_benchmark(cfg).load_tasks(cfg.benchmark.tasks)

    cells: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
    missing_tasks = []
    for task in tasks:
        try:
            data = read_json(task_dir(cfg, "rq2", task.label, phase="generate"), "completions.json")
        except FileNotFoundError:
            missing_tasks.append(task.task_id)
            continue
        for relation, by_model in data.items():
            for model, completions in by_model.items():
                cell = cells[(relation, model)]
                if not completions:
                    cell["empty_cell"] += 1
                    continue
                for completion in completions:
                    _, report = build_solution_with_report(completion, task.prompt, task.target)
                    cell["completions"] += 1
                    cell[report.extraction] += 1
                    cell["reattached_imports"] += len(report.imports_reattached)

    print(f"{'relation':18s} {'model':30s} {'n':>5s} {'fenced':>7s} {'raw':>5s} "
          f"{'trimmed':>8s} {'failed':>7s} {'empty':>6s} {'reattach':>9s}")
    rows = []
    for (relation, model), c in sorted(cells.items()):
        n = c["completions"]
        pct = lambda k: f"{c[k] / n:.1%}" if n else "-"  # noqa: E731
        print(f"{relation:18s} {model:30s} {n:5d} {pct('fenced'):>7s} {pct('raw'):>5s} "
              f"{pct('trimmed'):>8s} {pct('failed'):>7s} {c['empty_cell']:6d} {c['reattached_imports']:9d}")
        rows.append({"relation": relation, "model": model, "n": n, "fenced": c["fenced"],
                     "raw": c["raw"], "trimmed": c["trimmed"], "failed": c["failed"],
                     "empty_cell": c["empty_cell"], "reattached_imports": c["reattached_imports"]})
    if missing_tasks:
        print(f"\nno completions.json for {len(missing_tasks)} task(s): {missing_tasks}")

    out = Path(cfg.project.output_dir) / "rq2_generation_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    print(f"\nwritten -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
