"""calibrate_and_freeze's one job: never let the headline number be
influenced by the data the threshold was chosen from. Every test here is
built to demonstrate that property, not just exercise the happy path --
most of them construct synthetic scores specifically designed so that
calibration-on-itself and calibration-on-holdout give VISIBLY different
answers, so a regression that silently merges the two pools would fail
these deterministically, not by chance.
"""

from __future__ import annotations

import pytest

from meta_real_eval.analysis.calibration import (
    CalibrationLeakError,
    calibrate_and_freeze,
    calibration_record,
    stratified_calibration_split,
)
from meta_real_eval.analysis.statistics import roc_auc


def _separable(n=20, seed=0):
    """Scores where >=0.5 is a clean separator: positives high, negatives low."""
    import random
    rng = random.Random(seed)
    scores, labels = [], []
    for i in range(n):
        if i % 2 == 0:
            scores.append(0.6 + rng.uniform(0, 0.3)); labels.append(1)
        else:
            scores.append(0.1 + rng.uniform(0, 0.3)); labels.append(0)
    return scores, labels


def test_threshold_is_frozen_from_calibration_only():
    """Changing the HELD-OUT data must not change the frozen threshold at all."""
    cal_scores, cal_labels = _separable(seed=1)
    hold_a_scores, hold_a_labels = _separable(seed=2)
    hold_b_scores, hold_b_labels = _separable(seed=3)  # a different holdout sample

    r_a = calibrate_and_freeze(cal_scores, cal_labels, hold_a_scores, hold_a_labels)
    r_b = calibrate_and_freeze(cal_scores, cal_labels, hold_b_scores, hold_b_labels)

    assert r_a.threshold == r_b.threshold, "the threshold must depend only on calibration data"


def test_headline_is_a_pure_function_of_threshold_and_holdout():
    """Two calibration sets that happen to freeze the exact same threshold
    value (verified, not assumed -- youden_threshold's candidates are the
    observed scores themselves, so this has to be checked rather than
    guessed from "similar-looking" calibration data) must produce identical
    headlines on the same holdout: nothing about the calibration set besides
    the frozen number may leak through."""
    cal_1, lab_1 = [0.0, 0.3, 0.7, 1.0], [0, 0, 1, 1]
    cal_2, lab_2 = [0.0, 0.69, 0.7, 1.0], [0, 0, 1, 1]
    hold, hold_lab = _separable(seed=9)

    r1 = calibrate_and_freeze(cal_1, lab_1, hold, hold_lab)
    r2 = calibrate_and_freeze(cal_2, lab_2, hold, hold_lab)

    assert r1.threshold == r2.threshold == 0.7  # the actual shared cut-off, confirmed
    assert r1.headline == r2.headline


def test_evaluating_on_calibration_data_itself_is_optimistic_vs_holdout():
    """The core leak this module exists to prevent, demonstrated directly:
    scoring the threshold against the SAME data it was fit on (what a naive
    "split inside one function" implementation might accidentally do) gives a
    STRICTLY BETTER (or equal) Youden's J than scoring it against genuinely
    held-out data -- because the cut-off was chosen to maximise exactly that
    statistic on the calibration points.
    """
    cal_scores, cal_labels = _separable(seed=1)
    hold_scores, hold_labels = _separable(seed=42)

    honest = calibrate_and_freeze(cal_scores, cal_labels, hold_scores, hold_labels)
    # What a leaky implementation would report if it evaluated on its own
    # calibration data instead of genuine holdout:
    leaky = calibrate_and_freeze(cal_scores, cal_labels, cal_scores, cal_labels)

    assert leaky.threshold == honest.threshold  # same fit either way
    assert leaky.headline["youden_j"] >= honest.headline["youden_j"] - 1e-9
    assert leaky.headline["youden_j"] == pytest.approx(leaky.calibration_fit["youden_j"])


def test_overlapping_task_ids_raise_leak_error():
    scores, labels = _separable(seed=1)
    ids = [f"t{i}" for i in range(len(scores))]
    with pytest.raises(CalibrationLeakError):
        calibrate_and_freeze(
            scores, labels, scores, labels,
            calibration_task_ids=ids, holdout_task_ids=ids[:5] + ["t_only_in_holdout"],
        )


def test_disjoint_task_ids_do_not_raise():
    scores, labels = _separable(seed=1)
    ids = [f"t{i}" for i in range(len(scores))]
    half = len(ids) // 2
    r = calibrate_and_freeze(
        scores[:half], labels[:half], scores[half:], labels[half:],
        calibration_task_ids=ids[:half], holdout_task_ids=ids[half:],
    )
    assert r.calibration_task_ids == frozenset(ids[:half])
    assert r.holdout_task_ids == frozenset(ids[half:])


