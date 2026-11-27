"""run_witness.py guards for the full run (reviewed contracts only, G2 record, task selection) and
the stored-file checks of gate_g2.py."""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import gate_g2 as g2  # noqa: E402
import run_witness as rw  # noqa: E402
from meta_real_eval.benchmarks.witness import WitnessSettings  # noqa: E402

DEV = ["A", "B"]


def contract(status, supported):
    return {"review": {"status": status}, "support": {"supported": supported, "reasons": []}}


def test_only_reviewed_contracts_count():
    draft = rw.reviewed_only(contract("draft", True))
    assert draft["support"]["supported"] is False and "not reviewed" in draft["support"]["reasons"][-1]
    original = contract("draft", True)
    rw.reviewed_only(original)
    assert original["support"]["supported"] is True                      # the input is not modified
    assert rw.reviewed_only(contract("reviewed", True))["support"]["supported"] is True
    assert rw.reviewed_only(contract("draft", False))["support"]["reasons"] == []


def test_task_selection():
    assert rw.select_labels(["dev"], ["A", "B", "C", "D"], DEV) == DEV
    assert rw.select_labels(["eval"], ["D", "A", "C", "B"], DEV) == ["C", "D"]
    assert rw.select_labels(["C"], ["A", "C"], DEV) == ["C"]


def g2_record(tmp_path, **kw):
    rec = {"passed": True, "gated": True, "witness_settings": vars_of(WitnessSettings()), **kw}
    p = tmp_path / "G2.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    return p


def vars_of(s):
    import dataclasses
    return dataclasses.asdict(s)


def test_full_run_needs_a_passed_authoritative_g2_with_the_same_settings(tmp_path):
    s = WitnessSettings()
    with pytest.raises(SystemExit, match="gate G2 first"):
        rw.require_g2(None, s, True)
    with pytest.raises(SystemExit, match="authoritative"):
        rw.require_g2(g2_record(tmp_path), s, False)
    with pytest.raises(SystemExit, match="did not pass"):
        rw.require_g2(g2_record(tmp_path, passed=False), s, True)
    with pytest.raises(SystemExit, match="settings differ"):
        rw.require_g2(g2_record(tmp_path), WitnessSettings(pool_size=10), True)
    ok = rw.require_g2(g2_record(tmp_path), s, True)
    assert len(ok["sha256"]) == 64


def result(task, groups, status="reviewed", supported=True):
    return {"task": task, "gated": True, "contract": {"status": status, "path": "x"},
            "support": {"supported": supported, "reasons": [] if supported else ["r"]}, "groups": groups}


def group(gid, outcome, **kw):
    return {"group_id": gid, "outcome": outcome, **kw}


MANIFEST = {"settings": {"gated": True}, "checks": {"canary": {"verdict": {"ok": True}}}}


def test_static_checks_pass_on_a_clean_pilot():
    res = [result("A", [group("g1", "distinguished", level="api_visible", domain="valid", replay={"confirmed": True}),
                        group("g2", "unresolved", reason="no difference within budget (not an equivalence certificate)")]),
           result("B", [group("g3", "unsupported")], status="draft", supported=False)]
    checks = g2.static_checks(res, MANIFEST, DEV, [])
    assert all(c["ok"] for c in checks.values()), checks


def test_static_checks_catch_each_failure():
    res = [result("A", [group("g1", "distinguished", replay={"confirmed": False}),
                        group("g2", "unresolved", reason="no difference"),
                        group("g3", "equivalent")], status="draft")]
    checks = g2.static_checks(res, {"settings": {"gated": False}, "checks": {}}, DEV, ["B"])
    assert {k for k, c in checks.items() if not c["ok"]} == {
        "authoritative", "all_dev_tasks", "reviewed_contracts", "taxonomy", "canary", "replay_stored"}
    assert checks["taxonomy"]["unknown"] == ["equivalent"]
    assert checks["all_dev_tasks"]["missing"] == ["B"]


def test_heldout_populations_and_aggregate():
    import eval_heldout as eh
    prim = {"outcome": "distinguished", "level": "api_visible", "domain": "valid", "replay": {"confirmed": True},
            "origin": "generated", "members": [{"equivalence": "divergence", "killed": False}]}
    eq = {"outcome": "unresolved", "members": [{"equivalence": "no_divergence", "killed": None}]}
    assert eh.populations(prim) == ["primary/generated", "stage0_nonequiv"] and eh.populations(eq) == []
    assert eh.p_killed(prim) is False and eh.p_killed(eq) is None
    assert eh.hidden_names("def test_h_0():\n    pass\n\ndef helper():\n    pass\ndef test_h_1():\n") == \
        ["test_h_0", "test_h_1"]
    rows = [{"task": "A", "populations": ["primary/generated"], "p_killed": False, "h_detected": True},
            {"task": "A", "populations": ["primary/generated"], "p_killed": True, "h_detected": True},
            {"task": "B", "populations": ["stage0_nonequiv"], "p_killed": True, "h_detected": False}]
    agg = eh.aggregate(rows)
    assert agg["primary"]["groups"] == 2 and agg["primary"]["h_only"] == 1 and agg["primary"]["mean_task_rate_p"] == 0.5
    assert agg["stage0_nonequiv"]["p_only"] == 1


