"""compute_divergence_generic must reproduce compute_divergence's headline
numbers (pairwise_disagreement_rate, comparable/excluded counts, per-solution
passes_benchmark labels) exactly on real HumanEval tasks -- including a
timeout, which the two sentinels (ERROR_OUTPUT vs TIMEOUT/__error__) make the
riskiest case to get right generically (see divergence.py's module docstring
on _unusable)."""

from __future__ import annotations

from meta_real_eval.benchmarks.humaneval import HumanEvalBenchmark
from meta_real_eval.core.config import Config
from meta_real_eval.core.data_loader import load_humaneval
from meta_real_eval.rq3.divergence import compute_divergence, compute_divergence_generic

N_INPUTS = 15
TIMEOUT_S = 3.0

# HumanEval/0's real signature: has_close_elements(numbers: List[float], threshold: float) -> bool.
CORRECT = ("    for i in range(len(numbers)):\n"
          "        for j in range(len(numbers)):\n"
          "            if i != j and abs(numbers[i] - numbers[j]) < threshold:\n"
          "                return True\n"
          "    return False\n")
WRONG = CORRECT.replace("< threshold", "> threshold")  # a real, different-output mutant


def _completions(bodies):
    return {f"r{i}": {"m": [body]} for i, body in enumerate(bodies)}


def _cfg(cpu_workers=1):
    return Config.model_validate({"execution": {"cpu_workers": cpu_workers, "timeout_s": TIMEOUT_S}})


def _run_both(h, t, cfg, bodies):
    legacy = compute_divergence(h, _completions(bodies), n_shared_inputs=N_INPUTS, timeout_s=TIMEOUT_S)
    generic = compute_divergence_generic(cfg, t, _completions(bodies), n_shared_inputs=N_INPUTS, timeout_s=TIMEOUT_S)
    return legacy, generic


def _assert_headline_matches(legacy, generic):
    assert legacy["n_solutions"] == generic["n_solutions"]
    assert legacy["n_inputs"] == generic["n_inputs"]
    assert legacy["pairwise_disagreement_rate"] == generic["pairwise_disagreement_rate"]
    assert legacy["n_comparable_pairs"] == generic["n_comparable_pairs"]
    assert legacy["n_pairs_excluded_error"] == generic["n_pairs_excluded_error"]
    legacy_labels = sorted((s["relation"], s["model"], s["passes_benchmark"]) for s in legacy["solutions"])
    generic_labels = sorted((s["relation"], s["model"], s["passes_benchmark"]) for s in generic["solutions"])
    assert legacy_labels == generic_labels


def _pair(idx):
    h = load_humaneval(tasks=[idx])[0]
    t = HumanEvalBenchmark().load_tasks([idx])[0]
    return h, t


def test_identical_solutions_match():
    h, t = _pair(0)
    legacy, generic = _run_both(h, t, _cfg(), [CORRECT] * 3)
    _assert_headline_matches(legacy, generic)
    assert generic["pairwise_disagreement_rate"] == 0.0


def test_divergent_solutions_match():
    h, t = _pair(0)
    legacy, generic = _run_both(h, t, _cfg(), [CORRECT, WRONG])
    _assert_headline_matches(legacy, generic)
    assert generic["pairwise_disagreement_rate"] > 0


def test_crashing_solution_excluded_not_counted_as_agreement():
    """Two solutions that both crash must not register as agreeing -- this is
    exactly the case where a naive sentinel-string comparison would differ
    from is_timeout/is_error-based exclusion."""
    h, t = _pair(0)
    crash = "    raise ValueError('boom')\n"
    legacy, generic = _run_both(h, t, _cfg(), [crash, crash, CORRECT])
    _assert_headline_matches(legacy, generic)
    assert generic["n_pairs_excluded_error"] > 0


def test_timeout_is_excluded_not_compared_as_a_value():
    """A hang must be excluded via is_timeout, not silently treated as a
    comparable value distinct from a crash -- the one case where the two
    sentinels (ERROR_OUTPUT vs TIMEOUT) could diverge if handled naively."""
    h, t = _pair(0)
    hang = "    while True:\n        pass\n"
    legacy, generic = _run_both(h, t, _cfg(), [hang, CORRECT])
    _assert_headline_matches(legacy, generic)
    assert generic["n_comparable_pairs"] == 0
    assert generic["n_pairs_excluded_error"] == N_INPUTS


def test_parallel_cpu_workers_matches_serial():
    h, t = _pair(0)
    legacy, generic = _run_both(h, t, _cfg(cpu_workers=2), [CORRECT, WRONG, CORRECT])
    _assert_headline_matches(legacy, generic)


def test_consensus_matches_legacy_on_tier1():
    """_build_consensus_generic must reproduce _build_consensus's unanimous-vote
    consensus exactly for HumanEvalBenchmark, including the args_repr/
    expected_repr fields rq4.consistency.build_consistency_assertions reads."""
    h, t = _pair(0)
    legacy, generic = _run_both(h, t, _cfg(), [CORRECT, CORRECT, CORRECT, WRONG])
    lc, gc = legacy["consensus"], generic["consensus"]
    assert lc["n_inputs_with_consensus"] == gc["n_inputs_with_consensus"] > 0
    legacy_entries = sorted((e["args_repr"], e["expected_repr"], e["votes"], e["n_voters"])
                            for e in lc["entries"])
    generic_entries = sorted((e["args_repr"], e["expected_repr"], e["votes"], e["n_voters"])
                             for e in gc["entries"])
    assert legacy_entries == generic_entries
    assert generic["seed"] == 42 and generic["n_shared_inputs_requested"] == N_INPUTS


def test_single_solution_is_undefined_both_ways():
    h, t = _pair(2)
    legacy, generic = _run_both(h, t, _cfg(), ["    return number - int(number)\n"])
    assert legacy["pairwise_disagreement_rate"] is generic["pairwise_disagreement_rate"] is None
