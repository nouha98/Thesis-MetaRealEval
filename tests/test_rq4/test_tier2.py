"""RQ4 for Tier 2 (plan rev. 6, section 8): eligibility, the level-0.0 baseline
check against RQ2's own evaluator, missing levels, and the analysis."""

from __future__ import annotations

import gzip
import json

import pytest

from meta_real_eval.benchmarks.base import DegradedSuite, SuiteResult
from meta_real_eval.benchmarks.gate import VALID_BEHAVIOURAL, VALID_EXCEPTION_ORACLE, GatedTest
from meta_real_eval.benchmarks.outcomes import TestOutcome
from meta_real_eval.core.checkpoint import is_done, task_dir
from meta_real_eval.core.config import Config
from meta_real_eval.rq4 import tier2

MODELS = ["m_a", "m_b", "m_c"]

REFERENCE = '''\
class Counter:
    def __init__(self, start=0):
        self.count = start

    def add(self, n):
        if n < 0:
            raise ValueError("negative")
        self.count += n
        return self.count
'''
SKELETON = "class Counter:\n    '''A counter.'''\n\n    def add(self, n):\n        '''Add n.'''\n        pass\n"
TESTS = '''\
import pytest
import snippet_3 as module_0
import math as module_1


def test_case_0():
    counter_0 = module_0.Counter(3)
    var_0 = counter_0.add(2)
    assert var_0 == 5
    assert counter_0.count == 5
    var_1 = counter_0.add(1)
    assert var_1 == 6


def test_case_1():
    counter_0 = module_0.Counter(0)
    assert counter_0.count == 0
    var_0 = counter_0.add(4)
    assert var_0 == 4


def test_case_2():
    counter_0 = module_0.Counter(1)
    with pytest.raises(ValueError):
        counter_0.add(-5)


@pytest.mark.xfail(strict=True)
def test_case_3():
    counter_0 = module_0.Counter(1)
    counter_0.add('x')


def test_case_4():
    assert module_1.pi > 3
    assert module_0.Counter(7).count == 7
'''
GATE = {
    "test_case_0": {"validity": VALID_BEHAVIOURAL, "ref_exc_type": None, "trivial": False},
    "test_case_1": {"validity": VALID_BEHAVIOURAL, "ref_exc_type": None, "trivial": False},
    "test_case_2": {"validity": VALID_EXCEPTION_ORACLE, "ref_exc_type": "ValueError", "trivial": False},
    "test_case_3": {"validity": VALID_EXCEPTION_ORACLE, "ref_exc_type": "builtins.TypeError", "trivial": False},
    "test_case_4": {"validity": VALID_BEHAVIOURAL, "ref_exc_type": None, "trivial": False},
}
WRONG = "```python\n" + REFERENCE.replace("self.count += n", "self.count += n + 1") + "```"
CRASH = REFERENCE.replace("self.count += n\n", "raise RuntimeError('crash')\n")
NO_CLASS = "I cannot help with that."


@pytest.fixture
def cfg(tmp_path):
    corpus = tmp_path / "corpus.jsonl.gz"
    with gzip.open(corpus, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "task_id": "RealClassEval/csn/snippet_3", "split": "csn", "snippet_id": "snippet_3",
            "snippet_num": 3, "class_short_name": "Counter", "skeleton_full_docstr": SKELETON,
            "skeleton_partial_docstr": None, "skeleton_no_docstr": None,
            "reference_code": REFERENCE, "test_code": TESTS}) + "\n")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"tasks": [{
        "task_id": "RealClassEval/csn/snippet_3", "split": "csn", "status": "accepted",
        "task_index": 0, "tests": GATE, "scenarios": {"excluded": {}}}]}), encoding="utf-8")
    return Config.model_validate({
        "project": {"output_dir": str(tmp_path / "out"), "seed": 42},
        "benchmark": {"name": "realclasseval", "data_path": str(corpus), "manifest_path": str(manifest)},
        "llm": {"models": [{"id": m} for m in MODELS]},
        "execution": {"timeout_s": 30, "cpu_workers": 2},
        "rq2": {"template_relations": ["r1"], "include_control_resample": False, "n_completions": 2},
    })


@pytest.fixture
def bench(cfg):
    from meta_real_eval.benchmarks import get_benchmark
    return get_benchmark(cfg)


@pytest.fixture
def task(bench):
    return bench.load_tasks()[0]


