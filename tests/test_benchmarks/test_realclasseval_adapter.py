"""RealClassEval adapter tests, on a synthetic 2-task corpus + manifest."""

from __future__ import annotations

import gzip
import json

import pytest

from meta_real_eval.benchmarks.base import Benchmark
from meta_real_eval.benchmarks.gate import (
    INVALID_REFERENCE_MISMATCH,
    VALID_BEHAVIOURAL,
    VALID_EXCEPTION_ORACLE,
)
from meta_real_eval.benchmarks.realclasseval import (
    USER_TEMPLATE,
    ManifestMissing,
    RealClassEvalBenchmark,
    build_solution_with_report,
    extract_class_module,
)
from meta_real_eval.core.config import Config
from meta_real_eval.rq3.divergence import compute_divergence_generic
from meta_real_eval.stage0.corpus_builder import generate_mutants


def _rq4_cfg(bench):
    # compute_divergence_generic reconstructs get_benchmark(cfg) in its worker
    # function, so cfg must point at THIS fixture's corpus/manifest, not the
    # package defaults -- see rq2.evaluator._score_completion's docstring for
    # why reconstruction (rather than pickling bench) is the chosen pattern.
    return Config.model_validate({
        "benchmark": {"name": "realclasseval", "data_path": str(bench.corpus_path),
                      "manifest_path": str(bench.manifest_path)},
        "execution": {"cpu_workers": 1},
    })

REFERENCE = '''\
import math


class Counter:
    """A counter."""

    def __init__(self, start=0):
        self.count = start

    def add(self, n):
        if n < 0:
            raise ValueError("negative")
        self.count += n
        return self.count

    @property
    def root(self):
        return math.sqrt(self.count)

    @root.setter
    def root(self, value):
        self.count = value * value
        self.touched = True
'''

SKELETON = '''\
class Counter:
    """A counter."""

    def __init__(self, start=0):
        pass

    def add(self, n):
        """Add n; negative n raises ValueError."""
        pass
'''

TESTS = '''\
import pytest
import snippet_1 as module_0


def test_case_0():
    counter_0 = module_0.Counter(3)
    var_0 = counter_0.add(2)
    assert var_0 == 5


def test_case_1():
    counter_0 = module_0.Counter(1)
    with pytest.raises(ValueError):
        counter_0.add(-5)


@pytest.mark.xfail(strict=True)
def test_case_2():
    counter_0 = module_0.Counter(1)
    counter_0.add('x')


def test_case_3():
    counter_0 = module_0.Counter(0)
    var_0 = counter_0.add(4)
    assert var_0 == 4


def test_case_4():
    counter_0 = module_0.Counter(0)
    assert counter_0.count == 999
'''


def _row(split, num):
    return {
        "task_id": f"RealClassEval/{split}/snippet_{num}", "split": split,
        "snippet_id": f"snippet_{num}", "snippet_num": num, "class_short_name": "Counter",
        "skeleton_full_docstr": SKELETON, "skeleton_partial_docstr": None, "skeleton_no_docstr": None,
        "reference_code": REFERENCE.replace("snippet_1", f"snippet_{num}"),
        "test_code": TESTS.replace("snippet_1", f"snippet_{num}"),
    }


GATE_TESTS = {
    "test_case_0": {"validity": VALID_BEHAVIOURAL, "ref_exc_type": None, "trivial": False},
    "test_case_1": {"validity": VALID_EXCEPTION_ORACLE, "ref_exc_type": "ValueError", "trivial": False},
    "test_case_2": {"validity": VALID_EXCEPTION_ORACLE, "ref_exc_type": "builtins.TypeError", "trivial": False},
    "test_case_3": {"validity": VALID_BEHAVIOURAL, "ref_exc_type": None, "trivial": False},
    "test_case_4": {"validity": INVALID_REFERENCE_MISMATCH, "ref_exc_type": None, "trivial": False},
}


@pytest.fixture
def bench(tmp_path):
    corpus = tmp_path / "corpus.jsonl.gz"
    with gzip.open(corpus, "wt", encoding="utf-8") as f:
        for row in (_row("csn", 1), _row("post_cut-off", 7)):
            f.write(json.dumps(row) + "\n")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"tasks": [
        {"task_id": "RealClassEval/csn/snippet_1", "split": "csn", "status": "accepted",
         "task_index": 0, "tests": GATE_TESTS, "scenarios": {"excluded": {}}},
        {"task_id": "RealClassEval/post_cut-off/snippet_7", "split": "post_cut-off", "status": "excluded",
         "exclusion_reason": "missing_dependency"},
    ]}), encoding="utf-8")
    return RealClassEvalBenchmark(corpus_path=corpus, manifest_path=manifest)


@pytest.fixture
def task(bench):
    return bench.load_tasks()[0]


# --- loading -------------------------------------------------------------------

def test_conforms_to_protocol(bench):
    assert isinstance(bench, Benchmark)


def test_load_tasks_returns_only_accepted_tasks(bench, task):
    assert [t.task_id for t in bench.load_tasks()] == ["RealClassEval/csn/snippet_1"]
    assert task.label == "RCE_csn_snippet_1"
    assert task.target == "Counter" and task.module_name == "snippet_1"
    assert task.prompt == SKELETON


