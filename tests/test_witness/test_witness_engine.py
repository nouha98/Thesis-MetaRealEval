"""Gate G2 fixtures for the witness engine, run through the real scenario runner."""

import pytest

from meta_real_eval.benchmarks.contracts import draft_contract
from meta_real_eval.benchmarks.witness import WitnessSettings, prepare_task, search_group
from meta_real_eval.core import exec_policy
from meta_real_eval.core.exec_policy import ExecPolicy

from .fixtures import DEPENDENCY_SCAN, MUTANTS, make_task


@pytest.fixture(scope="module")
def ctx():
    ExecPolicy(kill_process_tree=True, isolate_home=True).activate()
    task = make_task()
    c = draft_contract(task, DEPENDENCY_SCAN)
    yield prepare_task(task, c, WitnessSettings(pool_size=12, max_calls=4, timeout_s=2.0,
                                                mutant_budget_s=120, shrink_rounds=4))
    exec_policy.deactivate()


def test_reference_baseline_and_domains(ctx):
    assert ctx["support"]["supported"]
    p = {e["scenario"]["scenario_id"]: e for e in ctx["pools"]["p"]["entries"]}
    assert p["test_case_0"]["domain"] == "valid"
    # the reference raises an undocumented ZeroDivisionError: domain-uncertain, not "invalid"
    assert p["test_case_3"]["domain"] == "domain_uncertain" and p["test_case_3"]["uncertain_step"] == 1
    assert p["test_case_1"]["scenario"]["api_flags"][-1] is False        # private attribute observation


def test_state_dependent_fault_gives_a_replayed_api_witness(ctx):
    r = search_group(ctx, "g", MUTANTS["state_fault"])
    assert (r["outcome"], r["level"], r["kind"], r["domain"]) == ("distinguished", "api_visible", "api_value", "valid")
    assert r["replay"]["confirmed"] and r["origin"] == "generated"
    assert len(r["witness"]["steps"]) <= r["witness"]["original_steps"]


def test_private_state_difference_is_not_api_visible(ctx):
    r = search_group(ctx, "g", MUTANTS["private_only"])
    assert (r["outcome"], r["level"]) == ("distinguished", "private_state_only")


def test_mutant_only_exception_is_a_witness(ctx):
    r = search_group(ctx, "g", MUTANTS["mutant_exception"])
    assert (r["outcome"], r["kind"], r["domain"]) == ("distinguished", "api_exception", "valid")


def test_difference_only_where_reference_raises_undocumented_is_domain_uncertain(ctx):
    r = search_group(ctx, "g", MUTANTS["uncertain_only"])
    assert (r["outcome"], r["domain"]) == ("distinguished", "domain_uncertain")


def test_nontermination(ctx):
    r = search_group(ctx, "g", MUTANTS["nontermination"])
    assert (r["outcome"], r["kind"], r["domain"]) == ("distinguished", "nontermination", "valid")


def test_no_witness_is_unresolved_never_equivalent(ctx):
    r = search_group(ctx, "g", MUTANTS["equivalent"])
    assert r["outcome"] == "unresolved" and "not an equivalence certificate" in r["reason"]


def test_invalid_artifacts(ctx):
    assert search_group(ctx, "g", MUTANTS["invalid"])["outcome"] == "invalid_artifact"
    assert search_group(ctx, "g", None)["outcome"] == "invalid_artifact"


def test_unsupported_task_is_reported_per_group():
    task = make_task()
    c = draft_contract(task, {"tasks": {}})
    ctx = prepare_task(task, c, WitnessSettings(pool_size=4))
    r = search_group(ctx, "g", MUTANTS["state_fault"])
    assert r["outcome"] == "unsupported" and "dependency scan" in r["reason"]