def _rq2(cfg, task, completions):
    """Real RQ2 generate output, then RQ2's own evaluator -- the v3 baseline."""
    from meta_real_eval.rq2.evaluator import evaluate_task
    gen = task_dir(cfg, "rq2", task.label, phase="generate")
    gen.mkdir(parents=True)
    (gen / "completions.json").write_text(json.dumps(completions))
    evaluate_task(task, cfg)
    return json.loads((task_dir(cfg, "rq2", task.label, phase="evaluate") / "pass_rates.json").read_text())


COMPLETIONS = {
    "original": {"m_a": [REFERENCE, REFERENCE], "m_b": [WRONG, REFERENCE], "m_c": [CRASH, NO_CLASS]},
    "r1": {"m_a": [REFERENCE, WRONG], "m_b": [WRONG, WRONG], "m_c": [REFERENCE, CRASH]},
}


def test_end_to_end_level_zero_reproduces_rq2_and_degraded_levels_behave(cfg, bench, task):
    pass_rates = _rq2(cfg, task, COMPLETIONS)
    tier2.run_degrade_tier2(task, cfg, bench)
    out = task_dir(cfg, "rq4", task.label, phase="degrade")
    rec = json.loads((out / tier2.DEGRADE_FILE).read_text())

    assert is_done(out) and rec["executed"]
    assert rec["eligibility"]["n_units"] == 8 and rec["eligibility"]["n_valid_tests"] == 5
    assert all(e["eligible"] for d in rec["eligibility"]["designs"].values() for e in d.values())
    check = rec["baseline_check"]
    assert check["ok"] and check["n_completions"] == 12 and check["n_mismatch_first_pass"] == 0

    units = rec["designs"]["units"]["levels"]
    for rel, by_model in pass_rates.items():                     # level 0.0 == RQ2 v3, cell by cell
        for m, c in by_model.items():
            assert units["0.0"]["cells"][rel][m]["primary_scores"] == c["primary_scores"]
            assert units["0.0"]["cells"][rel][m]["per_completion"] == c["per_completion"]
    assert [units[k]["n_remaining"] for k in ("0.0", "0.2", "0.5", "0.8")] == [8, 6, 4, 1]
    for k, lv in units.items():
        assert not lv["missing"]
        cell = lv["cells"]["original"]
        assert cell["m_a"]["primary_scores"] == [1.0, 1.0]          # the reference, at every level
        assert cell["m_c"]["primary_scores"][1] == 0.0              # no class: 0 at every level
    assert rec["designs"]["units"]["monotonicity"]["n_violations"] == 0
    tests = rec["designs"]["tests"]["levels"]
    assert [tests[k]["n_remaining"] for k in ("0.0", "0.2", "0.5", "0.8")] == [5, 4, 2, 1]
    assert tests["0.0"]["cells"] == units["0.0"]["cells"]           # shared intact level
    assert rec["designs"]["tests"]["monotonicity"]["n_violations"] == 0
    for score in tier2.SCORES:
        assert set(units["0.5"]["by_score"][score]["scores"]) == {"original", "r1"}


def _result(primary, passed=None):
    return SuiteResult(outcomes={"t": TestOutcome("t", "ordinary_pass" if primary == 1.0 else "ordinary_fail")},
                       scores={"primary": primary, "passed_all": float(primary == 1.0 if passed is None else passed)})


def test_the_baseline_check_reruns_a_mismatch_alone_and_fails_if_it_persists(cfg, task, monkeypatch):
    pass_rates = {"original": {"m_a": {"n": 2, "primary_scores": [1.0, 0.5], "per_completion": [True, False],
                                       "mean_primary": 0.75, "pass@1": 0.5}}}
    completions = {"original": {"m_a": ["c0", "c1"]}}
    for rerun_gives, ok in ((0.5, True), (0.0, False)):
        scored = {("original", "m_a"): ([_result(1.0), _result(0.0)], [])}
        monkeypatch.setattr(tier2, "_score_under_suite", lambda *a, v=rerun_gives: _result(v))
        check = tier2.baseline_check(task, cfg, completions, scored, pass_rates)
        assert check["n_mismatch_first_pass"] == 1 and check["rerun_alone"] == [("original", "m_a", 1)]
        assert check["ok"] is ok and len(check["mismatches"]) == (0 if ok else 1)