def test_replay_target_restores_nontermination():
    assert g2.replay_target({"level": "api_visible", "kind": "nontermination", "domain": "valid"}) == \
        ("nontermination", "valid")
    assert g2.replay_target({"level": "api_visible", "kind": "api_value", "domain": "valid"}) == ("api_visible", "valid")
    assert g2.replay_target({"level": "private_state_only", "kind": None, "domain": "valid"}) == \
        ("private_state_only", "valid")


def test_grade_hidden_compare_lists_only_extra_rejections(tmp_path):
    import grade_hidden as gh

    def grading(rows):
        return {"tasks": [{"task": "A", "rows": rows}]}
    row = lambda gid, p, h: {"group_id": gid, "p_pass": p, "h_pass": h, "members": [{}], "models": ["m"],  # noqa: E731
                             "differences": {"test_h_0": ["api:s1: 1 != 2"]}, "code": "class C: pass"}
    small = [row("g1", True, True), row("g2", True, False), row("g3", False, True), row("g4", True, True)]
    large = [row("g1", True, False), row("g2", True, False), row("g3", False, False), row("g4", True, True)]
    a, b = tmp_path / "k3" / "grading.json", tmp_path / "k5" / "grading.json"
    for p, rows in ((a, small), (b, large)):
        p.parent.mkdir()
        p.write_text(json.dumps(grading(rows)), encoding="utf-8")
    out = tmp_path / "cmp.md"
    gh.compare(a, b, out)
    text = out.read_text(encoding="utf-8")
    assert "**1 case(s).**" in text and "program g1" in text and "g2" not in text and "g3" not in text


def test_rq1_paired_rank_biserial():
    import analyze_rq1_witness as ar
    assert ar.rank_biserial([-0.5, -0.2, 0.0]) == -1.0
    assert ar.rank_biserial([0.0]) is None


def test_grade_hidden_failure_kinds():
    import grade_hidden as gh
    exc = ["exc", ["builtins.ValueError"]]
    assert gh.failure_kind(["@type", ["seq"]], exc) == "unexpected_exception"
    assert gh.failure_kind(["@any"], exc) == "unexpected_exception"
    assert gh.failure_kind(exc, ["none"]) == "missing_documented_exception"
    assert gh.failure_kind(exc, ["exc", ["builtins.KeyError"]]) == "other_exception_type"
    assert gh.failure_kind(["@type", ["seq"]], ["map", "builtins.dict", []]) == "type"
    assert gh.failure_kind(["int", "1"], ["int", "2"]) == "value"
    assert gh.failure_kind(["int", "1"], None) == "stopped_earlier"