def test_load_tasks_rejects_unknown_index(bench):
    with pytest.raises(ValueError):
        bench.load_tasks([5])


def test_corpus_tasks_are_ungated(bench):
    assert len(bench.corpus_tasks()) == 2


def test_missing_manifest_is_a_clear_error(tmp_path):
    with pytest.raises(ManifestMissing):
        RealClassEvalBenchmark(manifest_path=tmp_path / "nope.json").load_tasks()


def test_generation_messages_use_the_paper_prompt_verbatim(bench, task):
    msgs = bench.generation_messages(task, task.prompt)
    assert msgs[-1]["content"] == USER_TEMPLATE.format(skeleton=SKELETON)
    assert msgs[-1]["content"].startswith("Implement the following class. Do not explain the code.")


# --- extraction and D7 -----------------------------------------------------------

def test_extract_fenced_block_defining_the_class():
    raw = "Here you go:\n```python\nprint('example')\n```\n```python\nclass Counter:\n    pass\n```\n"
    code, how = extract_class_module(raw, "Counter")
    assert how == "fenced" and code.strip() == "class Counter:\n    pass"


def test_extract_keeps_imports_and_helpers_above_the_class():
    raw = "import math\n\ndef helper():\n    return 1\n\nclass Counter:\n    pass\n"
    code, how = extract_class_module(raw, "Counter")
    assert how == "raw" and "import math" in code and "def helper" in code


def test_extract_trims_leading_and_trailing_prose():
    raw = "Sure! Here is the class.\nclass Counter:\n    x = 1\nThis implementation is efficient."
    code, how = extract_class_module(raw, "Counter")
    assert how == "trimmed" and code.strip() == "class Counter:\n    x = 1"


def test_extract_unclosed_fence():
    raw = "```python\nclass Counter:\n    x = 1\n"
    code, _ = extract_class_module(raw, "Counter")
    assert "class Counter" in code and "```" not in code


def test_extract_failure_is_reported_not_repaired():
    _, how = extract_class_module("def something_else():\n    pass\n", "Counter")
    assert how == "failed"


def test_d7_never_copies_from_the_reference():
    """The skeleton has no imports (as for every task in the corpus), so a
    completion that forgets `import math` is NOT given the reference's
    import -- it must fail on its own."""
    completion = "class Counter:\n    def f(self):\n        return math.pi\n"
    code, report = build_solution_with_report(completion, SKELETON, "Counter")
    assert report.imports_prompt == [] and report.imports_reattached == []
    assert "import math" not in code


def test_d7_reattaches_only_prompt_visible_imports():
    prompt = "import os\n" + SKELETON
    code, report = build_solution_with_report("class Counter:\n    pass\n", prompt, "Counter")
    assert report.imports_reattached == ["import os"]
    assert code.startswith("import os\n")


# --- execution and scoring -------------------------------------------------------

def test_reference_scores_one_on_its_valid_tests(bench, task):
    r = bench.run_suite(task, task.reference_code, timeout_s=30)
    assert r.scores["primary"] == 1.0 and r.passed_all
    assert r.scores["n_valid"] == 4                 # test_case_4 is invalid: never run, never scored
    assert "test_case_4" not in r.outcomes


def test_wrong_exception_type_loses_primary_but_not_native_credit(bench, task):
    wrong = task.reference_code.replace('raise ValueError("negative")', 'raise KeyError("negative")')
    r = bench.run_suite(task, wrong, timeout_s=30)
    # test_case_1 (pytest.raises(ValueError)) now fails outright; test_case_2
    # (xfail, ref TypeError) is untouched.
    assert r.scores["primary"] == 0.75
    assert not r.passed_all


def test_broken_completion_scores_zero(bench, task):
    r = bench.run_suite(task, "raise ImportError('nope')\n", timeout_s=30)
    assert r.scores["primary"] == 0.0


def test_degrade_levels_are_nested(bench, task):
    subsets = [bench.degrade(task, lvl, seed=42).subset for lvl in (0.0, 0.2, 0.5, 0.8)]
    assert subsets[0] == frozenset({"test_case_0", "test_case_1", "test_case_2", "test_case_3"})
    for a, b in zip(subsets, subsets[1:]):
        assert b <= a
    assert [len(s) for s in subsets] == [4, 3, 2, 0]   # ceil(4*0.2)=1, ceil(4*0.5)=2, ceil(4*0.8)=4


def test_empty_degraded_suite_has_no_score_not_zero(bench, task):
    full = bench.run_suite(task, task.reference_code, timeout_s=30)
    assert bench.score_outcomes(task, full.outcomes, frozenset())["primary"] is None


def test_rq4_reuse_identity_against_real_degraded_execution(bench, task):
    """Plan review #14/#17: rescoring stored outcomes restricted to a degraded
    subset must EQUAL actually executing the degraded suite, at every level."""
    candidate = task.reference_code.replace("self.count += n", "self.count += n * 2")
    full = bench.run_suite(task, candidate, timeout_s=30)
    for level in (0.0, 0.2, 0.5):
        suite = bench.degrade(task, level, seed=42)
        executed = bench.run_suite(task, candidate, timeout_s=30, suite=suite)
        assert bench.score_outcomes(task, full.outcomes, suite.subset) == executed.scores, level


