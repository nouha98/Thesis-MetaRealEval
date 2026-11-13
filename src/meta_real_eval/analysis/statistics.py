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

    Returns (lower, upper) at the (alpha/2, 1-alpha/2) percentiles; (None, None)
    for an empty input (which used to raise inside numpy).
    """
    rng = np.random.default_rng(seed)
    arr = np.array(values, dtype=float)
    if arr.size == 0:
        return None, None
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


def cochran_q(table: list[list[int]]) -> dict:
    """Cochran's Q for k related binary outcomes (RQ4 ranking collapse).

    ``table`` has one row per block (task) and one 0/1 per condition (level).
    Q is undefined (None) when every row is constant -- no block varies -- and
    when the table is empty (which used to raise IndexError).
    """
    from scipy.stats import chi2

    if not table:
        return {"q": None, "p_value": None, "n_blocks": 0, "k": 0}
    k = len(table[0])
    col = [sum(r[j] for r in table) for j in range(k)]
    row_sums = [sum(r) for r in table]
    total = sum(row_sums)
    denom = k * total - sum(x * x for x in row_sums)
    if not denom:
        return {"q": None, "p_value": None, "n_blocks": len(table), "k": k}
    q = (k - 1) * (k * sum(c * c for c in col) - total * total) / denom
    return {"q": float(q), "p_value": float(chi2.sf(q, k - 1)), "n_blocks": len(table), "k": k}


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


# ---------------------------------------------------------------------------
# Helpers for the thesis extensions (plan rev. 8). New functions only: the
# historical analyses above keep their exact behaviour. Every helper returns
# None (never 0, 0.5 or NaN) when its quantity is undefined.
# ---------------------------------------------------------------------------

def safe_ratio(num: float, den: float):
    """num / den, or None when the denominator is zero."""
    return None if not den else num / den


def wilson_ci(k: int, n: int, alpha: float = 0.05) -> dict:
    """Wilson score interval for a binomial proportion k / n (None when n == 0)."""
    if n <= 0:
        return {"p": None, "lo": None, "hi": None, "k": k, "n": n}
    z = float(norm.ppf(1 - alpha / 2))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"p": p, "lo": float(max(0.0, centre - half)), "hi": float(min(1.0, centre + half)), "k": k, "n": n}


def mcnemar_exact(b: int, c: int) -> dict:
    """Exact (binomial) McNemar test on the discordant counts of a paired binary outcome:
    ``b`` = only the first condition succeeded, ``c`` = only the second. Undefined with no
    discordant pair."""
    from scipy.stats import binomtest
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "p_value": None, "note": "no discordant pairs"}
    return {"b": b, "c": c, "p_value": float(binomtest(b, n, 0.5).pvalue)}


def sign_test(diffs: list[float]) -> dict:
    """Exact two-sided sign test on paired differences (zeros dropped)."""
    pos = sum(1 for d in diffs if d > 0)
    neg = sum(1 for d in diffs if d < 0)
    res = mcnemar_exact(pos, neg)
    return {"n_positive": pos, "n_negative": neg, "n_zero": len(diffs) - pos - neg, "p_value": res["p_value"]}


def chi2_2x2_defined(table: list[list[int]]) -> dict:
    """Chi-square test of a 2x2 table, explicitly undefined when a row or column total is zero
    (e.g. ``[[4, 0], [2, 0]]``) instead of raising or returning NaN."""
    from scipy.stats import chi2_contingency
    arr = np.asarray(table, dtype=float)
    if arr.shape != (2, 2):
        raise ValueError("expected a 2x2 table")
    if (arr.sum(0) == 0).any() or (arr.sum(1) == 0).any():
        return {"chi2": None, "p_value": None, "note": "undefined: a row or column total is zero"}
    chi2, p, _, _ = chi2_contingency(arr)
    return {"chi2": float(chi2), "p_value": float(p)}


def spearman_rho_defined(a: list[float], b: list[float]) -> dict:
    """Spearman's rho, None when either input is constant or fewer than 3 pairs exist
    (``spearman_rho`` returns NaN there and is kept as is for the historical analyses)."""
    if len(a) != len(b):
        raise ValueError("a and b must have the same length")
    if len(a) < 3 or len(set(a)) < 2 or len(set(b)) < 2:
        return {"rho": None, "p_value": None, "n": len(a), "note": "undefined: constant input or n < 3"}
    return {**spearman_rho(a, b), "n": len(a)}


def paired_cluster_bootstrap(values_by_cluster: dict, n_boot: int = 2000, alpha: float = 0.05,
                             seed: int = 42) -> dict:
    """Bootstrap CI for the mean of paired differences that are grouped in clusters (e.g. several
    models or runs per task): clusters are resampled with replacement, and the statistic is the
    mean over every value in the resampled clusters. None when there is no value."""
    clusters = [np.asarray(v, dtype=float) for v in values_by_cluster.values() if len(v)]
    n_values = int(sum(len(c) for c in clusters))
    if not clusters:
        return {"mean": None, "lo": None, "hi": None, "n_clusters": 0, "n_values": 0}
    sums = np.array([c.sum() for c in clusters])
    sizes = np.array([len(c) for c in clusters], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(clusters), size=(n_boot, len(clusters)))
    boots = sums[idx].sum(1) / sizes[idx].sum(1)
    return {"mean": float(sums.sum() / sizes.sum()),
            "lo": float(np.percentile(boots, 100 * alpha / 2)),
            "hi": float(np.percentile(boots, 100 * (1 - alpha / 2))),
            "n_clusters": len(clusters), "n_values": n_values}


def holm(pvalues: dict, alpha: float = 0.05) -> dict:
    """Holm-Bonferroni over a named family. Undefined p-values (None) stay undefined and are
    not counted in the family size."""
    defined = sorted(((p, name) for name, p in pvalues.items() if p is not None))
    m = len(defined)
    out = {name: {"p_value": None, "p_adjusted": None, "reject": None} for name, p in pvalues.items() if p is None}
    running, still_rejecting = 0.0, True
    for i, (p, name) in enumerate(defined):
        adj = min(1.0, max(running, (m - i) * p))
        running = adj
        still_rejecting = still_rejecting and adj <= alpha
        out[name] = {"p_value": p, "p_adjusted": adj, "reject": still_rejecting}
    return out
