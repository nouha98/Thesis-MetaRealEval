"""compute_tau_at_degradation_level_generic must reproduce
compute_tau_at_degradation_level exactly on real HumanEval tasks, at every
degradation level, for a multi-model multi-relation corpus."""

from __future__ import annotations

from meta_real_eval.benchmarks.humaneval import HumanEvalBenchmark
from meta_real_eval.core.config import Config
from meta_real_eval.core.data_loader import load_humaneval
from meta_real_eval.rq4.degradation import degrade
from meta_real_eval.rq4.interaction import (
    compute_tau_at_degradation_level,
    compute_tau_at_degradation_level_generic,
)

MODELS = ["m_a", "m_b", "m_c"]
TIMEOUT_S = 5.0

CORRECT = ("    for i in range(len(numbers)):\n"
          "        for j in range(len(numbers)):\n"
          "            if i != j and abs(numbers[i] - numbers[j]) < threshold:\n"
          "                return True\n"
          "    return False\n")
WRONG = CORRECT.replace("< threshold", "> threshold")
BROKEN = "    raise RuntimeError('nope')\n"


def _cfg():
    return Config.model_validate({
        "llm": {"models": [{"id": m} for m in MODELS]},
        "execution": {"timeout_s": TIMEOUT_S},
        "rq2": {"template_relations": ["r1"], "include_control_resample": False},
    })


def _completions_data():
    # A mix that produces a non-trivial, non-degenerate tau_b: models disagree
    # with each other, and across relations.
    return {
        "original": {"m_a": [CORRECT], "m_b": [WRONG], "m_c": [CORRECT]},
        "r1": {"m_a": [WRONG], "m_b": [WRONG], "m_c": [BROKEN]},
    }


def test_matches_legacy_at_every_degradation_level():
    h = load_humaneval(tasks=[0])[0]
    t = HumanEvalBenchmark().load_tasks([0])[0]
    cfg = _cfg()
    completions_data = _completions_data()

    for level in (0.0, 0.2, 0.5, 0.8):
        legacy_test = degrade(h.test, level, seed=42)
        legacy = compute_tau_at_degradation_level(h, completions_data, legacy_test, cfg)

        suite = HumanEvalBenchmark().degrade(t, level, seed=42)
        generic = compute_tau_at_degradation_level_generic(cfg, t, completions_data, suite)

        assert legacy["mean_tau_b"] == generic["mean_tau_b"], level
        assert legacy["tau_b_per_relation"] == generic["tau_b_per_relation"], level
        assert legacy["pass_at_1"] == generic["pass_at_1"], level
        assert legacy["degenerate_relations"] == generic["degenerate_relations"], level
        assert legacy["incomplete_relations"] == generic["incomplete_relations"], level
