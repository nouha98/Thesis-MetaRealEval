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

from collections import Counter

from scipy.stats import norm

from ..core.checkpoint import add_force_arg, clear_done, is_done, mark_done, task_dir, write_json, read_json
from ..core.config import Config
from ..core.data_loader import load_humaneval, task_label
from ..core.logging_setup import setup as setup_logging
from ..core.task_selection import add_task_selection_args, resolve_task_filter
from ..analysis.statistics import spearman_rho, wilcoxon_test
from ..rq2.evaluator import _run_completion, pass_at_k
from ..rq2.ranking import _rank_vector
from .consistency import DEFAULT_DIVERGENCE_THRESHOLD, build_consistency_assertions
from .degradation import degrade_all_levels
from .interaction import compute_tau_at_degradation_level

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Degrade phase
# ---------------------------------------------------------------------------

def run_degrade_one(task, cfg: Config, force: bool = False) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq4", label, phase="degrade")

    if force:
        clear_done(out)

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
        summary = compute_tau_at_degradation_level(
            task, completions_data, degraded_test, cfg
        )
        results[str(level)] = {**summary, "degradation_level": level}

    # No per-task trend test here: Page's L is a randomized-block statistic and
    # one task is a single block. The per-level tau_b values written above are
    # the blocks; scripts/analyze_results.py pools them across tasks and runs
    # the test once (see analysis.statistics.pages_l_test).
    write_json(out, "degradation_analysis.json", results)
    mark_done(out)
    defined = [d["mean_tau_b"] for d in results.values() if d.get("mean_tau_b") is not None]
    logger.info("Degrade %s: tau_b defined at %d/%d level(s)", label, len(defined), len(results))


# ---------------------------------------------------------------------------
# Augment phase
# ---------------------------------------------------------------------------

def run_augment_one(task, cfg: Config, force: bool = False) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq4", label, phase="augment")

    if force:
        clear_done(out)

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

    # Build consistency assertion code from RQ3's majority-vote consensus.
    ca_code, n_assertions = build_consistency_assertions(
        task=task,
        divergence_data=divergence_data,
        threshold=cfg.rq3.divergence_threshold,
    )

    if cfg.rq3.divergence_threshold is None:
        logger.warning(
            "rq3.divergence_threshold is NOT calibrated - falling back to %s. "
            "Calibrate it from the Tier-1 pilot ROC curve before the full run; "
            "these results are tagged threshold_calibrated=false.",
            DEFAULT_DIVERGENCE_THRESHOLD,
        )

    results: dict = {
        "has_consistency_assertions": bool(ca_code),
        "n_consistency_assertions": n_assertions,
        # None when RQ3 found no comparable outputs at all; kept as null rather
        # than coerced to 0.0, which would read as "the solutions agree".
        "divergence_rate": divergence_data.get("pairwise_disagreement_rate"),
        "threshold_calibrated": cfg.rq3.divergence_threshold is not None,
        "divergence_threshold_used": (
            cfg.rq3.divergence_threshold
            if cfg.rq3.divergence_threshold is not None
            else DEFAULT_DIVERGENCE_THRESHOLD
        ),
    }

    # One augmented suite per degradation level, keyed the same way as
    # degradation_analysis.json, so rank recovery can be read at every level
    # instead of only at the single 50% point the old code hardcoded.
    degraded = degrade_all_levels(task.test, cfg.rq4.degradation_levels, seed=cfg.project.seed)
    for level, degraded_test in degraded.items():
        augmented_test = degraded_test + "\n" + ca_code if ca_code else degraded_test
        summary = compute_tau_at_degradation_level(task, completions_data, augmented_test, cfg)
        results[str(level)] = {**summary, "degradation_level": level}

    write_json(out, "augment_analysis.json", results)
    mark_done(out)
    logger.info("Augment %s: %d consistency assertion(s) over %d level(s)",
                label, n_assertions, len(degraded))


# ---------------------------------------------------------------------------
# Analyze phase (aggregate)
# ---------------------------------------------------------------------------

BASELINE_LEVEL = "0.0"
BASELINE_RELATION = "original"