def test_a_failed_baseline_check_runs_no_degraded_level(cfg, bench, task, monkeypatch):
    pass_rates = _rq2(cfg, task, COMPLETIONS)
    pr = task_dir(cfg, "rq2", task.label, phase="evaluate") / "pass_rates.json"
    pass_rates["original"]["m_a"]["primary_scores"] = [0.5, 1.0]        # RQ2 "said" something else
    pr.write_text(json.dumps(pass_rates))
    suites = []
    real = tier2.score_cells
    monkeypatch.setattr(tier2, "score_cells", lambda t, c, comp, s: suites.append(s) or real(t, c, comp, s))
    tier2.run_degrade_tier2(task, cfg, bench)
    out = task_dir(cfg, "rq4", task.label, phase="degrade")
    rec = json.loads((out / tier2.DEGRADE_FILE).read_text())
    check = rec["baseline_check"]
    assert suites == [None] and not check["ok"] and not rec["executed"] and "designs" not in rec
    assert check["rerun_alone"] == [["original", "m_a", 0]]           # re-run alone, still 1.0 != 0.5
    assert [(x["relation"], x["model"], x["index"]) for x in check["mismatches"]] == [("original", "m_a", 0)]
    assert is_done(out)                                               # excluded, not retried forever


class _Stub:
    """A bench whose levels run out of units at 0.8, with every rule forced eligible."""
    def __init__(self, n_units):
        self.n = n_units

    def _gated(self, task):
        return [GatedTest(f"t{i}", VALID_BEHAVIOURAL) for i in range(5)]

    def oracle_units(self, task):
        return []

    def degrade_units(self, task, level, seed):
        from meta_real_eval.benchmarks.oracle_units import n_removed
        k = n_removed(self.n, level)
        return DegradedSuite(level=level), {"n_units": self.n, "n_removed": k,
                                            "n_remaining": self.n - k, "removed": [f"u{i}" for i in range(k)]}


def test_a_level_with_no_unit_left_is_missing_and_never_executed(cfg, task, monkeypatch):
    out = task_dir(cfg, "rq2", task.label, phase="generate")
    out.mkdir(parents=True)
    (out / "completions.json").write_text(json.dumps({"original": {m: ["x"] for m in MODELS}}))
    ev = task_dir(cfg, "rq2", task.label, phase="evaluate")
    ev.mkdir(parents=True)
    (ev / "pass_rates.json").write_text(json.dumps({"original": {m: {"n": 1} for m in MODELS}}))
    forced = {"n_units": 4, "n_valid_tests": 5, "designs": {
        "units": {k: {"eligible": True, "reasons": []} for k in tier2.SCORES},
        "tests": {k: {"eligible": False, "reasons": ["x"]} for k in tier2.SCORES}}}
    monkeypatch.setattr(tier2, "eligibility", lambda *a: forced)
    monkeypatch.setattr(tier2, "_warm_up", lambda *a: None)
    monkeypatch.setattr(tier2, "baseline_check", lambda *a: {"ok": True, "n_completions": 3})
    levels_run = []

    def fake_score(t, c, comp, suite):
        levels_run.append(None if suite is None else suite.level)
        return {("original", m): ([_result(v)], []) for m, v in zip(MODELS, (1.0, 0.5, 0.0))}
    monkeypatch.setattr(tier2, "score_cells", fake_score)
    tier2.run_degrade_tier2(task, cfg, _Stub(4))
    rec = json.loads((task_dir(cfg, "rq4", task.label, phase="degrade") / tier2.DEGRADE_FILE).read_text())
    lv = rec["designs"]["units"]["levels"]
    assert levels_run == [None, 0.2, 0.5]                     # 4 units: none left at 0.8
    assert lv["0.8"]["missing"] and "by_score" not in lv["0.8"] and "cells" not in lv["0.8"]


def test_eligibility_rules(cfg, bench, task):
    tied = {"original": {m: {"n": 2, "mean_primary": 0.5, "pass@1": 0.0} for m in MODELS}}
    e = tier2.eligibility(task, bench, cfg, tied)
    assert e["min_required"] == 5
    assert all(not v["eligible"] for d in e["designs"].values() for v in d.values())
    split = {"original": {m: {"n": 2, "mean_primary": s, "pass@1": 0.0}
                          for m, s in zip(MODELS, (1.0, 0.5, 0.5))}}
    e = tier2.eligibility(task, bench, cfg, split)
    assert e["designs"]["units"]["mean_primary"]["eligible"]
    assert not e["designs"]["units"]["pass@1"]["eligible"]          # pass@1 ties every model at 0


