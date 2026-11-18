"""Stage 2b coupling: the pure maths (oracles/coupling.py), solution groups, and the observable-value
filter of the perturbed-P pool (benchmarks/detection.py)."""

import random
from itertools import combinations

import pytest

from meta_real_eval.benchmarks.detection import _builtin_only
from meta_real_eval.oracles import coupling as C
from meta_real_eval.oracles.solution_groups import build_solution_groups, digest

IDX = {f"t{i}": i - 1 for i in range(1, 5)}


def b(*ids):
    return C.bits(ids, IDX)


def test_chen_fig_8a():
    d = b("t1")
    assert C.pc(b("t1"), d) == 1.0                 # g1: perfectly coupled
    assert C.pc(b("t1", "t2"), d) == 0.5           # g2
    assert C.pc(b("t3"), d) == 0.0                 # g3: decoupled
    assert C.pc(0, d) is None                      # g4: unsatisfiable, undefined (never 0)


@pytest.mark.parametrize("seed", range(5))
def test_exact_expectations_equal_brute_force(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 7)
    goals = [rng.getrandbits(8) | 1 for _ in range(n)]
    d = rng.getrandbits(8) | 1
    for k in range(1, n + 1):
        subs = list(combinations(goals, k))
        pcs = lambda s: [C.pc(g, d) for g in s]  # noqa: E731
        assert C.expected_max(pcs(goals), k) == pytest.approx(sum(max(pcs(s)) for s in subs) / len(subs))
        assert C.expected_any([x == 1.0 for x in pcs(goals)], k) == pytest.approx(
            sum(any(x == 1.0 for x in pcs(s)) for s in subs) / len(subs))
        cov = lambda s: ((d & (sum(s) and __import__("functools").reduce(lambda a, c: a | c, s))).bit_count()  # noqa: E731
                         / d.bit_count())
        assert C.expected_coverage(goals, d, k) == pytest.approx(sum(cov(s) for s in subs) / len(subs))


def test_permutation_keeps_counts_per_stratum():
    rng = random.Random(1)
    strata = [[0, 1, 2], [3, 4, 5, 6]]
    d = 0b0100101                              # 2 in the first stratum, 1 in the second
    for _ in range(50):
        p = C.permuted(d, strata, rng)
        assert sum((p >> i) & 1 for i in strata[0]) == 2 and sum((p >> i) & 1 for i in strata[1]) == 1


def _task(mutants, solutions, n_tests=10, **kw):
    tests = {f"x{i}": ("p" if i < 3 else "gen") for i in range(n_tests)}
    return C.task_analysis("T", tests, mutants, solutions, B=50, seed=1, **kw)


def M(i, source, detect, models=()):
    return {"id": f"m{i}", "source": source, "models": list(models), "detect": set(detect)}


def S(i, detect, models=("A",), invalid=False):
    return {"id": f"s{i}", "models": list(models), "detect": set(detect), "invalid": invalid}


def test_a_mutant_killed_by_every_test_has_zero_lift():
    every = [f"x{i}" for i in range(10)]
    r = _task([M(1, "operator", every), M(2, "llm_whole", every, ["B"])], [S(1, ["x0", "x5"])])
    assert r["excluded"] is None
    for src in C.SOURCES:
        assert r["means"][src]["pc"] == pytest.approx(0.2) and r["means"][src]["lift"] == pytest.approx(0.0)


def test_identical_fault_coupling_and_strict():
    r = _task([M(1, "operator", ["x9"]), M(2, "llm_whole", ["x4", "x5"], ["B"])], [S(1, ["x4", "x5"])])
    assert r["means"]["llm_whole"]["pc"] == 1.0 and r["means"]["llm_whole"]["strict"] == 1.0
    assert r["means"]["operator"]["pc"] == 0.0 and r["delta_lift"] > 0


def test_deduplication_makes_duplicates_irrelevant():
    base = [M(1, "operator", ["x1"]), M(2, "operator", ["x2", "x3"]), M(3, "llm_whole", ["x1", "x2"], ["B"])]
    sols = [S(1, ["x1", "x2"]), S(2, ["x1", "x2"], ["C"])]
    r1 = _task(base, sols)
    r2 = _task(base + [M(9, "operator", ["x1"]), M(8, "llm_whole", ["x1", "x2"], ["B"])], sols)
    assert r1["means"] == r2["means"] and r1["n_fault_classes"] == 1


def test_mixed_groups_never_enter_a_source():
    r = _task([M(1, "mixed", ["x1"]), M(2, "operator", ["x2"]), M(3, "llm_whole", ["x3"], ["B"])], [S(1, ["x1"])])
    assert r["goals"] == {"operator": 1, "llm_whole": 1} and r["mutants"]["mixed"]["detected"] == 1


