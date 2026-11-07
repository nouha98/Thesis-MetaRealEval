"""scripts/analyze_results.py: RQ2 missingness report and the pilot-exclusion filter."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture
def ar(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "analyze_results_missing_under_test", REPO_ROOT / "scripts" / "analyze_results.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RESULTS = tmp_path
    module.EXCLUDE.clear()
    return module


def _pass_rates(root: Path, label: str, cells: dict) -> None:
    d = root / "rq2" / "evaluate" / label
    d.mkdir(parents=True)
    (d / "pass_rates.json").write_text(json.dumps(cells))


def test_the_cross_rq_join_reads_tier2_rows_and_counts_collapse_separately(ar):
    """Tier 2 hands per-task rows on although its RQ4 summary is 'unavailable' to the Tier 1
    reader. tau_b_drop is None where the ranking collapsed, so those tasks leave the join and
    are counted by the post-hoc collapse split instead."""
    def adequacy(deficit):
        return {"deficit": deficit}
    rq1 = {"per_task_adequacy": {f"T{i}": adequacy(d) for i, d in
                                 enumerate([0.5, 0.4, 0.3, 0.0, 0.0, 0.0, 0.2])}}
    row = lambda drop, collapsed: {"tau_b_drop": drop, "collapsed_at_top": collapsed}
    rq4 = {"available": False, "per_task": {
        "T0": row(0.9, False), "T1": row(0.7, False), "T2": row(None, True), "T3": row(0.1, False),
        "T4": row(0.0, False), "T5": row(None, True), "T6": row(None, True)}}
    out = ar.analyze_cross_rq(rq1, rq4)
    assert out["available"] and out["n_joined_tasks"] == 4                  # T2, T5, T6 have no drop
    g = out["weak_vs_strong_oracle"]
    assert (g["n_weak"], g["n_strong"]) == (2, 2)
    c = out["collapse_vs_oracle"]
    assert (c["collapsed_weak"], c["n_weak"], c["collapsed_strong"], c["n_strong"]) == (2, 4, 1, 3)
    assert 0 <= c["fisher_exact_p"] <= 1
    # Tier 1 rows carry no collapse flag: no split
    assert ar.analyze_cross_rq(rq1, {"available": True, "per_task": {"T0": {"tau_b_drop": 0.1}}}
                               )["collapse_vs_oracle"] is None


def test_missing_and_incomplete_cells_are_counted_and_flag_complete_case(ar, tmp_path):
    ok = {"n": 10, "pass@1": 0.5}
    _pass_rates(tmp_path, "T_0", {"original": {"a": ok, "b": ok}})
    _pass_rates(tmp_path, "T_1", {"original": {"a": ok, "b": {"n": 0, "pass@1": 0.0}}})
    _pass_rates(tmp_path, "T_2", {"original": {"a": ok, "b": {"n": 7, "incomplete": True,
                                                               "pass@1": None}}})
    rep = ar.analyze_rq2_missingness()
    assert rep["n_tasks"] == 3
    assert rep["tasks_with_missing_or_incomplete"] == ["T_1", "T_2"]
    assert rep["complete_case_is_qualified"] is True
    assert rep["by_model"]["b"]["original"] == {"cells": 3, "missing": 1, "incomplete": 1}
    assert rep["by_model"]["a"]["original"] == {"cells": 3}


def test_excluded_tasks_disappear_from_every_task_listing(ar, tmp_path):
    ok = {"n": 10, "pass@1": 0.5}
    _pass_rates(tmp_path, "T_0", {"original": {"a": ok}})
    _pass_rates(tmp_path, "T_1", {"original": {"a": {"n": 0}}})
    ar.EXCLUDE.update({"T_1"})
    assert [d.name for d in ar._task_dirs(tmp_path / "rq2" / "evaluate")] == ["T_0"]
    rep = ar.analyze_rq2_missingness()
    assert rep["n_tasks"] == 1 and rep["complete_case_is_qualified"] is False


def test_evaluation_errors_are_reported_as_missingness(ar, tmp_path):
    ok = {"n": 10, "pass@1": 0.5}
    _pass_rates(tmp_path, "T_0", {"original": {"a": ok, "b": {"n": 10, "evaluation_error": [2],
                                                              "pass@1": None, "correct": None}}})
    rep = ar.analyze_rq2_missingness()
    assert rep["by_model"]["b"]["original"] == {"cells": 1, "evaluation_error": 1}
    assert rep["tasks_with_missing_or_incomplete"] == ["T_0"]


def _rankings(root: Path, label: str, score: str, filename: str = "rankings.json") -> None:
    d = root / "rq2" / "evaluate" / label
    (d / filename).write_text(json.dumps({"score": score, "model_ids": ["a", "b"],
                                          "tau_b_per_relation": {}}))


def test_rq2_uses_the_rankings_score_and_counts_informative_pairs(ar, tmp_path):
    cell = lambda p1, g: {"n": 10, "correct": int(p1 * 10), "pass@1": p1, "mean_primary": g}  # noqa: E731
    # Binary: a and b tie at 0 under both prompts -> no informative pair.
    # Graded: a > b originally, b > a under 'formal' -> one informative reversal.
    _pass_rates(tmp_path, "T_0", {"original": {"a": cell(0.0, 0.6), "b": cell(0.0, 0.4)},
                                  "formal": {"a": cell(0.0, 0.3), "b": cell(0.0, 0.5)}})
    _rankings(tmp_path, "T_0", "mean_primary")
    graded = ar.analyze_rq2()
    assert graded["score"] == "mean_primary"
    rr = graded["pairwise_reversal_rate"]
    assert (rr["n_pair_comparisons"], rr["n_tied_excluded"], rr["n_informative"]) == (1, 0, 1)
    assert graded["task_strata"]["discriminating"] == 1

    _rankings(tmp_path, "T_0", "pass@1", filename="rankings_pass1.json")
    ar.RANKINGS = "rankings_pass1.json"
    binary = ar.analyze_rq2()
    assert binary["score"] == "pass@1"
    rr = binary["pairwise_reversal_rate"]
    assert (rr["n_pair_comparisons"], rr["n_tied_excluded"], rr["n_informative"]) == (1, 1, 0)
    assert binary["task_strata"]["floor"] == 1, "binary sees a floor task the graded score separates"
