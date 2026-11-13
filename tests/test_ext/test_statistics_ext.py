"""Statistics helpers added for the extensions; undefined quantities are None, never 0 or NaN."""

import math

import pytest

from meta_real_eval.analysis import statistics as st


def test_safe_ratio():
    assert st.safe_ratio(1, 4) == 0.25 and st.safe_ratio(3, 0) is None


def test_wilson_matches_the_textbook_value():
    r = st.wilson_ci(4, 120)          # Gate C v1 random-sample rate
    assert r["p"] == pytest.approx(4 / 120)
    assert r["lo"] == pytest.approx(0.0130, abs=5e-4) and r["hi"] == pytest.approx(0.0826, abs=5e-4)
    assert st.wilson_ci(0, 0)["p"] is None
    assert st.wilson_ci(0, 10)["lo"] == 0.0


def test_mcnemar_and_sign_test():
    assert st.mcnemar_exact(0, 0)["p_value"] is None
    assert st.mcnemar_exact(10, 0)["p_value"] == pytest.approx(2 * 0.5 ** 10)
    s = st.sign_test([1, 2, -1, 0, 0])
    assert (s["n_positive"], s["n_negative"], s["n_zero"]) == (2, 1, 2)
    assert st.sign_test([0, 0])["p_value"] is None


def test_chi2_undefined_on_a_zero_margin():
    assert st.chi2_2x2_defined([[4, 0], [2, 0]])["chi2"] is None
    assert st.chi2_2x2_defined([[0, 0], [2, 3]])["p_value"] is None
    assert st.chi2_2x2_defined([[10, 2], [3, 9]])["p_value"] < 0.05


def test_spearman_defined():
    assert st.spearman_rho_defined([1, 1, 1], [1, 2, 3])["rho"] is None
    assert st.spearman_rho_defined([1, 2], [1, 2])["rho"] is None
    assert st.spearman_rho_defined([1, 2, 3], [1, 2, 3])["rho"] == pytest.approx(1.0)
    assert math.isnan(st.spearman_rho([1, 1, 1], [1, 2, 3])["rho"])     # historical function unchanged


def test_guards_on_inputs_that_used_to_raise():
    assert st.bootstrap_ci([]) == (None, None)
    assert st.bootstrap_ci([1.0, 2.0, 3.0]) == st.bootstrap_ci([1.0, 2.0, 3.0])
    assert st.cochran_q([]) == {"q": None, "p_value": None, "n_blocks": 0, "k": 0}


def test_paired_cluster_bootstrap_weights_values_not_clusters():
    r = st.paired_cluster_bootstrap({"t1": [1.0, 1.0, 1.0], "t2": [0.0]})
    assert r["mean"] == pytest.approx(0.75) and r["n_clusters"] == 2 and r["n_values"] == 4
    assert r["lo"] <= r["mean"] <= r["hi"]
    assert st.paired_cluster_bootstrap({})["mean"] is None
    assert st.paired_cluster_bootstrap({"t": []})["mean"] is None


def test_holm():
    out = st.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
    assert out["a"]["p_adjusted"] == pytest.approx(0.03) and out["a"]["reject"]
    assert out["c"]["p_adjusted"] == pytest.approx(0.06) and not out["c"]["reject"]
    assert out["b"]["p_adjusted"] == pytest.approx(0.06) and not out["b"]["reject"]
    assert out["d"]["p_adjusted"] is None and out["d"]["reject"] is None
