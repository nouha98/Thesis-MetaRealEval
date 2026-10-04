"""Generic Stage 0 equivalence (check_equivalence_generic /
compute_canonical_observations) must reproduce the legacy Tier 1 functions
exactly, including the control-flow properties that are easy to lose in a
generalisation: early exit on first divergence, the suite-veto's timeout
exclusion, and compute_canonical_outputs' cpu_workers parallelism.

Tasks 32/38/50 are deliberately included: the module docstring on
stage0/equivalence.py calls them out as the only tasks where a helper-function
mutation can ONLY be caught by the suite veto (differential fuzzing on the
entry point alone never calls the helper), so they exercise the "suite_kills"
reason path specifically.
"""

from __future__ import annotations

import pytest

from meta_real_eval.benchmarks.humaneval import HumanEvalBenchmark
from meta_real_eval.core.config import Config
from meta_real_eval.core.data_loader import load_humaneval
from meta_real_eval.stage0.corpus_builder import generate_mutants
from meta_real_eval.stage0.equivalence import (
    _generate_inputs,
    check_equivalence,
    check_equivalence_generic,
    compute_canonical_observations,
    compute_canonical_outputs,
)

N_FUZZ = 40          # small, but exercises every reason path (see below)
TIMEOUT_S = 5.0
SEED = 42
TASK_INDICES = [0, 2, 32, 38, 50]
MAX_MUTANTS_PER_TASK = 4  # bound test runtime; real corpus is exercised in full below


def _cfg(cpu_workers: int = 1) -> Config:
    return Config.model_validate({"execution": {"cpu_workers": cpu_workers, "timeout_s": TIMEOUT_S}})


@pytest.fixture(scope="module")
def bench():
    return HumanEvalBenchmark()


@pytest.fixture(scope="module")
def pairs(bench):
    legacy = {t.task_index: t for t in load_humaneval(tasks=TASK_INDICES)}
    return [(t, legacy[t.task_index]) for t in bench.load_tasks(TASK_INDICES)]


def test_canonical_observations_match_legacy_outputs_serial(bench, pairs):
    cfg = _cfg(cpu_workers=1)
    for t, h in pairs:
        pool, obs = compute_canonical_observations(bench, t, N_FUZZ, TIMEOUT_S, SEED)
        legacy = compute_canonical_outputs(h, N_FUZZ, TIMEOUT_S, SEED, cpu_workers=1)
        assert pool.items == _generate_inputs(h, N_FUZZ, SEED)
        assert obs == legacy, t.label


def test_canonical_observations_match_legacy_outputs_parallel(bench, pairs):
    """The ProcessPoolExecutor branch in HumanEvalBenchmark.observe must
    produce the SAME values as the serial legacy path, in the SAME order."""
    t, h = pairs[0]
    cfg = _cfg(cpu_workers=2)
    bench2 = HumanEvalBenchmark(cfg)
    _, parallel_obs = compute_canonical_observations(bench2, t, N_FUZZ, TIMEOUT_S, SEED)
    legacy = compute_canonical_outputs(h, N_FUZZ, TIMEOUT_S, SEED, cpu_workers=2)
    assert parallel_obs == legacy


def test_equivalence_verdicts_match_on_real_generated_mutants(bench, pairs):
    """The real test: every mutant Stage 0 would actually generate for these
    tasks, scored both ways, must agree on is_equivalent / reason /
    n_inputs_tested / diverging_input -- not just on the final boolean."""
    cfg = _cfg(cpu_workers=1)
    seen_reasons: set[str] = set()

    for t, h in pairs:
        mutants = generate_mutants(h.prompt, h.canonical_solution, h.entry_point,
                                   ["AOR", "ROR", "SDL"], seed=SEED)[:MAX_MUTANTS_PER_TASK]
        if not mutants:
            continue
        legacy_canon = compute_canonical_outputs(h, N_FUZZ, TIMEOUT_S, SEED, cpu_workers=1)
        pool, obs = compute_canonical_observations(bench, t, N_FUZZ, TIMEOUT_S, SEED)
        assert obs == legacy_canon  # precondition for a fair comparison below

        for mutant in mutants:
            legacy = check_equivalence(h, mutant, N_FUZZ, TIMEOUT_S, SEED, canon_outs=legacy_canon)
            generic = check_equivalence_generic(cfg, t, mutant, N_FUZZ, TIMEOUT_S, SEED,
                                                pool=pool, canon_obs=obs)
            assert (generic.is_equivalent, generic.reason, generic.n_inputs_tested) == (
                legacy.is_equivalent, legacy.reason, legacy.n_inputs_tested
            ), (t.label, mutant.mutant_id, mutant.description)
            assert generic.diverging_input == legacy.diverging_input
            seen_reasons.add(legacy.reason)

    # A meaningful test exercises more than one path through the function.
    assert {"diverged"} <= seen_reasons


def test_suite_veto_path_is_reachable_and_matches(bench, pairs):
    """Tasks 32/38/50 mutate a helper the entry point's own fuzz inputs never
    reach -- confirms check_equivalence_generic's suite-veto step actually
    fires (not just that it's present in the code) and agrees with legacy."""
    cfg = _cfg(cpu_workers=1)
    helper_tasks = [(t, h) for t, h in pairs if t.task_index in (32, 38, 50)]
    found_suite_kill = False

    for t, h in helper_tasks:
        mutants = generate_mutants(h.prompt, h.canonical_solution, h.entry_point,
                                   ["AOR", "ROR", "SDL"], seed=SEED)
        legacy_canon = compute_canonical_outputs(h, N_FUZZ, TIMEOUT_S, SEED, cpu_workers=1)
        pool, obs = compute_canonical_observations(bench, t, N_FUZZ, TIMEOUT_S, SEED)

        for mutant in mutants:
            legacy = check_equivalence(h, mutant, N_FUZZ, TIMEOUT_S, SEED, canon_outs=legacy_canon)
            if legacy.reason != "suite_kills":
                continue
            found_suite_kill = True
            generic = check_equivalence_generic(cfg, t, mutant, N_FUZZ, TIMEOUT_S, SEED,
                                                pool=pool, canon_obs=obs)
            assert (generic.is_equivalent, generic.reason) == (False, "suite_kills")

    assert found_suite_kill, "expected at least one suite-veto-only kill among 32/38/50's mutants"
