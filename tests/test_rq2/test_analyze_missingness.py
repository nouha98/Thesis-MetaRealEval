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
