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


# ---------------------------------------------------------------------------
# Regression: both "is this the canonical solution?" and "have I already
# accepted this?" used to be byte comparisons -- and the second did not exist
# at all. Measured over the 164-task corpus that let through 7 mutants that
# were the canonical solution reformatted, and left 47% of the accepted
# population duplicating a sibling (1456 mutants, 772 distinct), which inflates
# the LLM sample size with copies rather than observations.
# ---------------------------------------------------------------------------

_TASK = HumanEvalTask(
    task_id="HumanEval/0", task_index=0,
    prompt="def f(a, b):\n", canonical_solution="    return a + b\n",
    test="def check(candidate):\n    pass\n", entry_point="f",
)


class _ScriptedClient:
    """Returns a fixed list of completions, ignoring the request."""

    def __init__(self, completions):
        self._completions = completions

    async def complete(self, **kwargs):
        return self._completions


async def test_reformatted_echo_of_canonical_is_rejected():
    # Same AST as prompt+canonical, different layout and a comment.
    echo = "def f(a, b):\n    # add them\n    return a+b\n"
    mutants = await generate_llm_mutants(
        _TASK, "m", _ScriptedClient([echo]), n_mutants=3)
    assert mutants == []


async def test_sibling_differing_only_in_formatting_is_rejected():
    fault = "def f(a, b):\n    return a - b\n"
    reworded = "def f(a, b):\n    # subtle fault\n    return a-b\n"
    mutants = await generate_llm_mutants(
        _TASK, "m", _ScriptedClient([fault, reworded]), n_mutants=3)
    assert len(mutants) == 1


async def test_distinct_faults_are_all_kept():
    completions = [
        "def f(a, b):\n    return a - b\n",
        "def f(a, b):\n    return a * b\n",
        "def f(a, b):\n    return b + a + 1\n",
    ]
    mutants = await generate_llm_mutants(
        _TASK, "m", _ScriptedClient(completions), n_mutants=3)
    assert len(mutants) == 3


# ---------------------------------------------------------------------------
# Mutant validity. A mutant is evidence about the TEST SUITE only if it is a
# runnable program with one fault in it. A fragment that cannot define the
# function under test is killed by every suite for a reason unrelated to the
# suite's quality, so it inflates the kill rate with free kills. Measured on
# the recorded corpus: 40 of 684 LLM-mutant kills were NameError/SyntaxError
# rather than assertion failures.
# ---------------------------------------------------------------------------

PROMPT = (
    "from typing import List\n"
    "\n"
    "\n"
    "def filter_by_substring(strings: List[str], substring: str) -> List[str]:\n"
    '    """Filter strings containing substring."""\n'
)


def test_a_bare_return_fragment_is_not_a_mutant():
    """The real HumanEval/7 case: a return with no enclosing def."""
    assert _extract_code(
        "return [x for x in strings if x in substring]",
        PROMPT, "filter_by_substring",
    ) is None


def test_a_function_of_the_wrong_name_is_not_a_mutant():
    assert _extract_code(
        "def something_else(a):\n    return a\n", PROMPT, "filter_by_substring",
    ) is None


def test_a_valid_mutant_is_accepted():
    code = _extract_code(
        "def filter_by_substring(strings, substring):\n"
        "    return [x for x in strings if substring in x][:-1]\n",
        PROMPT, "filter_by_substring",
    )
    assert code is not None
    assert "filter_by_substring" in code


def test_a_mutant_missing_the_prompts_import_gets_it_back():
    """The real HumanEval/1 case: NameError on `List`, scored as a kill."""
    code = _extract_code(
        "def filter_by_substring(strings: List[str], substring: str) -> List[str]:\n"
        "    return []\n",
        PROMPT, "filter_by_substring",
    )
    assert code is not None
    assert "from typing import List" in code
    compile(code, "<mutant>", "exec")          # would raise NameError at run time otherwise


def test_a_mutant_missing_a_prompt_helper_gets_it_back():
    prompt = (
        "def _helper(n):\n"
        "    return n * 2\n"
        "\n"
        "\n"
        "def entry(n):\n"
        '    """Doc."""\n'
    )
    code = _extract_code("def entry(n):\n    return _helper(n) + 1\n", prompt, "entry")
    assert code is not None
    assert "_helper" in code


def test_omitting_the_entry_point_keeps_the_old_parse_only_behaviour():
    """Callers that pass no entry point (older paths) are unaffected."""
    assert _extract_code("return 1", PROMPT) == "return 1"
