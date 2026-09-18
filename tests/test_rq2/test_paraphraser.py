"""Tests for deterministic metamorphic prompt transforms."""

import ast

import pytest
from meta_real_eval.rq2.paraphraser import apply_relation, apply_all_relations

SAMPLE_PROMPT = (
    'def has_close_elements(numbers: List[float], threshold: float) -> bool:\n'
    '    """ Check if in given list of numbers, are any two numbers closer to each other\n'
    '    than given threshold.\n'
    '    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n'
    '    False\n'
    '    """\n'
)


def test_original_is_unchanged():
    result = apply_relation(SAMPLE_PROMPT, "original")
    assert result == SAMPLE_PROMPT


def test_persona_prepends_framing():
    result = apply_relation(SAMPLE_PROMPT, "persona")
    assert result.startswith("As a senior Python engineer")
    assert SAMPLE_PROMPT in result


def test_terse_removes_filler():
    prompt_with_filler = "Please complete the function. Note that it should handle edge cases."
    result = apply_relation(prompt_with_filler, "terse")
    assert "Please" not in result
    assert "Note that" not in result


def test_formal_adds_specification_header():
    result = apply_relation(SAMPLE_PROMPT, "formal")
    assert "[Specification]" in result


def test_reorder_moves_examples():
    result = apply_relation(SAMPLE_PROMPT, "reorder")
    # Examples (>>>) should now appear before the description
    example_pos = result.find(">>>")
    desc_pos = result.find("Check if")
    if example_pos != -1 and desc_pos != -1:
        assert example_pos < desc_pos


def test_apply_all_returns_all_relations():
    relations = ["original", "persona", "formal", "reorder", "terse"]
    result = apply_all_relations(SAMPLE_PROMPT, relations)
    assert set(result.keys()) == set(relations)


# ---------------------------------------------------------------------------
# Regression: reorder used to leave the docstring's closing quote attached to
# `examples`, so moving examples ahead of the description closed the
# docstring early and stranded the description as dead code outside the
# function. Measured on the real corpus: 76/76 prompts this relation actually
# changes produced a SyntaxError once a completion was appended -- the
# previous test above never caught it because it only checks that ">>>"
# appears before "Check if" in the string, not that the result still parses.
# ---------------------------------------------------------------------------

def test_reorder_keeps_the_docstring_valid():
    result = apply_relation(SAMPLE_PROMPT, "reorder")
    ast.parse(result)  # raises SyntaxError if the docstring closed early
    # The description must still be inside the docstring, not ejected after it.
    closing_quote_idx = result.rindex('"""')
    assert result.index("Check if") < closing_quote_idx


def test_reorder_keeps_the_docstring_valid_on_every_humaneval_prompt():
    """The real thing the bug broke: every prompt reorder actually changes
    must still parse once a real completion is appended, not just the sample."""
    from meta_real_eval.core.data_loader import load_humaneval

    for task in load_humaneval():
        reordered = apply_relation(task.prompt, "reorder")
        if reordered == task.prompt:
            continue
        ast.parse(reordered + task.canonical_solution)


def test_reorder_is_a_no_op_without_examples():
    """A no-op relation is a dead cell, not a measurement.

    ``generate_task`` builds the messages from the transformed prompt, and
    ``ResponseCache.key`` hashes the messages — so a relation that returns its
    input unchanged produces the same cache key as ``original`` and replays
    original's completions, scoring tau_b = 1.0 without testing anything.
    Measured over the real corpus: ``reorder`` is a no-op on 88 of 164 HumanEval
    prompts and ``terse`` on 103, i.e. 191 of 656 (task, relation) cells.

    These transforms are kept as RQ2's control arm precisely so that shortfall is
    a measured comparison against the LLM corpus rather than a claim. The LLM arm
    has no equivalent hole: Gate A rejects any candidate byte-identical to the
    original (see test_corpus.py).
    """
    prompt = 'def f(x):\n    """Return x."""\n'
    assert apply_relation(prompt, "reorder") == prompt


def test_terse_is_a_no_op_without_filler():
    prompt = 'def f(x):\n    """Return x."""\n'
    assert apply_relation(prompt, "terse") == prompt


def test_unknown_relation_raises():
    with pytest.raises(ValueError):
        apply_relation(SAMPLE_PROMPT, "nonsense")
