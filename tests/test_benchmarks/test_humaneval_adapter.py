"""The HumanEval adapter must be a pure delegation: Tier 1 through the
adapter == Tier 1 without it. Checked on real tasks, against the legacy
functions and (where present) against stored Tier 1 results."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meta_real_eval.benchmarks.humaneval import CHECK, HumanEvalBenchmark
from meta_real_eval.benchmarks.outcomes import ORDINARY_FAIL, ORDINARY_PASS
from meta_real_eval.core.data_loader import load_humaneval, task_label
from meta_real_eval.rq2.evaluator import _run_completion, build_solution_code
from meta_real_eval.rq4.degradation import degrade
from meta_real_eval.stage0.corpus_builder import generate_mutants
from meta_real_eval.stage0.equivalence import _generate_inputs

_ROOT = Path(__file__).resolve().parents[2]
RESULTS = next((d for d in (_ROOT / "results_tier1", _ROOT / "results") if (d / "stage0").exists()), None)
SAMPLE = [0, 2, 10, 32, 38, 50]  # includes the helper-function tasks (32/38/50)


@pytest.fixture(scope="module")
def bench():
    return HumanEvalBenchmark()


@pytest.fixture(scope="module")
def pairs(bench):
    legacy = {t.task_index: t for t in load_humaneval(tasks=SAMPLE)}
    return [(t, legacy[t.task_index]) for t in bench.load_tasks(SAMPLE)]


def test_load_tasks_maps_every_field(pairs):
    for t, h in pairs:
        assert (t.task_id, t.task_index, t.label) == (h.task_id, h.task_index, task_label(h))
        assert t.prompt == h.prompt and t.test_code == h.test and t.target == h.entry_point
        assert t.reference_code == h.prompt + h.canonical_solution


def test_build_solution_delegates(pairs, bench):
    for t, h in pairs:
        for completion in (h.canonical_solution, "    return None\n", f"```python\n{h.prompt}{h.canonical_solution}```"):
            assert bench.build_solution(t, completion) == build_solution_code(completion, h.prompt, h.entry_point)


def test_run_suite_matches_legacy_execution(pairs, bench):
    for t, h in pairs:
        for completion, expected in ((h.canonical_solution, ORDINARY_PASS), ("    return None\n", ORDINARY_FAIL)):
            legacy = _run_completion(completion, h.prompt, h.test, h.entry_point, 10.0)
            result = bench.run_suite(t, bench.build_solution(t, completion), timeout_s=10.0)
            assert result.outcomes[CHECK].outcome == expected
            assert result.passed_all == legacy
            assert result.primary == (1.0 if legacy else 0.0)


def test_degrade_delegates(pairs, bench):
    for t, h in pairs:
        for level in (0.0, 0.2, 0.5, 0.8):
            assert bench.degrade(t, level, seed=42).test_code == degrade(h.test, level, seed=42)
            assert bench.degrade(t, level, seed=42).subset is None  # re-execute, not rescore


def test_input_pool_delegates(pairs, bench):
    for t, h in pairs[:3]:
        assert bench.input_pool(t, 50, seed=42).items == _generate_inputs(h, 50, 42)


def test_mutation_inputs_reproduce_legacy_mutants(pairs, bench):
    """Stage 0 will call generate_mutants("", mutation_source, ..., sdl_scope)
    through the adapter. That must give byte-identical mutants to the legacy
    call, and to the stored Tier 1 corpus where it exists."""
    for t, h in pairs:
        legacy = generate_mutants(h.prompt, h.canonical_solution, h.entry_point, ["AOR", "ROR", "SDL"], seed=42)
        via = generate_mutants("", bench.mutation_source(t), t.target, ["AOR", "ROR", "SDL"],
                               seed=42, sdl_scope=bench.sdl_scope(t))
        assert [(m.mutant_id, m.code) for m in via] == [(m.mutant_id, m.code) for m in legacy]


@pytest.mark.skipif(RESULTS is None, reason="no stored Tier 1 results (results_tier1/ or results/)")
def test_mutants_match_the_stored_tier1_corpus(pairs, bench):
    for t, _ in pairs:
        stored = RESULTS / "stage0" / t.label / "mutants.json"
        assert stored.exists(), stored
        via = generate_mutants("", bench.mutation_source(t), t.target, ["AOR", "ROR", "SDL"],
                               seed=42, sdl_scope=bench.sdl_scope(t))
        on_disk = json.loads(stored.read_text(encoding="utf-8"))
        assert [(m["mutant_id"], m["code"]) for m in on_disk] == [(m.mutant_id, m.code) for m in via]
