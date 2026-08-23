"""Tests for turning a raw model completion into runnable source.

Three defects found in the pilot corpus (24,600 completions) are pinned here:

  924  body-only completions opening with a nested helper ("    def f(x):")
       were read as complete modules, run without the prompt, and died with
       IndentationError - scored as wrong answers.
   22  complete modules had their own imports sliced off at the `def` line.
    2  complete modules referenced a name only the prompt imports.

All three scored a correct solution as incorrect, and the first was distributed
unevenly across models - which is precisely what RQ2's ranking analysis cannot
absorb.
"""

from meta_real_eval.core.sandbox import execute
from meta_real_eval.rq2.evaluator import (
    _defines_entry_point,
    _extract_function_body,
    _strip_markdown,
    build_solution_code,
)

PROMPT = (
    "import math\n"
    "from typing import List\n"
    "\n"
    "\n"
    "def total(xs: List[int]) -> int:\n"
    '    """Return the sum of xs."""\n'
)
TEST = "def check(candidate):\n    assert candidate([1, 2, 3]) == 6\n"


def _runs(completion: str) -> bool:
    code = build_solution_code(completion, PROMPT, "total")
    return execute(code, TEST + "\ncheck(total)\n", timeout_s=10.0).passed


# --- the three real-corpus regressions --------------------------------------

def test_body_opening_with_a_nested_helper_still_gets_the_prompt():
    """The 924-completion bug: a leading indent is not a module definition."""
    completion = "    def _add(a, b):\n        return a + b\n    return sum(xs)\n"
    assert not _defines_entry_point(completion, "total")
    assert _runs(completion)


def test_complete_module_keeps_its_own_imports():
    """The 22-completion bug: slicing at `def` dropped the import above it."""
    completion = (
        "from functools import reduce\n"
        "\n"
        "def total(xs):\n"
        "    return reduce(lambda a, b: a + b, xs, 0)\n"
    )
    assert "from functools import reduce" in _extract_function_body(completion, "total")
    assert _runs(completion)


def test_complete_module_gets_the_prompts_imports_back():
    """The 2-completion bug: the module needs a name only the prompt imports."""
    completion = "def total(xs):\n    return int(math.fsum(xs))\n"
    assert _runs(completion)


# --- body vs module classification ------------------------------------------

def test_plain_body_gets_the_prompt_prepended():
    assert build_solution_code("    return sum(xs)\n", PROMPT, "total").startswith(PROMPT)
    assert _runs("    return sum(xs)\n")


def test_complete_module_is_not_glued_onto_the_prompt():
    completion = "def total(xs):\n    return sum(xs)\n"
    code = build_solution_code(completion, PROMPT, "total")
    assert "def total" in code
    assert code.count("def total") == 1      # the prompt's signature is not duplicated
    assert _runs(completion)


def test_nested_def_of_the_entry_point_name_is_not_a_module():
    """A helper that shadows the entry point name is still not callable."""
    body = "    def total(ys):\n        return 0\n    return sum(xs)\n"
    assert not _defines_entry_point(body, "total")
    assert _runs(body)


# --- markdown fences --------------------------------------------------------

def test_fenced_code_is_unwrapped():
    assert _runs("```python\ndef total(xs):\n    return sum(xs)\n```")


def test_unterminated_fence_is_still_unwrapped():
    """Truncated generations open a fence and never close it."""
    assert _strip_markdown("```python\ndef total(xs):\n    return sum(xs)\n").startswith("def")
    assert _runs("```python\ndef total(xs):\n    return sum(xs)\n")


def test_prose_above_the_definition_is_dropped():
    completion = "Here is my solution:\n\ndef total(xs):\n    return sum(xs)\n"
    assert _runs(completion)


def test_prose_and_imports_together_keep_the_imports():
    completion = (
        "Sure! Here you go.\n"
        "from functools import reduce\n"
        "def total(xs):\n"
        "    return reduce(lambda a, b: a + b, xs, 0)\n"
    )
    extracted = _extract_function_body(completion, "total")
    assert "reduce" in extracted
    assert "Sure!" not in extracted
    assert _runs(completion)


# --- degenerate input -------------------------------------------------------

def test_unparseable_completion_does_not_raise():
    """A truncated completion must score as a failure, never crash the run."""
    assert not _runs("def total(xs:\n    return sum(")


def test_empty_completion_does_not_raise():
    assert not _runs("")