def test_cross_model_rule_and_exclusion_order():
    op, llm_a = M(1, "operator", ["x1"]), M(2, "llm_whole", ["x1"], ["A"])
    assert _task([op, llm_a], [S(1, ["x1"], ["A"])])["excluded"] == "no_cross_model_llm"
    assert _task([op, llm_a], [S(1, ["x1"], ["A"])], counts_only=True)["excluded"] == "no_cross_model_llm"
    assert C.task_analysis("T", {}, [op], [S(1, [])])["excluded"] == "no_valid_pool"
    assert _task([op, llm_a], [S(1, [])])["excluded"] == "no_near_miss_fault"            # undetected on pool
    every = [f"x{i}" for i in range(10)]
    assert _task([op, llm_a], [S(1, every)])["excluded"] == "no_near_miss_fault"         # total failure
    assert _task([op, llm_a], [S(1, ["x1"], invalid=True)])["excluded"] == "no_near_miss_fault"
    assert _task([llm_a], [S(1, ["x1"], ["B"])])["excluded"] == "no_detected_operator"
    assert _task([op], [S(1, ["x1"], ["B"])])["excluded"] == "no_detected_llm"


def test_cross_model_rule_applies_before_deduplication():
    """Section 9.2: an own-model group with the same K must not make an identical cross-model
    group ineligible (it would if the rule were applied to deduplicated goals)."""
    op = M(1, "operator", ["x1", "x2"])
    own, cross = M(2, "llm_whole", ["x1"], ["A"]), M(3, "llm_whole", ["x1"], ["B"])
    sols = [S(1, ["x1"], ["A"])]
    for kw in ({}, {"counts_only": True}):
        assert _task([op, own, cross], sols, **kw)["excluded"] is None
    with_own, without = _task([op, own, cross], sols), _task([op, cross], sols)
    assert with_own["means"] == without["means"]
    assert with_own["classes"][0]["llm_same_model_max_pc"] == 1.0
    assert without["classes"][0]["llm_same_model_max_pc"] is None


def test_detection_constants_match_the_frozen_spec():
    """The frozen SPEC states detection levels and run count; detection.py must use exactly those,
    otherwise the code could drift without changing spec_sha256."""
    import inspect
    from meta_real_eval.benchmarks import detection as D
    assert D.DETECT_LEVELS == {tuple(x) for x in C.SPEC["primary_pool"]["detect_levels"]}
    for fn in (D.primary_cells, D.perturbed_cells):
        assert inspect.signature(fn).parameters["runs"].default == C.SPEC["primary_pool"]["runs"]


def test_counts_only_computes_no_coupling_value():
    r = _task([M(1, "operator", ["x1"]), M(2, "llm_whole", ["x1"], ["B"])], [S(1, ["x1"])], counts_only=True)
    assert r["excluded"] is None and r["n_contributing"] == 1
    assert "means" not in r and "delta_lift" not in r and "classes" not in r


def test_null_is_reproducible():
    args = ([M(1, "operator", ["x1", "x7"]), M(2, "llm_whole", ["x2"], ["B"])], [S(1, ["x1", "x2", "x3"])])
    assert _task(*args)["means"] == _task(*args)["means"]


def test_observable_filter_keeps_builtins_and_exception_types_only():
    assert _builtin_only("VALUE:builtins.int:0x1.0p+0")
    assert _builtin_only("VALUE:builtins.list:[VALUE:builtins.str:'a',VALUE:builtins.int:1]")
    assert _builtin_only("EXC:builtins.ValueError")
    assert not _builtin_only("VALUE:snippet_1.Account:{balance:VALUE:builtins.int:1}")
    assert not _builtin_only("VALUE:builtins.list:[VALUE:snippet_1.Item:{}]")
    assert not _builtin_only("OPAQUE<Account()>")


def test_solution_groups_merge_identical_programs_and_keep_provenance():
    comps = {"original": {"A": ["x = 1", "x = 1\n"], "B": ["x = 2"]}, "control_resample": {"A": ['"""doc"""\nx = 1']}}
    rates = {"original": {"A": {"per_completion": [True, True]}, "B": {"per_completion": [False]}}}
    g = build_solution_groups("T", comps, rates, lambda c: c)
    assert len(g) == 2
    big = max(g.values(), key=lambda v: len(v["members"]))
    assert len(big["members"]) == 3 and big["models"] == ["A"]                 # docstring-insensitive
    assert {m["stored_p_pass"] for m in big["members"]} == {True, None}       # control has no stored verdict here
    assert digest(g) == digest(build_solution_groups("T", comps, rates, lambda c: c))