# --- mutation scope ---------------------------------------------------------------

def test_sdl_scope_covers_every_method_including_property_setter(bench, task):
    mutants = generate_mutants("", bench.mutation_source(task), task.target, ["SDL"],
                               max_per_operator=10, seed=42, sdl_scope=bench.sdl_scope(task))
    methods = {m.method for m in mutants}
    assert {"Counter.add", "Counter.root"} <= methods
    # The setter (same name as the getter) is mutated by position, not by name:
    # its two-statement body is the only place `self.touched` can disappear.
    assert any("self.touched" not in m.code for m in mutants)


def test_sdl_round_robin_does_not_let_one_method_take_the_budget(bench, task):
    mutants = generate_mutants("", bench.mutation_source(task), task.target, ["SDL"],
                               max_per_operator=2, seed=42, sdl_scope=bench.sdl_scope(task))
    assert len({m.method for m in mutants}) == 2


# --- scenarios -------------------------------------------------------------------------

def test_input_pool_and_reference_observations(bench, task):
    pool = bench.input_pool(task, 8, seed=42)
    assert pool.composition["n_original"] == 5 and len(pool.items) <= 8
    obs, masks = bench.reference_observations(task, pool, timeout_s=10)
    assert len(obs) == len(pool.items) and all(m == frozenset() for m in masks)
    assert all(bench.observations_agree(o, o, m) for o, m in zip(obs, masks))
    mutant = task.reference_code.replace("self.count += n", "self.count += n * 2")
    mut_obs = bench.observe(task, mutant, pool, timeout_s=10)
    assert not all(bench.observations_agree(a, b, m) for a, b, m in zip(obs, mut_obs, masks))


def test_consistency_suite_below_threshold_builds_nothing(bench, task):
    code, n = bench.consistency_suite(task, {"pairwise_disagreement_rate": 0.0, "n_solutions": 4}, threshold=0.1)
    assert (code, n) == ("", 0)


def test_consistency_suite_too_few_solutions_builds_nothing(bench, task):
    code, n = bench.consistency_suite(task, {"pairwise_disagreement_rate": 0.9, "n_solutions": 2}, threshold=0.1)
    assert (code, n) == ("", 0)


# A fresh candidate that was NOT one of the solutions divergence was computed
# over: it drops the guard that all four original solutions agreed on, so it
# must violate the resulting consensus even though it never contributed to it.
_DROPS_THE_GUARD = REFERENCE.replace(
    'if n < 0:\n            raise ValueError("negative")\n        ', ''
)


def test_consistency_suite_end_to_end(bench, task):
    """Build real consensus via compute_divergence_generic on 3 reference
    copies + 1 state-mutating mutant, then confirm: assertions are built,
    they compile, every ORIGINAL contributing solution (incl. the mutant that
    helped form them) still satisfies them, and a FRESH candidate that
    violates what they agreed on is caught."""
    mutant = REFERENCE.replace("self.count += n", "self.count += n * 2")
    completions_data = {"r0": {"m": [REFERENCE]}, "r1": {"m": [REFERENCE]},
                        "r2": {"m": [REFERENCE]}, "r3": {"m": [mutant]}}

    divergence_data = compute_divergence_generic(
        _rq4_cfg(bench), task, completions_data, n_shared_inputs=10, timeout_s=10, seed=1,
    )
    assert divergence_data["pairwise_disagreement_rate"] > 0  # r3 disagrees with r0-r2 on add()'s return
    assert divergence_data["consensus"]["n_inputs_with_consensus"] > 0  # but agrees on e.g. the raises scenario

    code, n = bench.consistency_suite(task, divergence_data, threshold=0.01, max_assertions=20)
    assert n > 0 and "test_ca_0" in code
    compile(code, "<test>", "exec")  # must be valid Python on its own

    degraded = bench.degrade(task, 0.0, seed=1)
    augmented = bench.augmented_suite(task, degraded, code, n)
    assert augmented.extra_valid == frozenset(f"test_ca_{i}" for i in range(n))

    for contributor in (REFERENCE, mutant):
        result = bench.run_suite(task, contributor, timeout_s=10, suite=augmented)
        ca_outcomes = {k: v for k, v in result.outcomes.items() if k.startswith("test_ca_")}
        assert len(ca_outcomes) == n
        assert all(o.outcome == "ordinary_pass" for o in ca_outcomes.values()), ca_outcomes

    violator = bench.run_suite(task, _DROPS_THE_GUARD, timeout_s=10, suite=augmented)
    ca_outcomes = {k: v for k, v in violator.outcomes.items() if k.startswith("test_ca_")}
    assert any(o.outcome != "ordinary_pass" for o in ca_outcomes.values()), (
        "a candidate that drops the agreed-on ValueError guard must fail at least one "
        "consistency assertion, even though it never contributed to building them"
    )
    assert not violator.passed_all
