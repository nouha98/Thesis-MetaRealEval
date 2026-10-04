"""D4 unit tests: scenario extraction and the fixed pool definition."""

from __future__ import annotations

import math
import random

import pytest

from meta_real_eval.benchmarks.scenarios import (
    EXEC,
    OBSERVE,
    RAISES,
    UnsupportedScenario,
    build_pool,
    extract_scenarios,
    perturb,
)

# Shaped like the real corpus: Assign / Expr / Assert(Compare) /
# With pytest.raises -> Expr, a strict xfail, an environment assertion on a
# second module, and the f-string type-check asserts Pynguin emits.
PYNGUIN_LIKE = '''\
import pytest
import snippet_7 as module_0
import inspect as module_1


def test_case_0():
    counter_0 = module_0.Counter(3)
    assert counter_0.count == 3
    var_0 = counter_0.add(2)
    assert var_0 is None
    assert f'{type(counter_0).__module__}.{type(counter_0).__qualname__}' == 'snippet_7.Counter'


@pytest.mark.xfail(strict=True)
def test_case_1():
    counter_0 = module_0.Counter(3)
    counter_0.add('x')


def test_case_2():
    counter_0 = module_0.Counter(1)
    with pytest.raises(ValueError):
        counter_0.add(-5)
    assert counter_0.count == 1


def test_case_3():
    counter_0 = module_0.Counter(0)
    var_0 = module_1.getcoroutinelocals(counter_0)
    assert module_1.CO_NESTED == 16
'''


def _scenarios():
    return extract_scenarios(PYNGUIN_LIKE, "snippet_7")


def test_header_keeps_imports_but_not_pytest():
    header, _ = _scenarios()
    assert "import snippet_7 as module_0" in header
    assert "import inspect as module_1" in header
    assert "pytest" not in header


def test_one_scenario_per_test_in_source_order():
    _, scs = _scenarios()
    assert [s.scenario_id for s in scs] == ["test_case_0", "test_case_1", "test_case_2", "test_case_3"]


def test_assign_and_expr_become_exec_steps_with_targets():
    _, scs = _scenarios()
    steps = scs[0].steps
    assert steps[0].kind == EXEC and steps[0].target == "counter_0"
    assert steps[0].src == "module_0.Counter(3)"


def test_assert_keeps_left_side_and_drops_the_oracle():
    _, scs = _scenarios()
    observes = [s for s in scs[0].steps if s.kind == OBSERVE]
    assert [o.src for o in observes][:2] == ["counter_0.count", "var_0"]
    # The expected values (3, None, 'snippet_7.Counter') are the oracle and
    # must not appear in any step.
    assert not any("'snippet_7.Counter'" in s.src for s in scs[0].steps)


def test_fstring_type_check_is_observed_not_dropped():
    _, scs = _scenarios()
    observes = [s for s in scs[0].steps if s.kind == OBSERVE]
    assert len(observes) == 3


def test_xfail_flag():
    _, scs = _scenarios()
    assert scs[1].xfail and not scs[0].xfail


def test_pytest_raises_is_kept_with_expected_exc():
    _, scs = _scenarios()
    raises = [s for s in scs[2].steps if s.kind == RAISES]
    assert len(raises) == 1
    assert raises[0].src == "counter_0.add(-5)"
    assert raises[0].expected_exc == "ValueError"
    # ...and the test continues after it.
    assert scs[2].steps[-1].kind == OBSERVE


def test_environment_assertion_is_dropped_and_counted():
    _, scs = _scenarios()
    s3 = scs[3]
    assert s3.env_observations_dropped == 1
    assert not any(s.kind == OBSERVE for s in s3.steps)
    # The call itself is behaviour and is kept.
    assert any("getcoroutinelocals" in s.src for s in s3.steps)


def test_taint_follows_assignments():
    src = (
        "import snippet_1 as module_0\n\n"
        "def test_a():\n"
        "    obj_0 = module_0.C()\n"
        "    var_0 = obj_0.f()\n"
        "    assert var_0 == 1\n"
    )
    _, scs = extract_scenarios(src, "snippet_1")
    assert scs[0].env_observations_dropped == 0


