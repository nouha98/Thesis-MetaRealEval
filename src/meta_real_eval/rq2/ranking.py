"""Compute Kendall tau_b ranking stability across prompt variants.

For each (task, model) pair we have one Pass@1 score per relation.
We compare the model ranking induced by each variant against the 'original'
variant using Kendall's tau_b, then bootstrap 95% confidence intervals.

Output format (per task)
------------------------
{
  "model_id": {
    "tau_b_per_variant": {"persona": 0.3, "formal": -0.1, ...},
    "mean_tau_b": 0.05,
    "ci_lower": -0.2,
    "ci_upper": 0.4
  },
  ...
}
"""

from __future__ import annotations

import logging
import random
from typing import Optional

import numpy as np
from scipy.stats import kendalltau

from ..core.checkpoint import is_done, mark_done, task_dir, write_json, read_json
from ..core.config import Config
from ..core.data_loader import HumanEvalTask, task_label

logger = logging.getLogger(__name__)


def _model_pass_at1(pass_rates: dict, relation: str) -> dict[str, float]:
    """Return {model_id: pass@1} for a given relation."""
    return {
        model_id: rates["pass@1"]
        for model_id, rates in pass_rates.get(relation, {}).items()
    }


def _rank_vector(scores: dict[str, float], model_ids: list[str]) -> list[float]:
    """Convert {model_id: score} to a list of scores in fixed model order."""
    return [scores.get(mid, 0.0) for mid in model_ids]


def _tau_b(vec_a: list[float], vec_b: list[float]) -> float:
    if len(set(vec_a)) <= 1 and len(set(vec_b)) <= 1:
        return 1.0  # both constant → trivially concordant
    result = kendalltau(vec_a, vec_b)
    return float(result.statistic) if not np.isnan(result.statistic) else 0.0


def _bootstrap_ci(
    values: list[float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap 95% CI over a list of tau_b values."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    boots = [
        np.mean(rng.choices(values, k=len(values)))
        for _ in range(n_boot)
    ]
    boots.sort()
    lo = boots[int(alpha / 2 * n_boot)]
    hi = boots[int((1 - alpha / 2) * n_boot)]
    return float(lo), float(hi)


def compute_ranking_stability(task: HumanEvalTask, cfg: Config) -> None:
    """Read pass_rates.json and write rankings.json for one task."""
    label = task_label(task)
    out = task_dir(cfg, "rq2", label, phase="evaluate")

    rankings_file = out / "rankings.json"
    if rankings_file.exists():
        logger.info("SKIP rankings %s (already done)", label)
        return

    try:
        pass_rates: dict = read_json(out, "pass_rates.json")
    except FileNotFoundError:
        logger.error("pass_rates.json missing for %s", label)
        return

    model_ids = cfg.model_ids()
    relations = cfg.rq2.relations
    baseline_relation = "original"

    baseline_scores = _model_pass_at1(pass_rates, baseline_relation)
    baseline_vec = _rank_vector(baseline_scores, model_ids)

    rankings: dict[str, dict] = {}
    for model_id in model_ids:
        variant_taus: dict[str, float] = {}
        for relation in relations:
            if relation == baseline_relation:
                continue
            variant_scores = _model_pass_at1(pass_rates, relation)
            variant_vec = _rank_vector(variant_scores, model_ids)
            variant_taus[relation] = _tau_b(baseline_vec, variant_vec)

        tau_values = list(variant_taus.values())
        mean_tau = float(np.mean(tau_values)) if tau_values else float("nan")
        ci_lo, ci_hi = _bootstrap_ci(tau_values, seed=cfg.project.seed)

        rankings[model_id] = {
            "tau_b_per_variant": variant_taus,
            "mean_tau_b": mean_tau,
            "ci_lower": ci_lo,
            "ci_upper": ci_hi,
        }
        logger.debug("  %s / %s mean_tau_b=%.3f", label, model_id, mean_tau)

    write_json(out, "rankings.json", rankings)
    logger.info("Rankings computed for %s", label)
