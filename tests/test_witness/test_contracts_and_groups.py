"""Contract drafting (D2), API step classification (D1) and fault groups / frozen split (D4)."""

from meta_real_eval.benchmarks import contracts as C
from meta_real_eval.benchmarks.strategies import generate_scenarios
from meta_real_eval.oracles import fault_groups as FG

from .fixtures import DEPENDENCY_SCAN, MUTANTS, REFERENCE, make_task


def test_draft_contract_reads_annotations_docstrings_and_documented_raises():
    c = C.draft_contract(make_task(), DEPENDENCY_SCAN)
    assert c["review"]["status"] == "draft" and c["support"]["supported"]
    assert c["attributes"] == ["count"]
    assert c["methods"]["add"]["raises_documented"] == ["ValueError"]
    assert c["methods"]["ratio"]["raises_documented"] == []
    (start,) = c["constructor"]["params"]
    assert start["type"] == {"t": "int"} and start["type_source"] == "annotation" and start["has_default"]


def test_unsupported_reasons_are_recorded_not_dropped():
    task = make_task()
    no_scan = C.draft_contract(task, {"tasks": {}})
    assert not no_scan["support"]["supported"] and "dependency scan has no entry" in no_scan["support"]["reasons"]
    side = make_task(reference="import subprocess\n" + REFERENCE)
    assert any("side-effect" in r for r in C.draft_contract(side, DEPENDENCY_SCAN)["support"]["reasons"])


def test_p_literals_ignore_xfail_tests_and_propagate_constants():
    tests = '''import pytest
import m as module_0

def test_a():
    int_0 = 594
    list_0 = [int_0, int_0]
    x = module_0.K(*list_0)
    y = x.f(int_0, k=-3)

@pytest.mark.xfail(strict=True)
def test_b():
    x = module_0.K()
    y = x.f(None)
'''
    lits = C.p_literals(tests, "m", "K")
    assert lits["__init__"]["*"] == [594, 594]
    assert lits["f"][0] == [594] and lits["f"]["k"] == [-3]       # None from the xfail test is ignored


def test_api_flags_exclude_private_and_introspection_steps():
    c = C.draft_contract(make_task(), DEPENDENCY_SCAN)
    steps = [{"src": "module_0.Counter(1)", "target": "c"}, {"src": "c.add(2)", "target": "v"},
             {"src": "c.count", "target": None}, {"src": "c._history", "target": None},
             {"src": "f'{type(c).__module__}'", "target": None}, {"src": "len(c.add(1).__class__.__name__)", "target": None},
             {"src": "unknown_var.add(1)", "target": None}]
    assert C.api_flags(steps, c, "module_0") == [True, True, True, False, False, False, False]


def test_generated_scenarios_are_contract_valid_safe_and_deterministic():
    c = C.draft_contract(make_task(), DEPENDENCY_SCAN)
    a = generate_scenarios(c, 20, 7, 4)
    b = generate_scenarios(c, 20, 7, 4)
    assert [x["steps"] for x in a] == [x["steps"] for x in b] and len(a) == 20
    assert all(all(x["api_flags"]) for x in a)
    assert all(s["steps"][0]["src"].startswith("module_0.Counter(") for s in a)
    assert generate_scenarios(c, 20, 8, 4) != a                   # the seed matters


def test_value_ok_checks_types_and_constraints():
    assert C.value_ok(3, {"t": "int"}) and not C.value_ok(True, {"t": "int"})
    assert C.value_ok([1, 2], {"t": "list", "items": {"t": "int"}}, {"non_empty": True})
    assert not C.value_ok([], {"t": "list", "items": {"t": "int"}}, {"non_empty": True})
    assert not C.value_ok(-1, {"t": "int"}, {"min": 0})


def _records():
    return [{"task": "T", "record_id": "AOR_0", "source": "operator", "code": MUTANTS["state_fault"]},
            {"task": "T", "record_id": "LLM-a-0", "source": "llm_whole", "code": MUTANTS["state_fault"].replace('"""A counter.', '"""Counts.')},
            {"task": "T", "record_id": "LLM-b-1", "source": "llm_whole", "code": MUTANTS["private_only"]},
            {"task": "T", "record_id": "LLM-a-1", "source": "llm_whole", "code": MUTANTS["equivalent"]},
            {"task": "T", "record_id": "ROR_0", "source": "operator", "code": MUTANTS["mutant_exception"]},
            {"task": "U", "record_id": "SDL_0", "source": "operator", "code": MUTANTS["state_fault"]}]


def test_groups_merge_docstring_variants_across_generators_and_keep_provenance():
    groups = FG.build_groups(_records())
    t = groups["T"]
    assert len(t) == 4 and len(groups["U"]) == 1
    merged = next(g for g in t.values() if len(g["members"]) == 2)
    assert merged["source"] == "mixed" and {m["record_id"] for m in merged["members"]} == {"AOR_0", "LLM-a-0"}
    assert all("code_sha256" in m for g in t.values() for m in g["members"])


def test_split_is_frozen_balanced_and_never_splits_a_group():
    groups = FG.build_groups(_records())
    s1, s2 = FG.freeze_split(groups, 1), FG.freeze_split(groups, 1)
    assert s1 == s2
    sides = list(s1["T"].values())
    llm = [s1["T"][g] for g, v in groups["T"].items() if v["source"] == "llm_whole"]
    assert sorted(llm) == ["discovery", "held_out"]                # balanced within the stratum
    assert set(sides) <= {"discovery", "held_out"}


def test_site_mutants_respect_the_frozen_boundary():
    groups = FG.build_groups(_records())
    split = FG.freeze_split(groups, 1)
    disc = next(g for g, s in split["T"].items() if s == "discovery")
    held = next(g for g, s in split["T"].items() if s == "held_out")
    code_of = {FG.group_id("T", FG.normalise_program(r["code"])): r["code"] for r in _records() if r["task"] == "T"}
    assert FG.place_site_mutant("T", code_of[disc], groups, split)["placement"] == "discovery_overlap"
    assert not FG.place_site_mutant("T", code_of[disc], groups, split)["held_out_eligible"]
    assert FG.place_site_mutant("T", code_of[held], groups, split)["placement"] == "joins_held_out_group"
    assert FG.place_site_mutant("T", REFERENCE + "\nX = 1\n", groups, split)["placement"] == "new_site_group"
