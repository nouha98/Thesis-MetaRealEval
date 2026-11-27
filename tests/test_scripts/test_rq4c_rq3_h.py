"""RQ4c held-out detection aggregates (eval_heldout), the arm gate (freeze_h.unlock) and RQ3 with H
(analyze_rq3_h): scored-solution rule, labels and metrics."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import analyze_rq3_h as rq3  # noqa: E402
import eval_heldout as eh  # noqa: E402
import freeze_h as fh  # noqa: E402


def test_heldout_aggregate_reports_h_only_and_intervals():
    rows = [{"task": "A", "populations": ["primary/generated"], "p_killed": True, "h_detected": True},
            {"task": "A", "populations": ["primary/generated"], "p_killed": False, "h_detected": True},
            {"task": "B", "populations": ["primary/p_scenario", "stage0_nonequiv"], "p_killed": False, "h_detected": False},
            {"task": "B", "populations": ["primary/generated"], "p_killed": None, "h_detected": True}]   # no P verdict
    agg = eh.aggregate(rows)
    p = agg["primary"]
    assert p["groups"] == 3 and p["h_only"] == 1 and p["p_only"] == 0
    assert p["mean_task_rate_h_only"] == (0.5 + 0.0) / 2
    lo, hi = p["ci95"]["h_only"]
    assert 0.0 <= lo <= 0.25 <= hi <= 0.5
    assert agg["stage0_nonequiv"]["groups"] == 1


def test_arm_gate_needs_a_frozen_bundle_and_its_tasks(tmp_path):
    bundle, arm = tmp_path / "hidden_v1", tmp_path / "a3"
    for d, labs in ((bundle, ("T1", "T2")), (arm, ("T1",))):
        for lab in labs:
            (d / lab).mkdir(parents=True)
            (d / lab / "hidden_tests.py").write_text(f"# {lab}\n", encoding="utf-8")
            (d / lab / "a2.json").write_text("{}", encoding="utf-8")
    files = fh.bundle_hashes(bundle)
    rec = tmp_path / "rec.json"
    rec.write_text(json.dumps({"version": "tier2-hidden-v1", "tasks": ["T1", "T2"], "files": files,
                               "global_sha256": fh.global_digest(files)}), encoding="utf-8")
    (bundle / "freeze_manifest.json").write_text(json.dumps({"version": "tier2-hidden-v1"}), encoding="utf-8")
    fh.RECORDS["tier2-hidden-v1"], old = rec, fh.RECORDS["tier2-hidden-v1"]
    try:
        assert fh.unlock(bundle)["frozen_h_sha256"] == fh.global_digest(files)
        u = fh.unlock(arm, bundle)
        assert u["frozen_h_sha256"] is None and u["arm_of_sha256"] == fh.global_digest(files)
        (arm / "T9").mkdir()
        (arm / "T9" / "hidden_tests.py").write_text("", encoding="utf-8")
        with pytest.raises(SystemExit, match="outside the frozen H"):
            fh.unlock(arm, bundle)
        with pytest.raises(SystemExit):
            fh.unlock(arm)                       # an arm is never a frozen bundle itself
    finally:
        fh.RECORDS["tier2-hidden-v1"] = old


def mem(rel, model, i, p):
    return {"relation": rel, "model": model, "index": i, "stored_p_pass": p}


GRADING = {"tasks": [
    {"task": "T1", "rows": [{"h_pass": False, "members": [mem("original", "a", 0, False), mem("original", "a", 1, True)]},
                            {"h_pass": True, "members": [mem("original", "b", 0, True), mem("other", "a", 0, True)]}]},
    {"task": "T2", "rows": [{"h_pass": True, "members": [mem("original", "a", 0, True), mem("original", "b", 0, False)]}]},
    {"task": "T3", "rows": [{"h_pass": True, "members": [mem("original", "a", 0, True)]}]}]}
POP = {"tau_div": 0.5, "held_out_labels": ["T1", "T2", "T3", "T9"],
       "task_level": {"tasks": {"T1": {"pairwise_disagreement_rate": 0.9, "n_solutions": 2, "selected_relations": ["original"]},
                                "T2": {"pairwise_disagreement_rate": 0.2, "n_solutions": 2, "selected_relations": ["original"]},
                                "T3": {"pairwise_disagreement_rate": None, "n_solutions": 1, "selected_relations": ["original"]}}}}


def test_rq3_scored_solutions_follow_rq3s_rule():
    cells = rq3.outcomes(GRADING)["T1"]
    # first P-passing completion of (original, a) is index 1 (H fails); the "other" relation is not selected
    assert rq3.scored(cells, ["original"], False) == [("original", "a", 1, True, False), ("original", "b", 0, True, True)]
    assert rq3.scored(cells, ["original"], True)[0] == ("original", "a", 0, False, False)       # first completion


def test_rq3_labels_and_metrics():
    res = rq3.analyse(GRADING, {"T1", "T2", "T3"}, POP)
    s = res["primary_selection"]
    assert res["population"] == 3 and s["skipped"] == [{"task": "T3", "reason": "no RQ3 score"}]
    lab = {r["task"]: (r["label_primary"], r["label_secondary"]) for r in s["tasks"]}
    assert lab == {"T1": (1, 1), "T2": (0, 1)}
    assert s["primary"]["auc"] == 1.0 and s["primary"]["sensitivity"] == 1.0 and s["primary"]["specificity"] == 1.0
    assert s["secondary"]["auc"] is None and s["secondary"]["n_positive"] == 2           # one class only
    first = res["first_completion_sensitivity"]
    assert {r["task"]: r["label_primary"] for r in first["tasks"]} == {"T1": 0, "T2": 0}  # index 0 of a fails P
