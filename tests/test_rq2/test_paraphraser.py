"""Tests for deterministic metamorphic prompt transforms."""

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


def test_unknown_relation_raises():
    with pytest.raises(ValueError):
        apply_relation(SAMPLE_PROMPT, "nonsense")