def _mde(a: list[float], b: list[float], alpha: float = 0.05, power: float = 0.80) -> dict:
    """Smallest mean paired difference this sample size could detect.

    Reported so a null result can be read as informative rather than merely
    underpowered: "no recovery detected, and we could have detected 0.02"
    says something, while "no recovery detected" on its own does not.

    A normal approximation to the paired t-test (z_alpha/2 + z_power) * sd /
    sqrt(n). The actual test is Wilcoxon signed-rank, which is somewhat less
    efficient under normality and more efficient under heavy tails, so treat
    this as an order-of-magnitude guide rather than an exact bound.
    """
    n = len(a)
    if n < 2:
        return {"mde": None, "note": "need at least 2 pairs"}
    diffs = [x - y for x, y in zip(a, b)]
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    sd = var ** 0.5
    if sd == 0:
        return {"mde": 0.0, "n": n, "sd_of_differences": 0.0,
                "note": "every pair differs by the same amount"}
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return {"mde": float(z * sd / (n ** 0.5)), "n": n, "sd_of_differences": float(sd),
            "alpha": alpha, "power": power,
            "note": "normal approximation to a paired t-test; the test used is Wilcoxon"}


def _rank_recovery(baseline_scores: dict, scores: dict, model_ids: list[str]) -> float | None:
    """Spearman rho between a suite's model ranking and the intact-suite ranking.

    rho = 1.0 means the suite reproduces the full benchmark's leaderboard
    exactly; lower values mean the ranking has moved.  Returns None when either
    vector is constant (every model tied) - the correlation is 0/0 there, and
    substituting 1.0 ("stable") or 0.0 ("random") would invent an observation.
    """
    a = _rank_vector(baseline_scores, model_ids)
    b = _rank_vector(scores, model_ids)
    if len(set(a)) <= 1 or len(set(b)) <= 1:
        return None
    rho = spearman_rho(a, b)["rho"]
    return None if rho != rho else float(rho)   # NaN-safe


def _pass_at_1(analysis: dict, level_key: str) -> dict | None:
    """{model: pass@1} under the baseline relation at one degradation level."""
    level = analysis.get(level_key)
    if not isinstance(level, dict):
        return None
    return level.get("pass_at_1", {}).get(BASELINE_RELATION)


def task_stratum(intact_scores: dict) -> str:
    """Classify a task by what the INTACT suite can still distinguish.

    Both RQ4 manipulations are monotone, which pins what each stratum can show
    (verified over the corpus: degradation never lowered a score in 1,476
    observations, augmentation never raised one):

    ``saturated``      every model at pass@1 = 1.0. Removing assertions cannot
                       raise a score that is already 1.0, so *degradation is
                       provably inert here* and rho against the intact ranking
                       is 1.0 by construction, not by measurement. Augmentation
                       can still lower scores, so these tasks contribute only
                       downward movement -- which is exactly how a mean recovery
                       comes out negative without the augmentation having failed
                       at anything.
    ``floor``          every model at 0.0. The mirror case: augmentation cannot
                       lower a 0.0, but degradation can raise one, so these are
                       inert for H1a while still informative for H1b. Kept
                       separate from ``saturated`` rather than lumped in as
                       "degenerate", because the two are inert for *opposite*
                       manipulations.
    ``discriminating`` everything else -- the only stratum where both arms have
                       room to move, and therefore where H1a has a valid
                       estimand.

    Computed from the intact suite at level 0.0, before any degradation or
    augmentation is applied. That makes it a pre-treatment covariate, so
    conditioning on it is stratification rather than selection on the outcome.
    It would only be circular if the stratum were derived from the same tau_b
    or rho values it is then used to filter.
    """
    values = list(intact_scores.values())
    if not values:
        return "unknown"
    if all(v == 1.0 for v in values):
        return "saturated"
    if all(v == 0.0 for v in values):
        return "floor"
    return "discriminating"


