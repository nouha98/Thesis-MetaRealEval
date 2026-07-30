"""RQ4 runner: MT augmentation, test suite degradation, and interaction analysis.

Phases
------
degrade
    Degrade task test suites at each level; re-evaluate cached completions.
    CPU-bound → SLURM job array.

augment
    Build MT-augmented test suites from RQ3 consistency assertions and
    re-evaluate under them.  CPU-bound → SLURM job array.

analyze
    Aggregate all per-task results; compute interaction statistics (Page's L).
    CPU-bound → single SLURM job.

Usage
-----
    python -m meta_real_eval.rq4.runner --config config/default.yaml --phase degrade --task-index 42
    python -m meta_real_eval.rq4.runner --config config/default.yaml --phase augment --task-index 42
    python -m meta_real_eval.rq4.runner --config config/default.yaml --phase analyze
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from ..core.checkpoint import is_done, mark_done, task_dir, write_json, read_json
from ..core.config import Config
from ..core.data_loader import load_humaneval, task_label
from ..core.logging_setup import setup as setup_logging
from ..rq2.evaluator import _run_completion, pass_at_k
from .consistency import build_consistency_assertions
from .degradation import degrade_all_levels
from .interaction import compute_tau_at_degradation_level, pages_l_trend_test

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Degrade phase
# ---------------------------------------------------------------------------

def run_degrade_one(task, cfg: Config) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq4", label, phase="degrade")

    if is_done(out):
        logger.info("SKIP degrade %s", label)
        return

    gen_out = task_dir(cfg, "rq2", label, phase="generate")
    try:
        completions_data: dict = read_json(gen_out, "completions.json")
    except FileNotFoundError:
        logger.error("Missing RQ2 completions for %s", label)
        return

    degraded_tests = degrade_all_levels(
        task.test, cfg.rq4.degradation_levels, seed=cfg.project.seed
    )

    results: dict[str, dict] = {}
    for level, degraded_test in degraded_tests.items():
        tau_by_model = compute_tau_at_degradation_level(
            task, completions_data, degraded_test, cfg
        )
        results[str(level)] = {
            "model_taus": tau_by_model,
            "degradation_level": level,
        }

    # Page's L: use mean across models
    tau_by_level = {
        float(lv): float(
            sum(d["model_taus"].values()) / max(len(d["model_taus"]), 1)
        )
        for lv, d in results.items()
    }
    trend = pages_l_trend_test(tau_by_level)
    results["trend_test"] = trend

    write_json(out, "degradation_analysis.json", results)
    mark_done(out)
    logger.info("Degrade %s: trend p=%.3f", label, trend.get("p_value_approx", float("nan")))


# ---------------------------------------------------------------------------
# Augment phase
# ---------------------------------------------------------------------------

def run_augment_one(task, cfg: Config) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq4", label, phase="augment")

    if is_done(out):
        logger.info("SKIP augment %s", label)
        return

    # Load RQ3 divergence
    rq3_out = task_dir(cfg, "rq3", label, phase="execute")
    try:
        divergence_data: dict = read_json(rq3_out, "divergence.json")
    except FileNotFoundError:
        logger.warning("Missing RQ3 divergence for %s — skipping augment", label)
        return

    # Load RQ2 completions
    gen_out = task_dir(cfg, "rq2", label, phase="generate")
    try:
        completions_data: dict = read_json(gen_out, "completions.json")
    except FileNotFoundError:
        logger.error("Missing RQ2 completions for %s", label)
        return

    # Build consistency assertion code
    ca_code = build_consistency_assertions(
        task=task,
        divergence_data=divergence_data,
        threshold=cfg.rq3.divergence_threshold,
        seed=cfg.project.seed,
    )

    # MT-augmented test = degraded test @ 50% + consistency assertions
    degraded_50 = degrade_all_levels(task.test, [0.5], seed=cfg.project.seed)[0.5]
    augmented_test = degraded_50 + "\n" + ca_code if ca_code else degraded_50

    # Evaluate completions under MT-augmented suite
    tau_by_model = compute_tau_at_degradation_level(
        task, completions_data, augmented_test, cfg
    )

    results = {
        "has_consistency_assertions": bool(ca_code),
        "model_taus_under_augmented": tau_by_model,
    }
    write_json(out, "augment_analysis.json", results)
    mark_done(out)
    logger.info("Augment %s: taus=%s", label, tau_by_model)


# ---------------------------------------------------------------------------
# Analyze phase (aggregate)
# ---------------------------------------------------------------------------

def run_analyze(cfg: Config, tasks) -> None:
    """Aggregate per-task results into a cross-task summary."""
    out = cfg.project.output_dir / "rq4" / "summary"
    out.mkdir(parents=True, exist_ok=True)

    all_trends: list[dict] = []
    all_augment: list[dict] = []

    for task in tasks:
        label = task_label(task)

        degrade_out = task_dir(cfg, "rq4", label, phase="degrade")
        try:
            d = read_json(degrade_out, "degradation_analysis.json")
            trend = d.get("trend_test", {})
            trend["task_id"] = task.task_id
            all_trends.append(trend)
        except FileNotFoundError:
            pass

        aug_out = task_dir(cfg, "rq4", label, phase="augment")
        try:
            a = read_json(aug_out, "augment_analysis.json")
            a["task_id"] = task.task_id
            all_augment.append(a)
        except FileNotFoundError:
            pass

    write_json(out, "trend_summary.json", all_trends)
    write_json(out, "augment_summary.json", all_augment)

    # High-level statistics
    sig_monotonic = [t for t in all_trends if t.get("monotonic_decrease_in_tau")]
    logger.info(
        "RQ4 analyze: %d/%d tasks show significant monotonic tau_b decrease",
        len(sig_monotonic), len(all_trends),
    )
    write_json(out, "high_level.json", {
        "n_tasks": len(all_trends),
        "n_monotonic_significant": len(sig_monotonic),
        "fraction": len(sig_monotonic) / max(len(all_trends), 1),
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="RQ4: MT augmentation and interaction")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--phase", choices=["degrade", "augment", "analyze"], required=True)
    parser.add_argument("--task-index", type=int, default=None)
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    setup_logging("rq4", args.phase, log_dir=Path("logs"))

    task_filter = [args.task_index] if args.task_index is not None else cfg.benchmark.tasks
    tasks = load_humaneval(tasks=task_filter)
    logger.info("RQ4 phase=%s, %d task(s)", args.phase, len(tasks))

    if args.phase == "degrade":
        for task in tasks:
            run_degrade_one(task, cfg)
    elif args.phase == "augment":
        for task in tasks:
            run_augment_one(task, cfg)
    else:
        run_analyze(cfg, tasks)

    logger.info("RQ4 phase=%s complete.", args.phase)


if __name__ == "__main__":
    main()