def test_missing_task_ids_skips_the_check_rather_than_crashing():
    scores, labels = _separable(seed=1)
    r = calibrate_and_freeze(scores, labels, scores, labels)  # no ids given at all
    assert r.frozen


def test_degenerate_calibration_set_freezes_nothing():
    """All-one-class calibration data: no threshold exists to freeze, and the
    function says so rather than fabricating one."""
    r = calibrate_and_freeze([0.1, 0.2, 0.3], [1, 1, 1], [0.1, 0.9], [0, 1])
    assert not r.frozen and r.threshold is None
    assert r.headline == {"available": False, "note": "calibration half degenerate; no threshold to freeze"}


def test_degenerate_holdout_set_reports_unavailable_not_fabricated():
    cal_scores, cal_labels = _separable(seed=1)
    r = calibrate_and_freeze(cal_scores, cal_labels, [0.1, 0.2, 0.3], [0, 0, 0])
    assert r.frozen and r.threshold is not None  # the threshold itself is still fine
    assert r.headline["available"] is False


def test_headline_matches_a_hand_computed_confusion_matrix():
    """Not just 'some number came out' -- the headline sensitivity/specificity
    must match a hand-worked confusion matrix for the frozen threshold."""
    cal_scores, cal_labels = [0.0, 1.0], [0, 1]  # threshold lands at 1.0 (score >= threshold)
    hold_scores = [1.0, 1.0, 0.0, 0.5]
    hold_labels = [1, 0, 0, 1]
    r = calibrate_and_freeze(cal_scores, cal_labels, hold_scores, hold_labels)
    assert r.threshold == 1.0
    # >= 1.0: indices 0,1 predicted positive; 2,3 predicted negative.
    # labels:                1, 0,          0, 1
    # TP=1 (idx0), FP=1 (idx1), FN=1 (idx3), TN=1 (idx2)
    assert r.headline["sensitivity"] == pytest.approx(0.5)
    assert r.headline["specificity"] == pytest.approx(0.5)
    assert r.headline["roc_auc"] == roc_auc(hold_scores, hold_labels)["auc"]


# ---------------------------------------------------------------------------
# stratified_calibration_split
# ---------------------------------------------------------------------------

def test_split_is_disjoint_and_covers_every_task():
    ids = [f"t{i}" for i in range(40)]
    strata = (["csn"] * 20) + (["post"] * 20)
    cal, hold = stratified_calibration_split(ids, strata, seed=7)
    assert set(cal) & set(hold) == set()
    assert set(cal) | set(hold) == set(ids)


def test_split_is_proportional_within_each_stratum():
    ids = [f"t{i}" for i in range(10)] + [f"p{i}" for i in range(30)]
    strata = (["csn"] * 10) + (["post"] * 30)
    cal, hold = stratified_calibration_split(ids, strata, seed=3, calibration_fraction=0.5)
    cal_csn = sum(1 for t in cal if t.startswith("t"))
    cal_post = sum(1 for t in cal if t.startswith("p"))
    assert cal_csn == 5    # half of the 10 csn tasks, not swamped by the 30 post tasks
    assert cal_post == 15  # half of the 30 post tasks


def test_split_is_deterministic_for_a_fixed_seed():
    ids = [f"t{i}" for i in range(20)]
    strata = ["csn"] * 20
    a = stratified_calibration_split(ids, strata, seed=5)
    b = stratified_calibration_split(ids, strata, seed=5)
    assert a == b


def test_different_seeds_usually_give_different_splits():
    ids = [f"t{i}" for i in range(30)]
    strata = ["csn"] * 30
    a = stratified_calibration_split(ids, strata, seed=1)
    b = stratified_calibration_split(ids, strata, seed=2)
    assert a != b


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        stratified_calibration_split(["t0", "t1"], ["csn"], seed=1)


# ---------------------------------------------------------------------------
# calibration_record
# ---------------------------------------------------------------------------

def test_record_includes_provenance_and_sorted_ids():
    scores, labels = _separable(seed=1)
    ids = [f"t{i}" for i in range(len(scores))]
    half = len(ids) // 2
    r = calibrate_and_freeze(
        scores[:half], labels[:half], scores[half:], labels[half:],
        calibration_task_ids=ids[:half], holdout_task_ids=ids[half:],
    )
    rec = calibration_record(r, corpus_sha256="abc123", seed=7)
    assert rec["threshold"] == r.threshold
    assert rec["corpus_sha256"] == "abc123" and rec["seed"] == 7
    assert rec["calibration_task_ids"] == sorted(ids[:half])