def run_analyze(cfg: Config, tasks) -> None:
    """Aggregate per-task results into a cross-task summary.

    Two questions are answered here:

    H1b (trend) is NOT computed here. Page's L is a randomized-block statistic
    whose blocks are the tasks, so it is run once over the pooled per-task
    tau_b values in scripts/analyze_results.py (analysis.statistics.pages_l_test)
    rather than per task and counted up.

    H1a (recovery) - do the MT consistency assertions restore the ranking that
                   degradation destroyed?  For each degradation level we correlate
                   the model ranking under the degraded suite, and under the
                   MT-augmented suite, against the intact-suite (0% degradation)
                   ranking, then compare the two paired lists across tasks with a
                   Wilcoxon signed-rank test.  Recovery means the augmented
                   correlations are reliably higher than the degraded ones.
    """
    out = cfg.project.output_dir / "rq4" / "summary"
    out.mkdir(parents=True, exist_ok=True)

    model_ids = cfg.model_ids()
    all_augment: list[dict] = []
    n_tasks_seen = 0
    # level -> {"degraded": [...], "augmented": [...], "tasks": [...]}
    recovery: dict[str, dict[str, list]] = {}
    n_uncalibrated = 0
    strata: Counter = Counter()

    for task in tasks:
        label = task_label(task)

        degrade_out = task_dir(cfg, "rq4", label, phase="degrade")
        aug_out = task_dir(cfg, "rq4", label, phase="augment")
        d = a = None
        try:
            d = read_json(degrade_out, "degradation_analysis.json")
            n_tasks_seen += 1
        except FileNotFoundError:
            pass
        try:
            a = read_json(aug_out, "augment_analysis.json")
            all_augment.append({
                "task_id": task.task_id,
                "has_consistency_assertions": a.get("has_consistency_assertions"),
                "n_consistency_assertions": a.get("n_consistency_assertions"),
                "divergence_rate": a.get("divergence_rate"),
                "threshold_calibrated": a.get("threshold_calibrated"),
            })
            if a.get("threshold_calibrated") is False:
                n_uncalibrated += 1
        except FileNotFoundError:
            pass

        if d is None or a is None:
            continue
        baseline = _pass_at_1(d, BASELINE_LEVEL)
        if baseline is None:
            continue
        stratum = task_stratum(baseline)
        strata[stratum] += 1

        for level in cfg.rq4.degradation_levels:
            key = str(level)
            if key == BASELINE_LEVEL:
                continue                      # correlating the baseline with itself is 1.0 by construction
            deg_scores = _pass_at_1(d, key)
            aug_scores = _pass_at_1(a, key)
            if deg_scores is None or aug_scores is None:
                continue
            rho_deg = _rank_recovery(baseline, deg_scores, model_ids)
            rho_aug = _rank_recovery(baseline, aug_scores, model_ids)
            if rho_deg is None or rho_aug is None:
                continue                      # keep the pairing intact: drop both or neither
            slot = recovery.setdefault(
                key,
                {"degraded": [], "augmented": [], "tasks": [], "strata": [],
                 "tau_degraded": [], "tau_augmented": []},
            )
            slot["degraded"].append(rho_deg)
            slot["augmented"].append(rho_aug)
            slot["tasks"].append(task.task_id)
            slot["strata"].append(stratum)
            tau_d, tau_a = d[key].get("mean_tau_b"), a[key].get("mean_tau_b")
            if tau_d is not None and tau_a is not None:
                slot["tau_degraded"].append(tau_d)
                slot["tau_augmented"].append(tau_a)

    write_json(out, "augment_summary.json", all_augment)

    # --- H1a: paired augmented-vs-degraded rank recovery, one pair per task ---
    def _paired_stats(aug: list[float], deg: list[float]) -> dict:
        if not deg:
            return {"n_tasks": 0, "note": "no task in this stratum"}
        stats = {
            "n_tasks": len(deg),
            "mean_rho_degraded": sum(deg) / len(deg),
            "mean_rho_augmented": sum(aug) / len(aug),
        }
        stats["mean_recovery"] = stats["mean_rho_augmented"] - stats["mean_rho_degraded"]
        stats["wilcoxon_augmented_vs_degraded"] = wilcoxon_test(aug, deg)
        stats["minimum_detectable_effect"] = _mde(aug, deg)
        return stats

    recovery_stats: dict[str, dict] = {}
    for key, slot in sorted(recovery.items(), key=lambda kv: float(kv[0])):
        deg, aug = slot["degraded"], slot["augmented"]
        stats = _paired_stats(aug, deg)

        # Same statistic restricted to the only stratum where H1a has an
        # estimand. Saturated tasks pin rho_degraded at 1.0 by construction
        # while still admitting downward movement under augmentation, so
        # including them drives mean recovery negative whatever the
        # augmentation does. Reported alongside, never instead of, the full
        # corpus figure above.
        by_stratum: dict[str, dict] = {}
        for name in ("discriminating", "saturated", "floor"):
            idx = [i for i, s in enumerate(slot["strata"]) if s == name]
            by_stratum[name] = _paired_stats([aug[i] for i in idx], [deg[i] for i in idx])
        stats["by_stratum"] = by_stratum
        # Secondary, in the proposal's own vocabulary. With only 3 models tau_b
        # takes just four possible values, so it is coarse - see the note below.
        tau_d, tau_a = slot["tau_degraded"], slot["tau_augmented"]
        if tau_d:
            stats["mean_tau_b_degraded"] = sum(tau_d) / len(tau_d)
            stats["mean_tau_b_augmented"] = sum(tau_a) / len(tau_a)
            stats["n_tasks_tau_b_defined"] = len(tau_d)
        recovery_stats[key] = stats

    n_with_ca = sum(1 for r in all_augment if r.get("has_consistency_assertions"))

    high_level = {
        "n_tasks": n_tasks_seen,
        "n_tasks_with_consistency_assertions": n_with_ca,
        "n_tasks_uncalibrated_threshold": n_uncalibrated,
        "task_strata": dict(strata),
        "rank_recovery_by_level": recovery_stats,
        "note": (
            "rank recovery correlates each suite's model ranking against the "
            "intact-suite ranking (Spearman rho over pass@1 under the 'original' "
            "prompt). The pseudo-oracle behind the augmentation is a majority "
            "vote over paraphrase-derived solutions, so recovery is measured "
            "relative to cross-variant consensus, not to ground truth. With 3 "
            "models tau_b can only take the values {-1, -1/3, 1/3, 1}, so it is "
            "reported as a coarse secondary descriptive statistic only."
        ),
        "stratum_note": (
            "task_strata classifies each task by what the INTACT suite can still "
            "distinguish, so it is a pre-treatment covariate, not the outcome. "
            "Both manipulations are monotone: degradation never lowers a score "
            "and augmentation never raises one. A 'saturated' task (every model "
            "at pass@1 = 1.0) therefore cannot move under degradation at all -- "
            "its rho of 1.0 is arithmetic, not evidence -- while augmentation "
            "can still lower it, so saturated tasks contribute only downward "
            "movement and push mean recovery negative however well the "
            "augmentation works. 'floor' tasks are the mirror case. Read "
            "rank_recovery_by_level[level]['by_stratum']['discriminating'] as "
            "the H1a result; the pooled figure beside it is the sensitivity "
            "check, not the estimate."
        ),
    }
    write_json(out, "high_level.json", high_level)

    logger.info(
        "RQ4 analyze: %d task(s) aggregated; %d carry consistency assertions. "
        "H1b's trend test runs across tasks in scripts/analyze_results.py.",
        n_tasks_seen, n_with_ca,
    )
    for key, stats in recovery_stats.items():
        logger.info(
            "  level %s: rho degraded=%.3f -> augmented=%.3f (recovery %+.3f, "
            "p=%.4g, n=%d)",
            key, stats["mean_rho_degraded"], stats["mean_rho_augmented"],
            stats["mean_recovery"],
            stats["wilcoxon_augmented_vs_degraded"]["p_value"], stats["n_tasks"],
        )
    if n_uncalibrated:
        logger.warning(
            "%d task(s) used an UNCALIBRATED divergence threshold - calibrate "
            "rq3.divergence_threshold from the pilot before reporting these numbers.",
            n_uncalibrated,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="RQ4: MT augmentation and interaction")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--phase", choices=["degrade", "augment", "analyze"], required=True)
    add_task_selection_args(parser)
    add_force_arg(parser)
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    setup_logging("rq4", args.phase, log_dir=Path("logs"))

    tasks = load_humaneval(tasks=resolve_task_filter(args, cfg))
    logger.info("RQ4 phase=%s, %d task(s)%s", args.phase, len(tasks), " (forced)" if args.force else "")

    if args.phase == "degrade":
        for task in tasks:
            run_degrade_one(task, cfg, force=args.force)
    elif args.phase == "augment":
        for task in tasks:
            run_augment_one(task, cfg, force=args.force)
    else:
        run_analyze(cfg, tasks)

    logger.info("RQ4 phase=%s complete.", args.phase)


if __name__ == "__main__":
    main()
