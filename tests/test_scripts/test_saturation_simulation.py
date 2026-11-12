"""scripts/saturation_simulation.py and saturation_common.py: the per-task row, the weighted
statistics, the random controls, and the independent-halves selection."""

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import saturation_common as sc  # noqa: E402
import saturation_simulation as ss  # noqa: E402

MODELS = ["a", "b", "c"]
UNIVERSE = ["control_resample", "llm_lexical_01", "llm_formal_01"]


def scores(**by_rel):
    return {rel: dict(zip(MODELS, vals)) for rel, vals in by_rel.items()}


def row(**by_rel):
    return ss.build_row(scores(**by_rel), UNIVERSE, MODELS, min_cov=1)


def test_a_task_row_matches_the_rq2_definitions():
    r = row(original=(1.0, 0.5, 0.0), control_resample=(1.0, 0.5, 0.0), llm_lexical_01=(0.0, 0.5, 1.0))
    assert r["tau_c"] == 1.0 and r["tau_p"] == -1.0 and r["covered"]
    assert r["rev_c"] == 0.0 and r["rev_p"] == 1.0                    # all three pairs reversed
    assert (r["n_cmp"], r["n_tied"]) == (6, 0)
    assert (r["rel_total"], r["rel_undef"]) == (3, 1)                 # llm_formal_01 has no cell: undefined, not 0
    assert r["base_disc"] and not r["floor"] and not r["ceiling"] and r["lb_ok"]
    assert r["difficulty"] == pytest.approx(0.5) and r["spread"] == 1.0


def test_tied_baselines_are_undefined_never_imputed():
    r = row(original=(1.0, 1.0, 1.0), control_resample=(1.0, 1.0, 1.0), llm_lexical_01=(1.0, 0.0, 0.0))
    assert r["ceiling"] and not r["base_disc"]
    assert math.isnan(r["tau_c"]) and math.isnan(r["tau_p"])           # no ordering to preserve
    assert (r["n_cmp"], r["n_tied"]) == (6, 6)                         # every pair tied on the baseline
    mid = row(original=(0.5, 0.5, 0.5), control_resample=(0.5, 0.5, 0.5))
    assert not mid["floor"] and not mid["ceiling"] and not mid["base_disc"]   # non-extreme yet no ranking


def test_the_coverage_gate_removes_both_arms():
    r = ss.build_row(scores(original=(1.0, 0.5, 0.0), control_resample=(1.0, 0.5, 0.0), llm_lexical_01=(0.0, 0.5, 1.0)),
                     UNIVERSE, MODELS, min_cov=2)
    assert not r["covered"] and math.isnan(r["tau_c"]) and math.isnan(r["tau_p"])
    assert r["rev_c"] == 0.0                                           # reversal is not coverage-gated, as in RQ2
    assert not r["lb_ok"]


def arrays(rows):
    return ss.to_arrays(rows)


def three_tasks():
    good = row(original=(1.0, 0.5, 0.0), control_resample=(1.0, 0.5, 0.0), llm_lexical_01=(0.0, 0.5, 1.0))
    mild = row(original=(1.0, 0.5, 0.0), control_resample=(1.0, 0.0, 0.5), llm_lexical_01=(1.0, 0.5, 0.0))
    ceil = row(original=(1.0, 1.0, 1.0), control_resample=(1.0, 1.0, 1.0), llm_lexical_01=(1.0, 1.0, 1.0))
    return arrays([good, mild, ceil])


