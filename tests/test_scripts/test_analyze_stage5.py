"""Stage 5 analysis (scripts/analyze_stage5.py): cohort from the freeze record, counts, leaderboard."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import analyze_stage5 as s5  # noqa: E402
import freeze_h as fh  # noqa: E402


def row(gid, h, members, outcomes=None, kinds=None):
    return {"group_id": gid, "h_pass": h, "members": members, "h_outcomes": outcomes or {},
            **({"failure_kinds": kinds} if kinds else {})}


def mem(model, p, i=0, rel="original"):
    return {"relation": rel, "model": model, "index": i, "stored_p_pass": p}


GRADING = {"isolation": "per_test_process", "tasks": [
    {"task": "RCE_csn_snippet_1", "rows": [
        row("g1", False, [mem("a", True)], {"test_h_0": "ordinary_fail"}, ["unexpected_exception"]),
        row("g2", True, [mem("b", True)]),
        # one test passed, one timed out: h_outcomes holds only the failing test, so this is timeout-only
        row("g3", False, [mem("a", False, 1)], {"test_h_1": "timeout"})]},
    {"task": "RCE_post_snippet_2", "rows": [row("g4", True, [mem("a", True), mem("b", False)])]},
    {"task": "RCE_post_snippet_9", "rows": [row("g5", False, [mem("a", True)], {"test_h_0": "ordinary_fail"})]}]}


def test_counts_split_and_leaderboard():
    res = s5.analyse(GRADING, {"RCE_csn_snippet_1", "RCE_post_snippet_2"})          # post_9 = audit task
    a = res["all"]
    assert a["completions"] == 5 and a["p_pass"] == 3 and a["p_and_h"] == 2 and a["p_pass_h_fail"] == 1
    assert a["p_pass_h_fail_exception_only"] == 1 and a["h_timeout_only"] == 1
    assert res["by_split"]["csn"]["completions"] == 3 and res["by_split"]["post"]["completions"] == 2
    assert res["tasks_with_p_pass_h_fail"] == ["RCE_csn_snippet_1"] and res["tasks_with_p_pass"] == 2
    lb = res["leaderboard_original"]
    assert lb["mean_score_p"] == {"a": 0.75, "b": 0.5} and lb["mean_score_p_and_h"] == {"a": 0.5, "b": 0.5}
    assert lb["rank_p"] == {"a": 1, "b": 2} and lb["rank_p_and_h"] == {"a": 1, "b": 1} and lb["order_changed"]
    assert abs(res["pass_at_1_original"]["a"]["diff"] - 0.25) < 1e-12


def test_collapse_to_tie_is_counted_not_dropped():
    pt = {("T", "a"): 1.0, ("T", "b"): 0.5, ("U", "a"): 0.5, ("U", "b"): 0.5, ("V", "a"): 1.0, ("V", "b"): 0.0}
    ph = {("T", "a"): 0.5, ("T", "b"): 0.5, ("U", "a"): 0.5, ("U", "b"): 0.0, ("V", "a"): 1.0, ("V", "b"): 0.0}
    lb = s5.leaderboard(pt, ph, ["a", "b"])
    assert lb["ranking_collapsed_to_tie"] == 1 and lb["tied_under_p"] == 1 and lb["tie_broken_by_h"] == 1
    assert lb["tau_b_tasks"] == 1 and lb["tau_b_mean"] == 1.0


def test_cohort_comes_from_the_freeze_record(tmp_path):
    bundle = tmp_path / "hidden_v1"
    for lab in ("RCE_csn_snippet_1", "RCE_post_snippet_2", "RCE_post_snippet_9"):
        (bundle / lab).mkdir(parents=True)
        (bundle / lab / "hidden_tests.py").write_text(f"# {lab}\n", encoding="utf-8")
        (bundle / lab / "a2.json").write_text("{}", encoding="utf-8")
    files = fh.bundle_hashes(bundle)
    record = tmp_path / "record.json"
    record.write_text(json.dumps({"tasks": sorted(p.name for p in bundle.iterdir()), "files": files,
                                  "global_sha256": fh.global_digest(files), "version": "v", "n_tasks": 3}),
                      encoding="utf-8")
    g = {**GRADING, "hidden": str(bundle)}
    audit = {"RCE_post_snippet_9"}
    assert s5.cohort_from_freeze(g, audit, record, 2) == {"RCE_csn_snippet_1", "RCE_post_snippet_2"}
    with pytest.raises(SystemExit, match="expected 55"):
        s5.cohort_from_freeze(g, audit, record, 55)
    with pytest.raises(SystemExit, match="graded tasks differ"):
        s5.cohort_from_freeze({**g, "tasks": g["tasks"][:2]}, audit, record, 2)
    with pytest.raises(SystemExit, match="another frozen H"):
        s5.cohort_from_freeze({**g, "frozen_h_sha256": "0" * 64}, audit, record, 2)
    (bundle / "RCE_csn_snippet_1" / "hidden_tests.py").write_text("# changed\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="differs from the frozen H"):
        s5.cohort_from_freeze(g, audit, record, 2)


def test_refuses_a_non_isolated_grading(tmp_path):
    path = tmp_path / "g.json"
    path.write_text(json.dumps({**GRADING, "isolation": None}), encoding="utf-8")
    (tmp_path / "audit.json").write_text(json.dumps({"tasks": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="isolated runner"):
        s5.main(["--grading", str(path), "--audit", str(tmp_path / "audit.json"), "--out", str(tmp_path / "o")])


def test_tau_tolerance_and_pairwise_gaps():
    pt = {("T", "a"): 1.0, ("T", "b"): 0.5, ("T", "c"): 0.0, ("U", "a"): 0.9, ("U", "b"): 0.3, ("U", "c"): 0.1}
    lb = s5.leaderboard(pt, dict(pt), ["a", "b", "c"])
    assert lb["tau_b_tasks"] == 2 and lb["tau_b_below_1"] == 0          # identical rankings: no spurious "below 1"
    g = lb["pairwise"]["a - b"]
    assert g["p"]["tasks"] == 2 and abs(g["p"]["gap"] - 0.55) < 1e-12 and g["p"]["ci95"][0] <= 0.55 <= g["p"]["ci95"][1]
    assert g["p_and_h"]["gap"] == g["p"]["gap"]


def test_main_resolves_the_record_from_the_bundle_and_writes_a_manifest(tmp_path, monkeypatch):
    bundle = tmp_path / "hidden_v1"
    (bundle / "RCE_csn_snippet_1").mkdir(parents=True)
    (bundle / "RCE_csn_snippet_1" / "hidden_tests.py").write_text("# t\n", encoding="utf-8")
    (bundle / "RCE_csn_snippet_1" / "a2.json").write_text("{}", encoding="utf-8")
    files = fh.bundle_hashes(bundle)
    record = tmp_path / "record.json"
    record.write_text(json.dumps({"tasks": ["RCE_csn_snippet_1"], "files": files, "global_sha256": fh.global_digest(files),
                                  "version": "tier2-hidden-v1", "n_tasks": 1}), encoding="utf-8")
    (bundle / "freeze_manifest.json").write_text(json.dumps({"version": "tier2-hidden-v1"}), encoding="utf-8")
    monkeypatch.setitem(fh.RECORDS, "tier2-hidden-v1", record)
    g = {"isolation": "per_test_process", "hidden": str(bundle), "tasks": [{**GRADING["tasks"][0], "task": "RCE_csn_snippet_1"}]}
    gp, ap_ = tmp_path / "g.json", tmp_path / "audit.json"
    gp.write_text(json.dumps(g), encoding="utf-8")
    ap_.write_text(json.dumps({"tasks": []}), encoding="utf-8")
    assert s5.main(["--grading", str(gp), "--audit", str(ap_), "--out", str(tmp_path / "o"), "--expect-cohort", "1"]) == 0
    assert (tmp_path / "o" / "run_manifest.json").is_file()
