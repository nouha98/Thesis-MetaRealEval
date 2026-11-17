"""scripts/saturation_rq_table.py (Note 3, plan rev. 3 Part A): cells, undefined handling, the
RQ3 task rule, and the cross-fit code path. The reproduction of the stored headline numbers is
checked by the script itself on the real results (``checks``)."""

import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import saturation_rq_table as rt  # noqa: E402
import saturation_simulation as ss  # noqa: E402

MODELS = ["a", "b", "c"]
UNIVERSE = ["control_resample", "llm_lexical_01", "llm_formal_01"]


def test_cells_are_none_with_a_reason_never_zero():
    c = rt.mean_cell([])
    assert c["mean"] is None and c["n"] == 0 and "reason" in c
    c = rt.mean_cell([float("nan"), None, 0.25])
    assert c["mean"] == 0.25 and c["n"] == 1 and c["lo"] is None          # one value: no interval
    a = rt.auc_cell([0.1, 0.9], [1, 1])
    assert a["auc"] is None and "one label class" in a["reason"]
    assert rt.perm_spearman([1.0, 1.0, 1.0], [0.1, 0.2, 0.3], 100)["rho"] is None


def test_paired_cell_is_operator_minus_llm_with_the_rq1_wilcoxon():
    c = rt.paired_cell([0.9, 0.8, 0.7, 0.6], [0.5, 0.5, 0.5, 0.5])
    assert c["mean"] == pytest.approx(0.25) and c["n"] == 4
    assert c["wilcoxon"]["statistic"] == 0.0                              # every difference positive


def test_permutation_p_is_valid_and_reproducible():
    x = list(np.arange(30.0))
    r1, r2 = rt.perm_spearman(x, x, 500), rt.perm_spearman(x, x, 500)
    assert r1 == r2 and r1["rho"] == pytest.approx(1.0) and r1["p_perm"] == pytest.approx(1 / 501)


def test_column_membership():
    strata = {"t1": {"non_extreme": True, "baseline_discriminating": False}}
    assert rt.in_column(strata, "t1", "all") and rt.in_column(strata, "t1", "non_extreme")
    assert not rt.in_column(strata, "t1", "baseline_discriminating") and not rt.in_column(strata, "zz", "all")


def test_rq3_task_rule_matches_analyze_rq3(tmp_path):
    root = tmp_path / "rq3" / "execute"
    cases = {
        "fails": {"pairwise_disagreement_rate": 0.5, "solutions": [
            {"consensus_disagreement_rate": 0.0, "passes_benchmark": True},
            {"consensus_disagreement_rate": 1.0, "passes_benchmark": False}]},
        "passes": {"pairwise_disagreement_rate": 0.1, "solutions": [
            {"consensus_disagreement_rate": 0.0, "passes_benchmark": True}]},
        "no_rate": {"pairwise_disagreement_rate": None, "solutions": [
            {"consensus_disagreement_rate": 0.0, "passes_benchmark": False}]},
        "no_consensus": {"pairwise_disagreement_rate": 0.3, "solutions": [{"passes_benchmark": False}]},
    }
    for name, dv in cases.items():
        (root / name).mkdir(parents=True)
        (root / name / "divergence.json").write_text(json.dumps(dv))
    out = rt.rq3_per_task(tmp_path)
    assert out == {"fails": (0.5, 1), "passes": (0.1, 0)}                 # undefined / unscored left out


def _run(n_tasks=24, seed=3):
    rng = np.random.default_rng(seed)
    tasks = []
    for i in range(n_tasks):
        raw, scores = {}, {}
        for rel in ["original"] + UNIVERSE:
            raw[rel] = {m: list(rng.choice([0.0, 1.0], size=10, p=[0.5, 0.5]) if i % 3 else
                                np.full(10, 0.5)) for m in MODELS}
            scores[rel] = {m: float(np.mean(v)) for m, v in raw[rel].items()}
        tasks.append(SimpleNamespace(label=f"t{i}", scores=scores, raw=raw, universe=UNIVERSE, stored_tau={}))
    return SimpleNamespace(models=MODELS, min_cov=1, tasks=tasks, key="mean_primary")


def test_crossfit_masks_reproduce_the_stored_crossfit_code_path():
    run = _run()
    mine = rt.crossfit_masks(run)
    ref = ss.crossfit(run, 0, np.random.default_rng(0))
    for k in ("S0_full", "S1b_baseline_discriminating"):
        for d in ("average_of_both_directions", "direction_A_to_B", "direction_B_to_A"):
            for key, v in ref[k][d].items():
                w = mine[k][d][key]
                assert (v is None and w is None) or (isinstance(v, float) and math.isnan(v) and math.isnan(w)) or v == w
    assert "S1a_non_extreme" in mine
    # tasks tied at 0.5 are non-extreme but not discriminating: S1a holds at least S1b's tasks
    assert mine["S1a_non_extreme"]["direction_A_to_B"]["n_tasks"] >= mine["S1b_baseline_discriminating"]["direction_A_to_B"]["n_tasks"]


def test_strata_follow_the_simulation_row():
    run = _run()
    strata = rt.strata_for(run)
    rows = [ss.build_row(t.scores, t.universe, MODELS, 1) for t in run.tasks]
    for t, r in zip(run.tasks, rows):
        s = strata[t.label]
        assert s["baseline_discriminating"] == r["base_disc"]
        assert s["non_extreme"] == (r["has_base"] and not r["floor"] and not r["ceiling"])
