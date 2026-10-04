#!/usr/bin/env python
"""Calibrate Tier 2's rq3.divergence_threshold, with a frozen-before-headline
calibration/held-out split (see src/meta_real_eval/analysis/calibration.py).

Unlike Tier 1's ``scripts/analyze_results.py --calibrate`` (which fits the
production threshold on the FULL sample and reports a held-out split only as
a secondary diagnostic), this script's headline number -- the one to quote
for how well τ_div separates benchmark-failing solutions -- is computed
EXCLUSIVELY on the held-out half. The threshold written to config is fit only
from the calibration half.

Per-task score/label, same definition as Tier 1's analyze_rq3:

    score = pairwise_disagreement_rate      (RQ3 divergence.json)
    label = 1 if ANY scored solution on the task fails the benchmark, else 0

The calibration/held-out split is stratified by RealClassEval's split (csn /
post-cutoff) via stratified_calibration_split, not Tier 1's flat 50/50.

    .venv/bin/python scripts/calibrate_tau_div_tier2.py --config config/tier2_realclasseval.yaml

Needs RQ2 evaluate + RQ3 execute to have already run for enough tasks (see
MIN_TASKS_PER_HALF below) -- at the time this script was written, that data
does not exist yet (M1/M3 have not run), so it will correctly refuse with
"not enough data" until they have. Its logic is exercised with synthetic
fixtures in tests/test_scripts/test_calibrate_tau_div_tier2.py so the
mechanism is already proven correct before there is anything real to run it on.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.analysis.calibration import (  # noqa: E402
    calibrate_and_freeze,
    calibration_record,
    stratified_calibration_split,
)
from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.config import CalibrationError, Config, write_divergence_threshold  # noqa: E402

# Below this many tasks per half, a Youden's J fit or a held-out ROC-AUC is
# fitted to noise -- refuse rather than freeze a number nobody should trust.
MIN_TASKS_PER_HALF = 20


def collect_task_scores_and_labels(cfg: Config, tasks) -> tuple[dict[str, float], dict[str, int], dict[str, str]]:
    """Per task: (pairwise_disagreement_rate, label, split), for tasks where
    both RQ3 divergence and RQ2-consistent per-solution labels are available.

    Mirrors scripts/analyze_results.py::analyze_rq3's score/label construction
    exactly (same task-level unit the Tier 2 plan's D8 framing calibrates on).
    """
    from meta_real_eval.core.checkpoint import read_json, task_dir

    scores: dict[str, float] = {}
    labels: dict[str, int] = {}
    split_of: dict[str, str] = {}

    for task in tasks:
        rq3_out = task_dir(cfg, "rq3", task.label, phase="execute")
        try:
            dv = read_json(rq3_out, "divergence.json")
        except FileNotFoundError:
            continue

        rate = dv.get("pairwise_disagreement_rate")
        sols = dv.get("solutions", [])
        scored = [s for s in sols if "passes_benchmark" in s]
        if rate is None or not scored:
            continue

        scores[task.task_id] = rate
        labels[task.task_id] = int(any(not s["passes_benchmark"] for s in scored))
        split_of[task.task_id] = task.split or "unknown"

    return scores, labels, split_of


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/tier2_realclasseval.yaml")
    parser.add_argument("--output", type=Path, default=None,
                        help="calibration record path (default: <manifest dir>/tau_div_calibration.json)")
    parser.add_argument("--min-tasks-per-half", type=int, default=MIN_TASKS_PER_HALF)
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and print the calibration without writing the config or a record")
    args = parser.parse_args()

    cfg = Config.from_yaml(args.config)
    bench = get_benchmark(cfg)
    tasks = bench.load_tasks(cfg.benchmark.tasks)

    scores, labels, split_of = collect_task_scores_and_labels(cfg, tasks)
    n = len(scores)
    print(f"{n}/{len(tasks)} task(s) have both an RQ3 divergence rate and a scored solution")
    if n < 2 * args.min_tasks_per_half:
        print(f"ERROR: need at least {2 * args.min_tasks_per_half} such tasks "
             f"({args.min_tasks_per_half} per half) to calibrate without fitting noise. "
             "Run RQ2 evaluate + RQ3 execute over more tasks first (M1/M3), then retry.",
             file=sys.stderr)
        return 1

    task_ids = sorted(scores)
    calibration_ids, holdout_ids = stratified_calibration_split(
        task_ids, [split_of[t] for t in task_ids], seed=cfg.project.seed,
    )
    if len(calibration_ids) < args.min_tasks_per_half or len(holdout_ids) < args.min_tasks_per_half:
        print(f"ERROR: the split gave {len(calibration_ids)}/{len(holdout_ids)} "
             f"(calibration/holdout); need >= {args.min_tasks_per_half} each.", file=sys.stderr)
        return 1

    result = calibrate_and_freeze(
        [scores[t] for t in calibration_ids], [labels[t] for t in calibration_ids],
        [scores[t] for t in holdout_ids], [labels[t] for t in holdout_ids],
        calibration_task_ids=calibration_ids, holdout_task_ids=holdout_ids,
    )

    print(f"calibration: n={result.n_calibration}, in-sample Youden J={result.calibration_fit.get('youden_j')}")
    print(f"FROZEN threshold: {result.threshold}")
    print(f"headline (held-out, n={result.n_holdout}): {result.headline}")

    if not result.frozen:
        print("ERROR: calibration half was degenerate (one class only) -- cannot freeze a threshold.",
             file=sys.stderr)
        return 1

    if args.dry_run:
        print("--dry-run: not writing the config or a calibration record.")
        return 0

    source_path = Path(cfg.benchmark.data_path or "") if cfg.benchmark.data_path else None
    corpus_sha256 = None
    if source_path and (source_path.parent / "source.json").exists():
        corpus_sha256 = json.loads((source_path.parent / "source.json").read_text())["corpus_sha256"]

    record = calibration_record(
        result,
        corpus_sha256=corpus_sha256,
        seed=cfg.project.seed,
        config_path=str(args.config),
        generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    output = args.output
    if output is None:
        # cfg.benchmark.manifest_path only has an intentional directory for
        # RealClassEval; a config without one (e.g. HumanEval, or a test
        # fixture) must not default to "." and write into whatever directory
        # the script happens to be run from -- project.output_dir always
        # exists and is already specific to this run.
        base = Path(cfg.benchmark.manifest_path).parent if cfg.benchmark.manifest_path \
            else Path(cfg.project.output_dir)
        base.mkdir(parents=True, exist_ok=True)
        output = base / "tau_div_calibration.json"
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"calibration record -> {output}")

    try:
        previous = write_divergence_threshold(args.config, result.threshold)
    except CalibrationError as exc:
        print(f"ERROR writing threshold to {args.config}: {exc}", file=sys.stderr)
        return 1
    print(f"wrote rq3.divergence_threshold = {result.threshold} to {args.config} (was {previous})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