def test_weighted_metrics_equal_a_plain_average_and_ignore_zero_weights():
    A = three_tasks()
    m = ss.metrics(A, np.array([[1.0, 1.0, 1.0], [1.0, 0.0, 5.0], [0.0, 2.0, 0.0]]))
    assert m["n_tau_c"].tolist() == [2, 1, 2]                          # the ceiling task is never defined
    assert m["mean_tau_p"][0] == pytest.approx((-1.0 + 1.0) / 2)
    assert m["mean_tau_c"][1] == pytest.approx(1.0)                    # weight 0 on 'mild' and weight 5 on the ceiling task
    assert m["yield_both"][0] == pytest.approx(2 / 3)
    both = ~np.isnan(A["tau_c"]) & ~np.isnan(A["tau_p"])
    expected = np.mean((A["tau_c"] - A["tau_p"])[both])                          # paired: control minus paraphrase
    assert m["gap_paired"][0] == pytest.approx(expected) and expected == pytest.approx(2 / 3)
    only_mild = A["tau_c"][1] - A["tau_p"][1]                                    # weights (0, 2, 0): the 'mild' task alone
    assert m["gap_paired"][2] == pytest.approx(only_mild) and only_mild == pytest.approx(1 / 3 - 1)


def test_removing_tasks_that_cannot_distinguish_models_leaves_the_tau_headline_unchanged():
    A = three_tasks()
    full = ss.metrics(A, np.ones((1, 3)))
    sub = ss.metrics(A, (~A["ceiling"]).astype(float)[None, :])
    for k in ("n_tau_c", "n_tau_p", "mean_tau_c", "mean_tau_p", "gap_paired", "rev_llm", "rev_ctrl", "n_rev_paired"):
        assert sub[k][0] == pytest.approx(full[k][0])
    lb_full = ss.leaderboard(A, np.ones((1, 3)))
    lb_sub = ss.leaderboard(A, (~A["ceiling"]).astype(float)[None, :])
    assert lb_full["margin_o"][0] != lb_sub["margin_o"][0]            # the leaderboard does respond to composition


def test_random_controls_never_look_at_the_outcomes():
    pool = np.ones(50, bool)
    w1 = ss.sample_weights(pool, 12, 20, np.random.default_rng(7))
    w2 = ss.sample_weights(pool, 12, 20, np.random.default_rng(7))
    assert (w1 == w2).all() and (w1.sum(1) == 12).all() and w1.max() == 1.0       # without replacement
    assert ss.sample_weights(pool, 80, 3, np.random.default_rng(1)).sum(1).tolist() == [50, 50, 50]
    b = ss.boot_weights(np.arange(10) < 4, 30, np.random.default_rng(3))
    assert (b.sum(1) == 4).all() and b[:, 4:].sum() == 0                            # stays inside the subset
    d = ss.dial_weights(np.arange(20) < 5, np.arange(20) >= 5, 0.4, 30, np.random.default_rng(3))
    assert (d.sum(1) == 20).all() and (d[:, :5].sum(1) == 8).all()                  # 40% from the discriminating pool


def test_terciles_partition_the_mask_with_label_order_breaking_ties():
    values = np.array([0.5, 0.5, 0.5, 0.1, 0.9, 0.5, 0.2])
    mask = np.array([True, True, True, True, True, True, False])
    g = ss.terciles(values, mask)
    assert sum(x.sum() for x in g) == 6 and not (g[0] & g[1]).any() and not (g[1] & g[2]).any()
    assert g[0][3] and g[2][4] and not any(x[6] for x in g)                         # lowest first, outside the mask never
    assert [x.sum() for x in g] == [2, 2, 2]


def test_leaderboard_ties_are_not_flips_and_reversals_are():
    A = {"lb_ok": np.array([True, True]), "S_o": np.array([[0.9, 0.5, 0.1], [0.9, 0.5, 0.1]]),
         "S_c": np.array([[0.9, 0.5, 0.1], [0.9, 0.5, 0.1]]), "S_p": np.array([[0.5, 0.9, 0.1], [0.5, 0.9, 0.1]])}
    out = ss.leaderboard(A, np.ones((1, 2)))
    assert not out["flip_c_any"][0] and out["flip_p_any"][0]
    # equal aggregates summed in a different order are a tie after rounding, not a flip
    A["S_p"] = np.array([[0.7 + 0.1, 0.8, 0.1], [0.8, 0.8, 0.1]])
    A["S_p"][0, 0] = 0.7 + 0.1 + 1e-16
    out = ss.leaderboard(A, np.ones((1, 2)))
    assert out["tie_p_any"][0]


