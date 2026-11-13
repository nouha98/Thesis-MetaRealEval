"""scripts/saturation_reporting_checks.py: paired vs marginal means, point margins and the
margin identity, on synthetic inputs."""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import saturation_reporting_checks as rc  # noqa: E402

NAN = float("nan")


def arrays(tau_c, tau_p):
    return {"tau_c": np.array(tau_c, float), "tau_p": np.array(tau_p, float)}


def test_paired_means_subtract_to_the_gap_while_marginal_means_do_not():
    # task 3 has only a control tau, task 4 only a paraphrase tau
    A = arrays([1.0, 0.5, 0.2, NAN], [0.0, 0.5, NAN, 1.0])
    p = rc.paired_vs_marginal(A, np.ones(4, bool))
    assert (p["n_tau_c"], p["n_tau_p"], p["n_both"]) == (3, 3, 2)
    assert p["marginal_tau_c"] == pytest.approx(1.7 / 3) and p["marginal_tau_p"] == pytest.approx(0.5)
    assert p["paired_tau_c"] == pytest.approx(0.75) and p["paired_tau_p"] == pytest.approx(0.25)
    assert p["gap_paired"] == pytest.approx(0.5)
    assert p["paired_means_subtract_to_gap"]
    assert not math.isclose(p["marginal_difference"], p["gap_paired"])


def test_no_defined_pair_gives_none_not_zero():
    p = rc.paired_vs_marginal(arrays([1.0, NAN], [NAN, 0.5]), np.ones(2, bool))
    assert p["n_both"] == 0 and p["gap_paired"] is None and p["paired_tau_c"] is None
    assert p["paired_means_subtract_to_gap"]


def test_margin_record_names_the_closest_adjacent_pair():
    lb_point = {"n_tasks": 10, "scores_original": [0.50, 0.70, 0.52], "margin_original": 0.02}
    lb_boot = {"margin_o": {"mean": 0.05, "lo": 0.0, "hi": 0.1}}
    m = rc.margin_record(["a", "b", "c"], lb_point, lb_boot)
    assert m["order"] == ["b", "c", "a"]
    assert m["point_margin"] == pytest.approx(0.02) and m["point_margin_pair"] == ["c", "a"]
    assert m["bootstrap_mean_of_min_margin"] == 0.05


def test_margin_identity_holds_when_extra_tasks_have_equal_scores():
    # discriminating: 2 tasks, scores per model summed (1.0, 0.5, 0.0) -> means over 2
    disc = {"n_tasks": 2, "scores_original": [0.5, 0.25, 0.0]}
    # add 6 tasks where all models score 1.0: sums become (7, 6.5, 6), means over 8
    full = {"n_tasks": 8, "scores_original": [7 / 8, 6.5 / 8, 6 / 8]}
    sim = {"subsets": {"S0_full": {"leaderboard_point": full},
                       "S1b_baseline_discriminating": {"leaderboard_point": disc}}}
    chk = rc.margin_identity(["a", "b", "c"], sim, "S0_full")
    assert chk["ok"] and chk["compression_factor"] == pytest.approx(0.25)
    sim["subsets"]["S0_full"]["leaderboard_point"] = {"n_tasks": 8, "scores_original": [0.9, 6.5 / 8, 6 / 8]}
    assert not rc.margin_identity(["a", "b", "c"], sim, "S0_full")["ok"]
