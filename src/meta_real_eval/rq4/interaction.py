"""RQ4 interaction analysis: does prompt sensitivity compound with oracle weakness?

For each task, we re-run the RQ2 tau_b analysis at each degradation level
and regress tau_b against degradation percentage.  Page's L trend test checks
whether tau_b decreases monotonically as degradation increases.

H1b: Ranking instability (tau_b) increases monotonically with degradation degree.
"""

from __future__ import annotations

import logging
from itertools import combinations

import numpy as np
from scipy.stats import kendalltau

from ..core.config import Config
from ..core.data_loader import HumanEvalTask, task_label
from ..rq2.evaluator import _run_completion, pass_at_k
from ..rq2.ranking import _rank_vector, _model_pass_at1, _tau_b

logger = logging.getLogger(__name__)


def compute_tau_at_degradation_level(
    task: HumanEvalTask,
    completions_data: dict,
    degraded_test: str,
    cfg: Config,
) -> dict[str, float]:
    """Compute mean tau_b across variants for one degradation level.

    Returns {model_id: mean_tau_b} using degraded_test instead of task.test.
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed

    model_ids = cfg.model_ids()
    relations = cfg.rq2.relations

    # Compute pass@1 for each (relation, model) using the degraded test
    pass_at1: dict[str, dict[str, float]] = {}
    for relation, model_completions in completions_data.items():
        pass_at1[relation] = {}
        for model_id, completions in model_completions.items():
            correct = 0
            n = len(completions)
            for comp in completions:
                try:
                    if _run_completion(comp, task.prompt, degraded_test,
                                       task.entry_point, cfg.execution.timeout_s):
                        correct += 1
                except Exception:
                    pass
            pass_at1[relation][model_id] = pass_at_k(n, correct, 1)

    # Compute tau_b per model relative to 'original' variant
    baseline_vec = _rank_vector(
        {mid: pass_at1.get("original", {}).get(mid, 0.0) for mid in model_ids},
        model_ids,
    )
    model_taus: dict[str, float] = {}
    for model_id in model_ids:
        variant_taus = []
        for relation in relations:
            if relation == "original":
                continue
            variant_vec = _rank_vector(
                {mid: pass_at1.get(relation, {}).get(mid, 0.0) for mid in model_ids},
                model_ids,
            )
            variant_taus.append(_tau_b(baseline_vec, variant_vec))
        model_taus[model_id] = float(np.mean(variant_taus)) if variant_taus else float("nan")

    return model_taus


def pages_l_trend_test(tau_by_level: dict[float, float]) -> dict:
    """Page's L statistic for monotonic trend in tau_b across ordered degradation levels.

    tau_by_level: {degradation_fraction: mean_tau_b}

    Returns {L, p_value_approx, monotonic}.
    Under H1b we expect tau_b to *decrease* (or instability to increase) as
    degradation increases.
    """
    levels = sorted(tau_by_level.keys())
    values = [tau_by_level[l] for l in levels]
    k = len(levels)
    if k < 3:
        return {"L": None, "note": "Need at least 3 levels for Page's L"}

    # Page's L = sum(rank_i * col_sum_i) for a one-group version
    # Here we use a simplified formulation: L = sum(i * v_i) for expected ascending trend
    # We test for descending tau_b (ascending instability) so we use -values
    L = sum((i + 1) * v for i, v in enumerate([-v for v in values]))
    # Normal approximation (for small k, this is very rough)
    n = 1  # single "block"
    mean_L = n * k * (k + 1) ** 2 / 4
    var_L = n * k ** 2 * (k ** 2 - 1) * (k + 2) / 144
    z = (L - mean_L) / (var_L ** 0.5) if var_L > 0 else 0.0

    from scipy.stats import norm
    p = float(norm.sf(z))  # one-tailed

    return {
        "L": round(L, 4),
        "z": round(z, 4),
        "p_value_approx": round(p, 4),
        "monotonic_decrease_in_tau": p < 0.05,
        "levels": levels,
        "tau_values": values,
    }
