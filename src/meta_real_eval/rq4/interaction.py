"""RQ4 interaction analysis: does prompt sensitivity compound with oracle weakness?

For each task, we re-run the RQ2 tau_b analysis at each degradation level
and regress tau_b against degradation percentage.  Page's L trend test checks
whether tau_b decreases monotonically as degradation increases.

H1b: Ranking instability (tau_b) increases monotonically with degradation degree.
"""

from __future__ import annotations

import logging

import numpy as np

from ..core.config import Config
from ..core.data_loader import HumanEvalTask
from ..rq2.evaluator import _run_completion, pass_at_k
from ..rq2.ranking import _rank_vector, _tau_b, collapse_tau_by_arm

logger = logging.getLogger(__name__)


def compute_tau_at_degradation_level(
    task: HumanEvalTask,
    completions_data: dict,
    degraded_test: str,
    cfg: Config,
) -> dict:
    """Re-run RQ2's ranking-stability protocol using a degraded test suite.

    Returns the (task, relation)-level summary that rq2.ranking produces, so
    every degradation level is directly comparable to the intact baseline:

        {"mean_tau_b": float | None, "tau_b_per_relation": {...},
         "degenerate_relations": [...], "pass_at_1": {relation: {model: float}}}

    tau_b describes the ordering of the whole model set, so there is one value
    per relation — not one per model (see rq2/ranking.py).

    ``pass_at_1`` is returned as well because two downstream analyses need the
    raw scores, not just their rank correlation: RQ4's rank-recovery statistic
    (H1a) compares each suite's model ranking against the intact-suite ranking,
    and the augment-vs-degrade verification check needs to see that the two
    suites actually score candidates differently.
    """
    model_ids = cfg.model_ids()
    relations = [r for r in cfg.rq2.relations if r != "original"]

    # pass@1 for each (relation, model) under the degraded test. A cell with no
    # completions is left out entirely rather than scored 0.0 — see
    # rq2/ranking.py::_model_pass_at1 for why an empty sample is not a zero.
    pass_at1: dict[str, dict[str, float]] = {}
    for relation, model_completions in completions_data.items():
        pass_at1[relation] = {}
        for model_id, completions in model_completions.items():
            n = len(completions)
            if n == 0:
                continue
            correct = 0
            for comp in completions:
                try:
                    if _run_completion(comp, task.prompt, degraded_test,
                                       task.entry_point, cfg.execution.timeout_s):
                        correct += 1
                except Exception:
                    pass
            pass_at1[relation][model_id] = pass_at_k(n, correct, 1)

    def _complete(relation: str) -> bool:
        scores = pass_at1.get(relation, {})
        return all(mid in scores for mid in model_ids)

    baseline_ok = _complete("original")
    baseline_vec = _rank_vector(pass_at1.get("original", {}), model_ids)
    tau_per_relation: dict[str, float | None] = {}
    for relation in relations:
        if not baseline_ok or not _complete(relation):
            tau_per_relation[relation] = None
            continue
        variant_vec = _rank_vector(pass_at1.get(relation, {}), model_ids)
        tau_per_relation[relation] = _tau_b(baseline_vec, variant_vec)

    defined = [t for t in tau_per_relation.values() if t is not None]
    by_arm = collapse_tau_by_arm(tau_per_relation)
    return {
        # Same definition as rq2/ranking.py: the primary arm, collapsed
        # variant -> family -> arm. Page's L compares this value across
        # degradation levels, so it has to mean the same thing at every level.
        "mean_tau_b": by_arm["primary"],
        "tau_b_by_arm": by_arm,
        "mean_tau_b_all_relations": float(np.mean(defined)) if defined else None,
        "tau_b_per_relation": tau_per_relation,
        "degenerate_relations": [r for r, t in tau_per_relation.items() if t is None],
        "pass_at_1": pass_at1,
    }


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
