"""Tests for the inferential statistics the thesis's claims rest on."""

import math

from meta_real_eval.analysis.statistics import (
    cliffs_delta,
    mannwhitney_test,
    roc_auc,
    spearman_rho,
    wilcoxon_test,
    youden_threshold,
)


# --- ROC-AUC (RQ3 headline metric) -----------------------------------------

def test_auc_is_one_for_a_perfect_separator():
    assert roc_auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1])["auc"] == 1.0


def test_auc_is_zero_when_the_score_is_perfectly_inverted():
    assert roc_auc([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1])["auc"] == 0.0


def test_auc_is_half_when_every_score_is_tied():
    assert roc_auc([0.5, 0.5, 0.5, 0.5], [0, 0, 1, 1])["auc"] == 0.5


def test_auc_is_none_when_only_one_class_is_present():
    """Reporting 0.5 here would fabricate a 'chance-level' result."""
    assert roc_auc([0.1, 0.9], [1, 1])["auc"] is None


# --- Youden's J (tau_div calibration) ---------------------------------------

def test_youden_finds_the_separating_cut_off():
    best = youden_threshold([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1])
    assert best["youden_j"] == 1.0
    assert 0.2 < best["threshold"] <= 0.8


def test_youden_is_undefined_for_a_single_class():
    assert youden_threshold([0.1, 0.9], [0, 0])["threshold"] is None


# --- effect sizes and group comparisons -------------------------------------

def test_cliffs_delta_is_one_when_a_dominates_b():
    assert cliffs_delta([5, 6, 7], [1, 2, 3]) == 1.0
    assert cliffs_delta([1, 2, 3], [1, 2, 3]) == 0.0


def test_wilcoxon_handles_all_zero_differences():
    """scipy raises on an all-tied input; the wrapper must not."""
    r = wilcoxon_test([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert r["p_value"] == 1.0
    assert r["cliffs_delta"] == 0.0


def test_mannwhitney_handles_independent_groups_of_different_size():
    r = mannwhitney_test([1, 2, 3], [7, 8, 9, 10])
    assert r["p_value"] < 0.1
    assert r["cliffs_delta"] == -1.0


def test_spearman_is_one_for_a_monotone_relationship():
    assert math.isclose(spearman_rho([1, 2, 3, 4], [10, 20, 30, 40])["rho"], 1.0)
