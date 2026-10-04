#!/usr/bin/env python
"""M1(a): fork-server traces must equal fresh-process traces; report throughput.

For each pilot task, the reference and its first --mutants Stage 0 mutants are
run over the same scenario pool twice: once in fork mode (production) and once
in single mode (one fresh process per scenario). Status and tokens must match
exactly. Fork mode is Linux-only, so run this on the cluster:

    .venv/bin/python scripts/prototype_scenarios.py --config config/tier2_m1_pilot.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.benchmarks.forkserver import run_scenarios  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402
from meta_real_eval.stage0.corpus_builder import generate_mutants  # noqa: E402


def _timed(code: str, task, pool, mode: str, timeout_s: float):
    t0 = time.perf_counter()
    obs = run_scenarios(task.module_name, code, pool.header, pool.items,
                        timeout_s=timeout_s, mode=mode)
    return obs, time.perf_counter() - t0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/tier2_m1_pilot.yaml")
    parser.add_argument("--mutants", type=int, default=3)
    parser.add_argument("--pool-size", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=10.0, help="per-scenario timeout (gate used 10 s)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    cfg = Config.from_yaml(args.config)
    bench = get_benchmark(cfg)
    rows = []
    for task in bench.load_tasks(cfg.benchmark.tasks):
        pool = bench.input_pool(task, args.pool_size, cfg.project.seed)
        mutants = generate_mutants(
            prompt="",
            canonical_solution=bench.mutation_source(task),
            entry_point=task.target,
            operators=cfg.rq1.operators,
            max_per_operator=cfg.stage0.max_mutants_per_operator,
            seed=cfg.project.seed,
            sdl_scope=bench.sdl_scope(task),
        )
        codes = [("reference", task.reference_code)]
        codes += [(m.mutant_id, m.code) for m in mutants[: args.mutants]]

        for name, code in codes:
            fork, t_fork = _timed(code, task, pool, "fork", args.timeout)
            fresh, t_fresh = _timed(code, task, pool, "single", args.timeout)
            differing = sum(
                1 for a, b in zip(fork, fresh)
                if a["status"] != b["status"] or a["tokens"] != b["tokens"]
            )
            n = max(len(pool.items), 1)
            row = {
                "task_id": task.task_id,
                "code": name,
                "n_scenarios": len(pool.items),
                "identical": differing == 0 and len(fork) == len(fresh),
                "differing": differing,
                "fork_s_per_scenario": round(t_fork / n, 4),
                "fresh_s_per_scenario": round(t_fresh / n, 4),
            }
            rows.append(row)
            print(f"{row['task_id']:38s} {name:12s} identical={row['identical']} "
                  f"differing={differing}/{n} fork={row['fork_s_per_scenario']}s "
                  f"fresh={row['fresh_s_per_scenario']}s", flush=True)

    out = args.out or Path(cfg.project.output_dir) / "prototype" / "prototype.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    all_identical = all(r["identical"] for r in rows)
    print(f"\n{len(rows)} runs, all identical: {all_identical} -> {out}")
    return 0 if all_identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
