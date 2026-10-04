"""Generic RQ1 LLM-mutation functions must reproduce the Tier 1-only ones
exactly. The messages comparison matters most: they are a ResponseCache key,
so any drift silently turns every cached RQ1-generate response into a miss.
"""

from __future__ import annotations

from meta_real_eval.benchmarks.humaneval import HumanEvalBenchmark
from meta_real_eval.core.data_loader import load_humaneval
from meta_real_eval.rq1.llm_mutator import (
    _SYSTEM_PROMPT,
    _build_user_message,
    _extract_code,
    repair_mutant_code,
)
from meta_real_eval.rq1.llm_mutator import _extract_code_generic

TASK_INDICES = [0, 2, 32]


def _pairs():
    bench = HumanEvalBenchmark()
    legacy = {t.task_index: t for t in load_humaneval(tasks=TASK_INDICES)}
    return [(t, legacy[t.task_index]) for t in bench.load_tasks(TASK_INDICES)]


def test_llm_mutation_messages_match_byte_for_byte():
    bench = HumanEvalBenchmark()
    for t, h in _pairs():
        for hint in ("", "Make the fault an off-by-one or boundary error."):
            got = bench.llm_mutation_messages(t, hint)
            expected = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(h, hint)},
            ]
            assert got == expected, (t.label, hint)


def test_repair_mutant_matches_legacy():
    bench = HumanEvalBenchmark()
    for t, h in _pairs():
        for code in (
            h.prompt + h.canonical_solution,                        # valid as-is
            h.canonical_solution,                                   # needs prompt re-attached
            "def not_the_entry_point():\n    return 1\n",           # unrepairable
        ):
            assert bench.repair_mutant(t, code) == repair_mutant_code(code, h.prompt, h.entry_point)


def test_extract_code_generic_matches_legacy():
    bench = HumanEvalBenchmark()
    for t, h in _pairs():
        for raw in (
            h.canonical_solution,
            f"```python\n{h.canonical_solution}```",
            "",
            "   \n\t\n  ",
            "```python\n```",
            "not valid python (((",
        ):
            assert _extract_code_generic(raw, bench, t) == _extract_code(raw, h.prompt, h.entry_point)