def test_audit_selection_sampling_and_estimates(tmp_path):
    import csv as _csv
    import audit_h as ah
    a2 = tmp_path / "a2"
    for lab, ready in (("T1", True), ("T2", False), ("T3", True)):
        (a2 / lab).mkdir(parents=True)
        (a2 / lab / "a2.json").write_text(json.dumps({"ready": ready}), encoding="utf-8")
    assert ah.ready_tasks(a2) == {"T1", "T3"}
    # the seeded per-task sample is reproducible and task-specific
    assert ah.task_rng("T1", 7).sample(range(20), 5) == ah.task_rng("T1", 7).sample(range(20), 5)
    assert ah.task_rng("T1", 7).sample(range(20), 5) != ah.task_rng("T3", 7).sample(range(20), 5)
    out = tmp_path / "audit"
    out.mkdir()
    rows = ([{"id": f"Q1-{i}", "question": "Q1", "task": f"T{i % 4}", "item": "t", "weight": 1.0, "failure_kinds": "",
              "verdict": "invalid" if i == 0 else "valid"} for i in range(20)]
            + [{"id": "Q2-1", "question": "Q2", "task": "T1", "item": "p", "weight": 2.0, "failure_kinds": "",
                "verdict": "unclear"}])
    with (out / "items.csv").open("w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ah.estimate(out)
    est = json.loads((out / "estimates.json").read_text(encoding="utf-8"))
    assert est["Q1"]["invalid"]["point"] == 0.05 and est["Q1"]["n_tasks"] == 4
    assert est["Q2"]["erroneous_unclear_as_fault"]["point"] == 0.0
    assert est["Q2"]["erroneous_unclear_as_erroneous"]["point"] == 1.0 and not est["acceptance"]["accepted"]
    zero = ah.exact_ci([{"v": "valid"}] * 97, lambda v: v == "invalid")     # 0 of 97: not [0, 0]
    assert zero["ci95"][0] == 0.0 and abs(zero["ci95"][1] - 0.0373) < 5e-4 and abs(zero["upper95_one_sided"] - 0.0304) < 5e-4


def test_audit_show_token():
    import audit_h as ah
    assert ah.show_token(["@any"]) == "returns normally"
    assert ah.show_token(["@type", ["seq"]]) == "returns a value of kind seq"
    assert ah.show_token(["exc", ["builtins.ValueError", "builtins.Exception"]]) == "raises builtins.ValueError"


def test_freeze_needs_acceptance_and_decision_then_verifies(tmp_path):
    import freeze_h as fh
    a2, audit, out = tmp_path / "a2", tmp_path / "audit", tmp_path / "hidden_v1"
    for lab, ready in (("T1", True), ("T2", False)):
        (a2 / lab).mkdir(parents=True)
        (a2 / lab / "a2.json").write_text(json.dumps({"ready": ready}), encoding="utf-8")
        (a2 / lab / "hidden_tests.py").write_text(f"def test_h_0():\n    assert '{lab}'\n", encoding="utf-8")
    audit.mkdir()
    for f in ("items.csv", "audit_reserved.json"):
        (audit / f).write_text("x", encoding="utf-8")
    decision, record = tmp_path / "decision.json", tmp_path / "record.json"
    (audit / "estimates.json").write_text(json.dumps({"acceptance": {"accepted": False}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="did not accept"):
        fh.freeze(a2, audit, out, decision, record)
    (audit / "estimates.json").write_text(json.dumps({"acceptance": {"accepted": True}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="section 7 decision"):
        fh.freeze(a2, audit, out, decision, record)
    decision.write_text(json.dumps({"components": ["A2", "A3"]}), encoding="utf-8")
    with pytest.raises(SystemExit, match="only H = A2"):
        fh.freeze(a2, audit, out, decision, record)
    decision.write_text(json.dumps({"components": ["A2"]}), encoding="utf-8")
    rec = fh.freeze(a2, audit, out, decision, record)
    assert rec["tasks"] == ["T1"] and set(rec["files"]) == {"T1/a2.json", "T1/hidden_tests.py"}
    assert fh.verify(out, record)["global_sha256"] == rec["global_sha256"]
    with pytest.raises(SystemExit, match="exists"):
        fh.freeze(a2, audit, tmp_path / "other", decision, record)       # never frozen twice
    (out / "T1" / "hidden_tests.py").write_text("def test_h_0():\n    pass\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="differs from the frozen H"):
        fh.verify(out, record)


def test_a3_precheck_keeps_only_a2_missed_primary_dev_groups():
    import a3_precheck as pc
    rows = [{"task": "D", "h_detected": False, "populations": ["primary/generated"]},
            {"task": "D", "h_detected": True, "populations": ["primary/generated"]},
            {"task": "D", "h_detected": False, "populations": ["stage0_nonequiv"]},
            {"task": "E", "h_detected": False, "populations": ["primary/p_scenario"]},
            {"task": "D", "h_detected": None, "populations": ["primary/generated"]}]
    assert pc.missed_groups(rows, {"D"}) == [rows[0]]



def test_stage5_review_sample_is_seeded_random_and_bounded():
    import audit_h as ah
    rows = [{"group_id": f"g{i:02d}", "p_pass": i % 4 != 0, "h_pass": i % 3 == 0, "members": [{}]} for i in range(40)]
    bad = {r["group_id"] for r in rows if r["p_pass"] and not r["h_pass"]}
    a = ah.review_sample(rows, "T1", 7)
    assert len(a) == min(ah.REVIEW_PER_TASK, len(bad)) and {r["group_id"] for r in a} <= bad
    assert [r["group_id"] for r in a] == [r["group_id"] for r in ah.review_sample(list(reversed(rows)), "T1", 7)]
    assert [r["group_id"] for r in a] != [r["group_id"] for r in ah.review_sample(rows, "T2", 7)]
    assert len(ah.review_sample(rows[:3], "T1", 7)) == len([r for r in rows[:3] if r["p_pass"] and not r["h_pass"]])