def test_unsupported_statement_raises():
    src = "import snippet_1 as module_0\n\ndef test_a():\n    for i in range(3):\n        module_0.C()\n"
    with pytest.raises(UnsupportedScenario):
        extract_scenarios(src, "snippet_1")


def test_missing_sut_import_raises():
    with pytest.raises(UnsupportedScenario):
        extract_scenarios("def test_a():\n    pass\n", "snippet_1")


def test_extracts_every_test_in_the_real_corpus():
    """The extractor must cover the whole corpus, not just the fixture.

    The only suites it may reject are the 3 vacuous ones Pynguin produced
    without ever importing the class (they build an empty dict/list/tuple
    and stop); the gate excludes those with a reason of their own.
    """
    import gzip
    import json
    from pathlib import Path

    from meta_real_eval.benchmarks.outcomes import static_test_info

    corpus = Path(__file__).resolve().parents[2] / "data" / "realclasseval" / "realclasseval_v1.jsonl.gz"
    if not corpus.exists():
        pytest.skip("RealClassEval corpus not fetched (scripts/fetch_realclasseval.py)")
    rejected: dict[str, int] = {}
    n = 0
    for line in gzip.open(corpus, "rt", encoding="utf-8"):
        row = json.loads(line)
        try:
            _, scs = extract_scenarios(row["test_code"], row["snippet_id"])
            n += len(scs)
        except UnsupportedScenario as e:
            assert "never imports the module under test" in str(e), (row["task_id"], str(e))
            rejected[row["task_id"]] = len(static_test_info(row["test_code"]))
    assert set(rejected) == {
        "RealClassEval/csn/snippet_197",
        "RealClassEval/csn/snippet_301",
        "RealClassEval/post_cut-off/snippet_110",
    }
    assert n + sum(rejected.values()) == 1736


# --- perturbation and pool ---------------------------------------------------

def test_perturb_changes_exactly_one_literal_in_a_non_observe_step():
    _, scs = _scenarios()
    p = perturb(scs[0], random.Random(1), 1)
    assert p is not None and p.perturbed
    changed = [(a, b) for a, b in zip(scs[0].steps, p.steps) if a != b]
    assert len(changed) == 1
    assert changed[0][0].kind != OBSERVE


def test_perturb_returns_none_without_literals():
    src = "import snippet_1 as module_0\n\ndef test_a():\n    obj_0 = module_0.C()\n"
    _, scs = extract_scenarios(src, "snippet_1")
    assert perturb(scs[0], random.Random(0), 1) is None


def test_pool_keeps_every_original_first():
    header, scs = _scenarios()
    pool = build_pool(header, scs, target_size=20, seed=42)
    assert [s.scenario_id for s in pool.scenarios[:4]] == [s.scenario_id for s in scs]
    assert pool.n_original == 4


def test_pool_respects_per_original_cap():
    header, scs = _scenarios()
    pool = build_pool(header, scs, target_size=20, seed=42)
    cap = math.ceil((20 - 4) / 4)
    assert pool.perturbations_per_original_cap == cap
    for s in scs:
        n = sum(1 for p in pool.scenarios if p.perturbed and p.origin_test == s.origin_test)
        assert n <= cap


def test_pool_has_no_duplicates():
    header, scs = _scenarios()
    pool = build_pool(header, scs, target_size=40, seed=42)
    keys = [s.canonical() for s in pool.scenarios]
    assert len(keys) == len(set(keys))


def test_pool_is_seed_deterministic():
    header, scs = _scenarios()
    a = build_pool(header, scs, target_size=20, seed=7)
    b = build_pool(header, scs, target_size=20, seed=7)
    assert [s.canonical() for s in a.scenarios] == [s.canonical() for s in b.scenarios]


def test_pool_never_exceeds_target_and_does_not_perturb_when_full():
    header, scs = _scenarios()
    pool = build_pool(header, scs, target_size=3, seed=1)
    assert pool.n_original == 4 and pool.n_perturbed == 0  # originals are never removed


def test_pool_reports_low_diversity():
    header, scs = _scenarios()
    pool = build_pool(header, scs[:2], target_size=10, seed=1)
    assert pool.composition()["low_scenario_diversity"]
