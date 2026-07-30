"""Statistical tests used across RQs.

All functions accept plain lists/arrays and return a dict with the
statistic value, p-value, and effect size where applicable.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import wilcoxon, kendalltau


def wilcoxon_test(a: list[float], b: list[float]) -> dict:
    """Paired Wilcoxon signed-rank test (RQ1a/b, RQ4 rank recovery).

    Requires equal-length paired lists.  Returns statistic, p_value,
    and Cliff's delta as effect size.
    """
    if len(a) != len(b):
        raise ValueError("Paired lists must have the same length")
    if all(x == y for x, y in zip(a, b)):
        return {"statistic": 0.0, "p_value": 1.0, "cliffs_delta": 0.0, "note": "all differences zero"}

    stat, p = wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
    delta = cliffs_delta(a, b)
    return {"statistic": float(stat), "p_value": float(p), "cliffs_delta": delta}


def cliffs_delta(a: list[float], b: list[float]) -> float:
    """Cliff's delta effect size: probability that a value in A > B minus the reverse."""
    n_a, n_b = len(a), len(b)
    if n_a == 0 or n_b == 0:
        return float("nan")
    dominance = sum(
        (1 if x > y else (-1 if x < y else 0))
        for x in a
        for y in b
    )
    return dominance / (n_a * n_b)


def bootstrap_ci(
    values: list[float],
    statistic_fn=np.mean,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval.

    Returns (lower, upper) at the (alpha/2, 1-alpha/2) percentiles.
    """
    rng = np.random.default_rng(seed)
    arr = np.array(values, dtype=float)
    boots = [statistic_fn(rng.choice(arr, size=len(arr), replace=True)) for _ in range(n_boot)]
    boots_sorted = sorted(boots)
    lo = boots_sorted[int(alpha / 2 * n_boot)]
    hi = boots_sorted[int((1 - alpha / 2) * n_boot)]
    return float(lo), float(hi)


def kendall_tau_b(a: list[float], b: list[float]) -> dict:
    """Kendall tau_b between two rank vectors."""
    result = kendalltau(a, b)
    return {
        "tau_b": float(result.statistic),
        "p_value": float(result.pvalue),
    }


def spearman_rho(a: list[float], b: list[float]) -> dict:
    """Spearman rank correlation."""
    from scipy.stats import spearmanr
    result = spearmanr(a, b)
    return {
        "rho": float(result.statistic),
        "p_value": float(result.pvalue),
    }