def test_frequency_intervals_are_monte_carlo_not_percentiles_of_a_0_1_variable():
    f = ss.summ_freq(np.array([1.0] * 30 + [0.0] * 70))
    assert f["mean"] == pytest.approx(0.3) and 0.2 < f["lo"] < 0.3 < f["hi"] < 0.4
    assert ss.summ(np.array([1.0] * 30 + [0.0] * 70))["lo"] == 0.0              # what NOT to report for a frequency


def make_task(label, original, control, para):
    cell = lambda vals: {m: v for m, v in zip(MODELS, vals)}                      # noqa: E731
    raw = {"original": cell(original), "control_resample": cell(control), "llm_lexical_01": cell(para)}
    return SimpleNamespace(label=label, raw=raw, scores={}, universe=UNIVERSE, stored_tau={})


def test_the_independent_halves_select_on_one_half_and_evaluate_on_the_other():
    # first half: every model passes everything (a ceiling task); second half: the models differ.
    orig = [[1.0] * 5 + [1.0, 0.0, 0.0, 0.0, 0.0], [1.0] * 5 + [1.0, 1.0, 0.0, 0.0, 0.0], [1.0] * 5 + [1.0, 1.0, 1.0, 0.0, 0.0]]
    para = [[1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0], [1.0] * 10, [0.0] * 10]
    run = SimpleNamespace(models=MODELS, min_cov=1, key="pass@1", tasks=[make_task("T", orig, orig, para)])
    out = ss.crossfit(run, 5, np.random.default_rng(0))
    a_to_b, b_to_a = out["S1b_baseline_discriminating"]["direction_A_to_B"], out["S1b_baseline_discriminating"]["direction_B_to_A"]
    assert a_to_b["n_tasks"] == 0                                   # selected on half A: a ceiling task, so not selected
    assert b_to_a["n_tasks"] == 1                                   # selected on half B, evaluated on half A


def test_deep_diff_ignores_prose_notes_and_extra_keys_and_flags_numbers():
    worst, other = sc.deep_diff({"a": 1.0, "note": "old wording", "b": [1, 2]}, {"a": 1.0 + 1e-12, "note": "new", "b": [1, 2], "c": 5})
    assert worst < 1e-9 and not other
    worst, other = sc.deep_diff({"a": 1.0, "b": None}, {"a": 1.5, "b": 3})
    assert worst == pytest.approx(0.5) and len(other) == 2


def test_the_tree_hash_is_content_based_and_detects_any_change(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "REPO", tmp_path)                    # hash_tree reports paths relative to the repo
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "a.json").write_text("1")
    (tmp_path / "x" / "b.json").write_text("2")
    h1 = sc.hash_tree(tmp_path / "x", ["*.json"])
    assert h1["n_files"] == 2 and sc.hash_tree(tmp_path / "x", ["*.json"])["tree_sha256"] == h1["tree_sha256"]
    (tmp_path / "x" / "b.json").write_text("3")                   # one byte changed
    assert sc.hash_tree(tmp_path / "x", ["*.json"])["tree_sha256"] != h1["tree_sha256"]
    (tmp_path / "x" / "b.json").write_text("2")
    (tmp_path / "x" / "c.json").write_text("4")                   # one file added
    assert sc.hash_tree(tmp_path / "x", ["*.json"])["n_files"] == 3


def test_the_views_are_copies_and_leave_every_original_untouched():
    """The baseline freeze must still hold after the whole analysis ran (read-only on all inputs)."""
    manifest = sc.OUT / "baseline_manifest.json"
    if not manifest.exists():
        pytest.skip("baseline not frozen on this machine")
    import saturation_baseline as sb
    assert sb.verify_unchanged() == []
