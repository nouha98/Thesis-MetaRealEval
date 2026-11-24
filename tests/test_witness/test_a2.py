"""A2 construction (oracles.regression) and admission/control (oracles.admission) on the G2 fixture class,
through the real scenario runner and real pytest."""

import pytest

from meta_real_eval.benchmarks.contracts import draft_contract
from meta_real_eval.benchmarks.strategies import generate_scenarios
from meta_real_eval.benchmarks.witness import WitnessSettings, _materialise
from meta_real_eval.core import exec_policy
from meta_real_eval.core.exec_policy import ExecPolicy
from meta_real_eval.oracles.admission import admit, private_rename, run_tests, validate_control
from meta_real_eval.oracles.regression import A2Settings, a2_base_seed, a2_pool, build_a2, emit, reference_entries

from .fixtures import DEPENDENCY_SCAN, MODULE, MUTANTS, REFERENCE, make_task

SEED = 20261112
A2 = A2Settings(pool_size=30, max_calls=4, max_tests=5, timeout_s=2.0)
WS = WitnessSettings(pool_size=12, max_calls=4)


@pytest.fixture(scope="module")
def built():
    ExecPolicy(kill_process_tree=True, isolate_home=True).activate()
    task = make_task()
    c = draft_contract(task, DEPENDENCY_SCAN)
    disc = {"g_state": MUTANTS["state_fault"], "g_exc": MUTANTS["mutant_exception"],
            "g_private": MUTANTS["private_only"], "g_invalid": None}
    yield task, c, build_a2(task.label, MODULE, REFERENCE, c, disc, A2, SEED, WS)
    exec_policy.deactivate()


def test_pool_is_disjoint_from_the_witness_pool(built):
    _, c, _ = built
    assert a2_base_seed(SEED) != SEED
    witness = {tuple(st["src"] for st in _materialise(s, c)["steps"])
               for s in generate_scenarios(c, WS.pool_size, SEED, WS.max_calls)}
    pool, _ = a2_pool(c, A2, SEED, WS.pool_size, WS.max_calls)
    assert pool and not ({tuple(st["src"] for st in s["steps"]) for s in pool} & witness)


def test_tests_kill_api_faults_only(built):
    _, _, b = built
    assert {"g_state", "g_exc"} <= set(b["covered_by_tests"])
    assert "g_private" not in b["killed_by_pool"]                   # private state is never asserted
    assert 0 < len(b["tests"]) <= A2.max_tests and all(t["kills"] and t["expected"] for t in b["tests"])
    assert all(k.startswith("api:") for t in b["tests"] for k in t["expected"])


def test_emitted_tests_pass_on_reference_and_fail_on_the_fault(built):
    task, c, b = built
    code = emit(task.task_id, MODULE, c, b["tests"])
    names = [t["name"] for t in b["tests"]]
    assert set(run_tests(MODULE, REFERENCE, code, names, 30).values()) == {"ordinary_pass"}
    assert "ordinary_fail" in run_tests(MODULE, MUTANTS["state_fault"], code, names, 30).values()
    assert "repr(" not in code and "._" not in code.replace("_h_", "").replace("._run", "")


def test_admission_and_validated_control(built):
    task, c, b = built
    code = emit(task.task_id, MODULE, c, b["tests"])
    names = [t["name"] for t in b["tests"]]
    adm = admit(MODULE, REFERENCE, code, names, 30, repeats=2)
    assert all(a["admitted"] for a in adm.values()), adm
    variant = private_rename(REFERENCE, "Counter")
    assert "_history_ctl" in variant and "self._history " not in variant
    entries = reference_entries(MODULE, REFERENCE, c, [{"scenario_id": t["scenario_id"], "steps": t["steps"],
                                                         "api_flags": t["api_flags"]} for t in b["tests"]],
                                A2.witness_settings())
    assert validate_control(MODULE, variant, c, entries, A2.witness_settings())["valid"]
    assert set(run_tests(MODULE, variant, code, names, 30).values()) == {"ordinary_pass"}


