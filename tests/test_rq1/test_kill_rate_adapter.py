"""compute_kill_matrix_generic must agree with compute_kill_matrix on real
generated mutants, including a timeout (which counts as killed -- unlike
Stage 0's suite veto, which excludes it)."""

from __future__ import annotations

from meta_real_eval.benchmarks.humaneval import HumanEvalBenchmark
from meta_real_eval.core.config import Config
from meta_real_eval.core.data_loader import load_humaneval
from meta_real_eval.rq1.kill_rate import compute_kill_matrix, compute_kill_matrix_generic
from meta_real_eval.stage0.corpus_builder import Mutant, generate_mutants

TASK_INDICES = [0, 2]


def _cfg(timeout_s=5.0, cpu_workers=1):
    return Config.model_validate({"execution": {"timeout_s": timeout_s, "cpu_workers": cpu_workers}})


def test_kill_verdicts_match_legacy_on_real_mutants():
    bench = HumanEvalBenchmark()
    legacy = {t.task_index: t for t in load_humaneval(tasks=TASK_INDICES)}
    cfg = _cfg()

    for t in bench.load_tasks(TASK_INDICES):
        h = legacy[t.task_index]
        mutants = generate_mutants(h.prompt, h.canonical_solution, h.entry_point,
                                   ["AOR", "ROR", "SDL"], seed=42)
        if not mutants:
            continue
        equiv_ids: set[str] = set()  # evaluate every mutant, equivalence is Stage 0's job
        legacy_results = {r.mutant_id: r for r in compute_kill_matrix(h, mutants, equiv_ids, timeout_s=5.0, cpu_workers=1)}
        generic_results = {r.mutant_id: r for r in compute_kill_matrix_generic(cfg, t, mutants, equiv_ids, timeout_s=5.0, cpu_workers=1)}

        assert set(legacy_results) == set(generic_results)
        for mid in legacy_results:
            assert legacy_results[mid].is_killed == generic_results[mid].is_killed, (t.label, mid)


def test_timeout_counts_as_killed_both_ways():
    bench = HumanEvalBenchmark()
    h = load_humaneval(tasks=[0])[0]
    t = bench.load_tasks([0])[0]
    cfg = _cfg(timeout_s=0.5)

    hanging = Mutant(mutant_id="X", operator="LLM",
                     description="hangs", code="while True:\n    pass\n")
    legacy = compute_kill_matrix(h, [hanging], set(), timeout_s=0.5, cpu_workers=1)[0]
    generic = compute_kill_matrix_generic(cfg, t, [hanging], set(), timeout_s=0.5, cpu_workers=1)[0]
    assert legacy.is_killed and generic.is_killed


def test_equivalent_mutants_are_excluded_from_both():
    bench = HumanEvalBenchmark()
    h = load_humaneval(tasks=[0])[0]
    t = bench.load_tasks([0])[0]
    cfg = _cfg()
    identity = Mutant(mutant_id="same", operator="LLM", description="unchanged",
                      code=h.prompt + h.canonical_solution)
    assert compute_kill_matrix(h, [identity], {"same"}, timeout_s=5.0, cpu_workers=1) == []
    assert compute_kill_matrix_generic(cfg, t, [identity], {"same"}, timeout_s=5.0, cpu_workers=1) == []
