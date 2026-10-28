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
