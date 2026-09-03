"""Tests for LLM-mutant code extraction."""

from meta_real_eval.core.data_loader import HumanEvalTask
from meta_real_eval.rq1.llm_mutator import (
    MUTANT_MAX_TOKENS,
    _extract_code,
    generate_llm_mutants,
)


# ---------------------------------------------------------------------------
# Regression: ast.parse("") succeeds -- an empty module is syntactically
# valid Python -- so a blank completion used to be "extracted" as a real,
# zero-length mutant instead of being rejected as a failed attempt. This is
# how qwen36-35b's empty completions (see test_llm_client.py's
# _message_text tests for the root cause) ended up written to
# llm_mutants.json as code: "" instead of triggering the generate-phase
# retry logic.
# ---------------------------------------------------------------------------

def test_empty_completion_is_rejected():
    assert _extract_code("", "def f():\n") is None


def test_whitespace_only_completion_is_rejected():
    assert _extract_code("   \n\t\n  ", "def f():\n") is None


def test_empty_fenced_block_is_rejected():
    assert _extract_code("```python\n```", "def f():\n") is None


def test_valid_code_still_extracted():
    code = "def f(a, b):\n    return a - b"
    assert _extract_code(code + "\n", "def f(a, b):\n") == code


def test_fenced_code_still_stripped_and_extracted():
    raw = "```python\ndef f(a, b):\n    return a - b\n```"
    assert _extract_code(raw, "def f(a, b):\n") == "def f(a, b):\n    return a - b"


def test_unparseable_completion_is_rejected():
    assert _extract_code("def bad(:\n    pass", "def f():\n") is None


# ---------------------------------------------------------------------------
# Regression: live-probed 2026-09-03 -- at max_tokens=1024, qwen36-35b spends
# its entire budget on reasoning and hits finish_reason="length" with EMPTY
# content on every attempt, even for a trivial function. Raising the budget
# is what actually fixes it (the reasoning_content fallback in
# InnkubeClient._message_text only helps once the model has room to finish).
# This just locks in that the real call site asks for a generous budget, not
# the specific number -- see the comment on MUTANT_MAX_TOKENS for why.
# ---------------------------------------------------------------------------

class _FakeClient:
    def __init__(self):
        self.last_call: dict | None = None

    async def complete(self, **kwargs):
        self.last_call = kwargs
        return ["def f():\n    return 1\n"]


def test_mutant_max_tokens_is_not_the_old_undersized_budget():
    assert MUTANT_MAX_TOKENS > 1024


async def test_generate_llm_mutants_requests_the_generous_budget():
    task = HumanEvalTask(
        task_id="HumanEval/0", task_index=0,
        prompt="def f():\n", canonical_solution="    return 0\n",
        test="def check(candidate):\n    pass\n", entry_point="f",
    )
    client = _FakeClient()
    await generate_llm_mutants(task, "some-model", client, n_mutants=1)
    assert client.last_call["max_tokens"] == MUTANT_MAX_TOKENS
