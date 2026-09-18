"""Statistical tests used across RQs.

All functions accept plain lists/arrays and return a dict with the
statistic value, p-value, and effect size where applicable.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import wilcoxon, mannwhitneyu, norm


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


def pages_l_test(blocks: list[list[float]], descending: bool = True) -> dict:
    """Page's L trend test for an ordered alternative (RQ4 H1b).

    ``blocks`` is one list per block (here: per task), each holding the k
    measurements in treatment order (here: tau_b at each degradation level,
    ordered 0%, 20%, 50%, 80%). Blocks of differing length, or containing a
    None, are dropped — Page's L needs a complete ranking within each block.

    ``descending=True`` tests the H1b alternative "values decrease as the
    ordered condition increases" by reversing the treatment weighting.

    Page's L is a *rank* statistic: values are ranked 1..k **within each
    block**, and L = sum_j(j * R_j) over the rank sums R_j. The normal
    approximation below is only valid because n is the number of tasks
    (~164), not 1 — with a single block there are just k! = 24 possible
    arrangements and no meaningful asymptotics.
    """
    clean = [b for b in blocks
             if len(b) == len(blocks[0]) and all(v is not None for v in b)] if blocks else []
    n, k = len(clean), len(clean[0]) if clean else 0
    if n == 0 or k < 3:
        return {"L": None, "n_blocks": n, "k_levels": k,
                "note": "Page's L needs >=3 ordered levels and >=1 complete block"}

    from scipy.stats import rankdata

    rank_sums = np.zeros(k)
    for block in clean:
        values = [-v for v in block] if descending else list(block)
        rank_sums += rankdata(values, method="average")

    weights = np.arange(1, k + 1)
    L = float(np.sum(weights * rank_sums))

    mean_L = n * k * (k + 1) ** 2 / 4.0
    var_L = n * (k ** 3 - k) ** 2 / (144.0 * (k - 1))
    z = (L - mean_L) / np.sqrt(var_L) if var_L > 0 else 0.0
    p = float(norm.sf(z))                      # one-tailed: L large => trend present

    return {
        "L": round(L, 4),
        "z": round(float(z), 4),
        "p_value": round(p, 6),
        "n_blocks": n,
        "k_levels": k,
        "trend_present": bool(p < 0.05),
        "direction": "decreasing" if descending else "increasing",
    }


def spearman_rho(a: list[float], b: list[float]) -> dict:
    """Spearman rank correlation."""
    from scipy.stats import spearmanr
    result = spearmanr(a, b)
    return {
        "rho": float(result.statistic),
        "p_value": float(result.pvalue),
    }


def roc_auc(scores: list[float], labels: list[int]) -> dict:
    """Rank-based ROC-AUC for a continuous score against binary labels (RQ3).

    ``labels`` is 1 for the positive class.  Implemented as the Mann-Whitney U
    identity (AUC = P(score_positive > score_negative), ties counted as 0.5)
    rather than pulling in scikit-learn for a five-line computation.

    Returns {"auc", "n_positive", "n_negative"}.  AUC is None when either class
    is empty — with only one class present the statistic is undefined, and
    reporting 0.5 there would fabricate a "chance-level" result.
    """
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have the same length")
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return {"auc": None, "n_positive": len(pos), "n_negative": len(neg),
                "note": "AUC undefined: only one class present"}

    wins = sum(
        (1.0 if p > n else (0.5 if p == n else 0.0))
        for p in pos for n in neg
    )
    return {
        "auc": wins / (len(pos) * len(neg)),
        "n_positive": len(pos),
        "n_negative": len(neg),
    }


def youden_threshold(scores: list[float], labels: list[int]) -> dict:
    """Pick the score cut-off maximising Youden's J = sensitivity + specificity - 1.

    Used to calibrate rq3.divergence_threshold from the Tier-1 pilot.  The
    positive class is label==1 and the rule is ``score >= threshold``.
    Candidate cut-offs are the observed scores themselves.
    """
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have the same length")
    n_pos = sum(1 for y in labels if y)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return {"threshold": None, "youden_j": None,
                "note": "undefined: only one class present"}

    best = {"threshold": None, "youden_j": -1.0, "sensitivity": None, "specificity": None}
    for cut in sorted(set(scores)):
        tp = sum(1 for s, y in zip(scores, labels) if y and s >= cut)
        fp = sum(1 for s, y in zip(scores, labels) if not y and s >= cut)
        sens = tp / n_pos
        spec = 1 - fp / n_neg
        j = sens + spec - 1
        if j > best["youden_j"]:
            best = {"threshold": float(cut), "youden_j": float(j),
                    "sensitivity": float(sens), "specificity": float(spec)}
    return best


def mannwhitney_test(a: list[float], b: list[float]) -> dict:
    """Mann-Whitney U for two *independent* groups, with Cliff's delta.

    Used where the two samples are different sets of tasks (e.g. weak-oracle vs
    strong-oracle tasks in the cross-RQ join).  The paired wilcoxon_test above
    would be wrong there: it assumes each value in `a` is matched to the value
    at the same position in `b`, which unrelated task groups are not.
    """
    if not a or not b:
        return {"statistic": None, "p_value": None, "cliffs_delta": None,
                "note": "one group is empty"}
    stat, p = mannwhitneyu(a, b, alternative="two-sided")
    return {"statistic": float(stat), "p_value": float(p),
            "cliffs_delta": cliffs_delta(a, b), "n_a": len(a), "n_b": len(b)}
