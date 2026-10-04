"""τ_div calibration with a structurally enforced calibration/held-out split.

The leak this exists to prevent: picking a threshold BECAUSE it separates a
set of points, then reporting how well it separates that same set of points.
Tier 1's own calibration (``scripts/analyze_results.py::_split_half_validation``)
already warns about this in its docstring, but only as a comment -- the
threshold it actually writes to config is fit on the FULL sample, and the
held-out check is a secondary diagnostic reported alongside an optimistic
full-sample number, not a gate on what gets called the headline result.

For Tier 2 the discipline is structural, not a comment:

    calibration data  ->  youden_threshold  ->  FROZEN value
                                                     |
    held-out data     ----------------------------->+--> the one number
                                                          reported as the
                                                          headline AUC

:func:`calibrate_and_freeze` takes the two sets as separate arguments --
there is no "one pool, split inside" code path for a caller to accidentally
bypass -- and raises :class:`CalibrationLeakError` if their task ids are
shown to overlap. The threshold it returns is fit ONLY from the calibration
arguments; the ``headline`` block it returns is computed ONLY from the
held-out arguments, using that already-fixed threshold, never refitting.

This module has no cluster/real-data dependency: it operates on whatever
(score, label, task_id) triples a caller assembles from stored RQ2/RQ3
output. The actual Tier 2 calibration VALUE needs that data at a real scale
(M1/M3), which does not exist yet; what exists here is the mechanism, and it
is exercised in tests with synthetic data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .statistics import roc_auc, youden_threshold


class CalibrationLeakError(ValueError):
    """Raised when calibration and held-out task sets are shown to overlap.

    Never silenced or downgraded to a warning: a caller that hits this has a
    bug in how it built the split, and the one thing this module exists to
    guarantee is that such a bug cannot quietly produce an optimistic
    headline number instead.
    """


@dataclass(frozen=True)
class CalibrationResult:
    threshold: Optional[float]
    frozen: bool
    n_calibration: int
    n_holdout: int
    # Diagnostic only -- the threshold was chosen to maximise this on this
    # same data, so it is optimistic by construction. Never the number to
    # report as "how well τ_div separates correct from incorrect".
    calibration_fit: dict
    # The number to report: sensitivity/specificity/Youden's J/ROC-AUC of the
    # FROZEN threshold against data it never influenced.
    headline: dict
    calibration_task_ids: Optional[frozenset] = field(default=None)
    holdout_task_ids: Optional[frozenset] = field(default=None)


def calibrate_and_freeze(
    calibration_scores: list[float],
    calibration_labels: list[int],
    holdout_scores: list[float],
    holdout_labels: list[int],
    *,
    calibration_task_ids: Optional[list[str]] = None,
    holdout_task_ids: Optional[list[str]] = None,
) -> CalibrationResult:
    """Fit τ_div on the calibration set only; freeze it; score the held-out
    set with that frozen value.

    ``*_task_ids``, when both given, are checked for overlap and
    :class:`CalibrationLeakError` is raised if any task appears in both --
    this is the one enforcement point that cannot be skipped by a caller in
    a hurry. Omit them only when the caller has already verified disjointness
    some other way (e.g. a corpus too large to pass whole task-id lists
    around); prefer passing them.
    """
    if calibration_task_ids is not None and holdout_task_ids is not None:
        overlap = sorted(set(calibration_task_ids) & set(holdout_task_ids))
        if overlap:
            raise CalibrationLeakError(
                f"{len(overlap)} task(s) appear in BOTH the calibration and held-out "
                f"sets: {overlap[:5]}{', ...' if len(overlap) > 5 else ''}. The split "
                "must be disjoint before this function is ever called -- fix it upstream."
            )

    fit = youden_threshold(calibration_scores, calibration_labels)
    threshold = fit.get("threshold")
    calibration_fit = {
        "youden_j": fit.get("youden_j"),
        "sensitivity": fit.get("sensitivity"),
        "specificity": fit.get("specificity"),
        "note": fit.get("note") or (
            "In-sample: this threshold was chosen BECAUSE it maximises Youden's J "
            "on this exact data. Never quote this J as the method's accuracy -- "
            "report `headline` instead."
        ),
    }

    if threshold is None:
        return CalibrationResult(
            threshold=None, frozen=False,
            n_calibration=len(calibration_scores), n_holdout=len(holdout_scores),
            calibration_fit=calibration_fit,
            headline={"available": False, "note": "calibration half degenerate; no threshold to freeze"},
            calibration_task_ids=frozenset(calibration_task_ids) if calibration_task_ids is not None else None,
            holdout_task_ids=frozenset(holdout_task_ids) if holdout_task_ids is not None else None,
        )

    n_pos = sum(1 for y in holdout_labels if y)
    n_neg = len(holdout_labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        headline = {"available": False,
                    "note": "held-out set contains only one class; cannot report a headline"}
    else:
        tp = sum(1 for s, y in zip(holdout_scores, holdout_labels) if y and s >= threshold)
        fp = sum(1 for s, y in zip(holdout_scores, holdout_labels) if not y and s >= threshold)
        sensitivity = tp / n_pos
        specificity = 1 - fp / n_neg
        headline = {
            "available": True,
            "sensitivity": sensitivity,
            "specificity": specificity,
            "youden_j": sensitivity + specificity - 1,
            "roc_auc": roc_auc(holdout_scores, holdout_labels).get("auc"),
            "n_positive": n_pos,
            "n_negative": n_neg,
        }

    return CalibrationResult(
        threshold=threshold, frozen=True,
        n_calibration=len(calibration_scores), n_holdout=len(holdout_scores),
        calibration_fit=calibration_fit, headline=headline,
        calibration_task_ids=frozenset(calibration_task_ids) if calibration_task_ids is not None else None,
        holdout_task_ids=frozenset(holdout_task_ids) if holdout_task_ids is not None else None,
    )


def stratified_calibration_split(
    task_ids: list[str],
    strata: list[str],
    seed: int,
    calibration_fraction: float = 0.5,
) -> tuple[list[str], list[str]]:
    """A seeded calibration/held-out split, proportional within each stratum
    (e.g. csn / post-cutoff) rather than one global shuffle that could by bad
    luck concentrate a whole stratum on one side of the split.

    Deterministic in ``seed`` and in each stratum's own sorted task-id order,
    so the split is reproducible without needing to be stored verbatim --
    though the calibration record (see the Tier 2 calibration script) stores
    the resulting id lists anyway, so a later audit never has to re-derive it.
    """
    if len(task_ids) != len(strata):
        raise ValueError("task_ids and strata must have the same length")
    by_stratum: dict[str, list[str]] = {}
    for tid, s in zip(task_ids, strata):
        by_stratum.setdefault(s, []).append(tid)

    calibration: list[str] = []
    holdout: list[str] = []
    for s in sorted(by_stratum):
        ids = sorted(by_stratum[s])
        random.Random(f"{seed}:{s}").shuffle(ids)
        cut = round(len(ids) * calibration_fraction)
        calibration += ids[:cut]
        holdout += ids[cut:]
    return calibration, holdout


def calibration_record(result: CalibrationResult, **provenance) -> dict:
    """A JSON-serialisable audit record: what was frozen, from what, scored
    against what. ``provenance`` is merged in verbatim (corpus sha256, the
    config path written to, a timestamp, the seed) -- this function does not
    prescribe its shape, it just guarantees the result's own fields are never
    silently dropped.
    """
    return {
        "threshold": result.threshold,
        "frozen": result.frozen,
        "n_calibration": result.n_calibration,
        "n_holdout": result.n_holdout,
        "calibration_fit": result.calibration_fit,
        "headline": result.headline,
        "calibration_task_ids": sorted(result.calibration_task_ids) if result.calibration_task_ids else None,
        "holdout_task_ids": sorted(result.holdout_task_ids) if result.holdout_task_ids else None,
        **provenance,
    }