def test_tier1_keeps_its_own_rq4_path():
    from meta_real_eval.benchmarks.humaneval import HumanEvalBenchmark
    from meta_real_eval.rq4.runner import _tier2
    assert not _tier2(HumanEvalBenchmark())


def test_analysis_counts_only_eligible_checked_tasks(cfg, bench, task):
    """Synthetic per-task files: one eligible task, one that failed the check,
    one ineligible -- only the first enters H1b."""
    def level(tau, scores):
        return {"missing": False, "by_score": {k: {"mean_tau_b": tau, "tau_b_by_arm": {"control": 1.0},
                                                   "scores": {"original": scores}} for k in tier2.SCORES},
                "cells": {}}
    elig = lambda ok, n=2: {"designs": {d: {k: {"eligible": ok, "reasons": [] if ok else
                                                [f"fewer than 5 oracle units ({n})"]}
                                            for k in tier2.SCORES} for d in ("units", "tests")}}
    good = {"executed": True, "eligibility": elig(True),
            "baseline_check": {"ok": True, "n_completions": 12, "rerun_alone": []},
            "designs": {"units": {"levels": {"0.0": level(1.0, {"m_a": 1, "m_b": .5, "m_c": 0}),
                                             "0.2": level(1 / 3, {"m_a": 1, "m_b": .5, "m_c": 0}),
                                             "0.5": level(1 / 3, {"m_a": 1, "m_b": 1, "m_c": 1}),
                                             "0.8": level(-1.0, {"m_a": 0, "m_b": .5, "m_c": 1})},
                                  "monotonicity": {"n_violations": 0}}}}
    failed = {**good, "baseline_check": {"ok": False, "n_completions": 12, "rerun_alone": [["o", "m", 0]]}}
    for label, rec in (("RCE_csn_snippet_3", good), ("T_failed", failed),
                       ("T_small", {"eligibility": elig(False, 2)}),
                       ("T_small2", {"eligibility": elig(False, 4)})):     # different counts, one reason
        d = task_dir(cfg, "rq4", label, phase="degrade")
        d.mkdir(parents=True)
        (d / tier2.DEGRADE_FILE).write_text(json.dumps(rec))
    tasks = [task] + [type(task)(**{**task.__dict__, "label": n}) for n in ("T_failed", "T_small", "T_small2")]
    s = tier2.analyze_tier2(cfg, tasks)
    r = s["designs"]["units"]["mean_primary"]
    assert s["baseline_check"]["n_failed"] == 1 and s["baseline_check"]["failed_tasks"] == ["T_failed"]
    assert r["n_eligible"] == 1 and r["eligible_tasks"] == ["RCE_csn_snippet_3"]
    assert r["ineligible_reasons"] == {"baseline check failed": 1, "fewer than 5 oracle units": 2}
    assert r["h1b_pages_l"]["n_blocks"] == 1
    assert r["ranking_collapse"] == {"0.2": 0, "0.5": 1, "0.8": 0}
    assert not r["h1a"]["available"]
    assert "PRIMARY" in tier2.report(s)


def test_augment_needs_the_calibrated_threshold_builds_on_the_degraded_suite_and_reuses_without_ca(
        cfg, bench, task, monkeypatch):
    cfg.rq4.degradation_levels = [0.0, 0.5]                  # keeps the test short; rule 1 needs 2 units
    with pytest.raises(SystemExit, match="calibrated"):
        tier2.run_augment_tier2(task, cfg, bench)
    cfg.rq3.divergence_threshold = 0.1
    _rq2(cfg, task, COMPLETIONS)
    tier2.run_degrade_tier2(task, cfg, bench)
    rq3 = task_dir(cfg, "rq3", task.label, phase="execute")
    rq3.mkdir(parents=True)
    (rq3 / "divergence.json").write_text(json.dumps({"pairwise_disagreement_rate": 0.4}))
    deg = json.loads((task_dir(cfg, "rq4", task.label, phase="degrade") / tier2.DEGRADE_FILE).read_text())

    ca = "def test_ca_0():\n    counter_0 = module_0.Counter(2)\n    assert counter_0.add(3) == 5\n"
    monkeypatch.setattr(type(bench), "consistency_suite", lambda self, t, d, th: (ca, 1))
    tier2.run_augment_tier2(task, cfg, bench)
    out = task_dir(cfg, "rq4", task.label, phase="augment")
    rec = json.loads((out / tier2.AUGMENT_FILE).read_text())
    assert rec["has_consistency_assertions"] and rec["n_consistency_assertions"] == 1
    for design in ("units", "tests"):
        lv = rec["designs"][design]["levels"]
        assert lv["0.0"]["cells"]["original"]["m_a"]["primary_scores"] == [1.0, 1.0]   # reference
        wrong_deg = deg["designs"][design]["levels"]["0.5"]["cells"]["original"]["m_b"]["primary_scores"][0]
        assert lv["0.5"]["cells"]["original"]["m_b"]["primary_scores"][0] < wrong_deg or wrong_deg == 0
        assert rec["designs"][design]["monotonicity_vs_degraded"]["n_violations"] == 0
    assert rec["designs"]["tests"]["levels"]["0.0"]["cells"] == rec["designs"]["units"]["levels"]["0.0"]["cells"]

    monkeypatch.setattr(type(bench), "consistency_suite", lambda self, t, d, th: ("", 0))
    tier2.run_augment_tier2(task, cfg, bench, force=True)
    rec = json.loads((out / tier2.AUGMENT_FILE).read_text())
    lv = rec["designs"]["units"]["levels"]
    assert not rec["has_consistency_assertions"] and all(v["reused_degraded"] for v in lv.values())
    assert lv["0.5"]["cells"] == deg["designs"]["units"]["levels"]["0.5"]["cells"]