def test_output_levels_restrict_assertions():
    from meta_real_eval.oracles.regression import restrict, spec_diff, step_name  # re-exported from oracles.spec
    v = ["seq", "builtins.list", [["str", "a"]]]
    assert restrict(v, "value") == v and restrict(v, "type") == ["@type", ["seq"]] and restrict(v, "none") == ["@any"]
    exc = ["exc", ["builtins.ValueError", "builtins.Exception"]]
    assert all(restrict(exc, lvl) == exc for lvl in ("value", "type", "none"))     # exceptions always asserted
    assert spec_diff(["@type", ["seq"]], ["seq", "builtins.tuple", []]) is None      # other content, same kind
    assert spec_diff(["@type", ["seq"]], ["map", "builtins.dict", []])
    assert spec_diff(["@type", ["number"]], ["float", "0x1p+0"]) is None            # int vs float: same family
    assert spec_diff(["@any"], ["str", "x"]) is None and spec_diff(["@any"], exc) and spec_diff(["@any"], None)
    assert step_name("obj.add(2)", "module_0", "Counter") == "add" and step_name("obj.count", "module_0", "Counter") == "count"
    assert step_name("module_0.Counter(1)", "module_0", "Counter") == "__init__"


def test_type_level_spec_drops_value_only_kills(built):
    """With `add` at type level the state fault (wrong count) is no longer asserted; the exception fault still is."""
    task, c, _ = built
    disc = {"g_state": MUTANTS["state_fault"], "g_exc": MUTANTS["mutant_exception"]}
    levels = {"add": "type", "half": "type", "ratio": "type"}
    b = build_a2(task.label, MODULE, REFERENCE, c, disc, A2, SEED, WS, levels)
    assert "g_exc" in b["covered_by_tests"] and "g_state" not in b["killed_by_pool"]
    assert all(v[0] in ("@type", "@any", "exc", "opaque") for t in b["tests"] for v in t["expected"].values())
    code = emit(task.task_id, MODULE, c, b["tests"])
    names = [t["name"] for t in b["tests"]]
    assert set(run_tests(MODULE, REFERENCE, code, names, 30).values()) == {"ordinary_pass"}
    assert set(run_tests(MODULE, MUTANTS["state_fault"], code, names, 30).values()) == {"ordinary_pass"}


def test_greedy_multi_cover():
    from meta_real_eval.oracles.regression import greedy_select
    entries = [{"scenario": {"scenario_id": f"s{i}", "steps": [{"src": "x"}] * (i + 1), "api_flags": [True] * (i + 1)},
                "ref": {"tokens": {f"api:s{j}": ["v", 1] for j in range(i + 1)}}, "api_mask": [],
                "valid_prefix": i + 1} for i in range(4)]
    kills = {"s0": {"a"}, "s1": {"a", "b"}, "s2": {"a"}, "s3": set()}
    assert [e["scenario"]["scenario_id"] for e in greedy_select(entries, kills, 20, 1)] == ["s1"]
    assert [e["scenario"]["scenario_id"] for e in greedy_select(entries, kills, 20, 2)] == ["s1", "s0"]
    assert [e["scenario"]["scenario_id"] for e in greedy_select(entries, kills, 2, 3)] == ["s1", "s0"]


def test_control_validation_rejects_a_behaviour_change(built):
    task, c, b = built
    entries = reference_entries(MODULE, REFERENCE, c, [{"scenario_id": t["scenario_id"], "steps": t["steps"],
                                                         "api_flags": t["api_flags"]} for t in b["tests"]],
                                A2.witness_settings())
    assert not validate_control(MODULE, MUTANTS["state_fault"], c, entries, A2.witness_settings())["valid"]


def test_protocol_builtin_steps_map_to_their_dunder_level():
    """Regression (audit round 1, post_264): repr(obj) must use the __repr__ level, not the constructor's value."""
    from meta_real_eval.oracles.regression import level_of, step_name
    assert step_name("repr(obj)", "module_0", "User") == "__repr__"
    assert step_name("str(obj)", "module_0", "User") == "__str__"
    assert step_name("len(obj)", "module_0", "User") == "__len__"
    assert level_of({"__repr__": "type"}, step_name("repr(obj)", "module_0", "User")) == "type"
    assert level_of({}, None) == "type" and level_of({}, "__init__") == "value"