def test_h1a_is_estimated_on_tasks_that_got_assertions_and_pooled_beside_it(cfg):
    """A task without assertions reuses its degraded results (recovery exactly 0), so it
    can only dilute H1a: the primary population is the tasks with >= 1 assertion."""
    from types import SimpleNamespace
    intact, wrecked = {"m_a": 1, "m_b": .5, "m_c": 0}, {"m_a": 0, "m_b": .5, "m_c": 1}

    def level(scores):
        return {"missing": False, "by_score": {k: {"mean_tau_b": 1.0, "tau_b_by_arm": {"control": 1.0},
                                                   "scores": {"original": scores}} for k in tier2.SCORES},
                "cells": {}}
    levels = ("0.0", "0.2", "0.5", "0.8")
    elig = {"designs": {d: {k: {"eligible": True, "reasons": []} for k in tier2.SCORES} for d in ("units", "tests")}}
    degraded = {k: level(intact if k == "0.0" else wrecked) for k in levels}
    deg_rec = {"executed": True, "eligibility": elig, "baseline_check": {"ok": True, "n_completions": 1, "rerun_alone": []},
               "designs": {"units": {"levels": degraded, "monotonicity": {"n_violations": 0}}}}
    restored = {k: level(intact) for k in levels}                      # the assertions restore the ranking
    mono = {"n_violations": 0}
    aug = lambda ca, lv: {"has_consistency_assertions": ca,
                          "designs": {"units": {"levels": lv, "monotonicity_vs_degraded": mono}}}
    for label, a in (("A1", aug(True, restored)), ("A2", aug(True, restored)), ("B", aug(False, degraded))):
        for ph, fn, rec in (("degrade", tier2.DEGRADE_FILE, deg_rec), ("augment", tier2.AUGMENT_FILE, a)):
            d = task_dir(cfg, "rq4", label, phase=ph)
            d.mkdir(parents=True)
            (d / fn).write_text(json.dumps(rec))
    s = tier2.analyze_tier2(cfg, [SimpleNamespace(label=n) for n in ("A1", "A2", "B")])
    r = s["designs"]["units"]["mean_primary"]
    assert r["h1a"]["n_tasks"] == 2 and r["h1a"]["n_with_consistency_assertions"] == 2
    assert r["h1a"]["by_level"]["0.2"]["mean_recovery"] == pytest.approx(2.0)      # rho -1 -> +1
    assert r["h1a_all_eligible"]["n_tasks"] == 3
    assert r["h1a_all_eligible"]["by_level"]["0.2"]["mean_recovery"] == pytest.approx(4 / 3)
    text = tier2.report(s)
    assert "H1a (tasks with assertions): 2 task(s)" in text and "all eligible tasks): 3 task(s)" in text
    # nobody got an assertion: the primary population is empty, and says so
    for label in ("A1", "A2"):
        (task_dir(cfg, "rq4", label, phase="augment") / tier2.AUGMENT_FILE).write_text(
            json.dumps(aug(False, degraded)))
    r = tier2.analyze_tier2(cfg, [SimpleNamespace(label=n) for n in ("A1", "A2", "B")])["designs"]["units"]["mean_primary"]
    assert not r["h1a"]["available"] and "no eligible task received" in r["h1a"]["note"]
