"""Gate A (structural validation) and corpus bookkeeping.

Every rejection reason gets a case: Gate A is the only free, deterministic check
standing between a bad rewrite and the corpus, and the one it exists for above
all is ``identical_to_original`` — a no-op prompt hashes to the same LLM cache
key as ``original``, so its completions come back identical and its tau_b is 1.0
by construction. 191 of 656 (task, relation) cells in the 164-task template run
were exactly that.
"""

import json

import pytest

from meta_real_eval.core.config import Config
from meta_real_eval.rq2.corpus import (
    CorpusError,
    corpus_variant_ids,
    family_of,
    load_corpus,
    strip_fence,
    structural_gate,
    tasks_sha256,
    variant_id,
    variants_for_task,
    verify_corpus,
)

ORIGINAL = (
    'from typing import List\n'
    '\n'
    '\n'
    'def has_close_elements(numbers: List[float], threshold: float) -> bool:\n'
    '    """ Check if in given list of numbers, are any two numbers closer to each other\n'
    '    than given threshold.\n'
    '    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n'
    '    False\n'
    '    """\n'
)

ENTRY = "has_close_elements"


def gate(candidate, family="lexical", **kwargs):
    return structural_gate(ORIGINAL, candidate, ENTRY, family, **kwargs)


# ---------------------------------------------------------------------------
# Accepts
# ---------------------------------------------------------------------------

def test_accepts_a_genuine_reword():
    candidate = ORIGINAL.replace(
        " Check if in given list of numbers, are any two numbers closer to each other\n"
        "    than given threshold.",
        " Determine whether the supplied sequence contains a pair of values whose\n"
        "    separation falls below the supplied tolerance.",
    )
    assert gate(candidate) is None


def test_persona_family_may_prepend_framing():
    candidate = "You are reviewing sensor readings for duplicates.\n\n" + ORIGINAL
    assert gate(candidate, family="persona") is None


def test_reorder_family_may_move_examples_but_not_change_them():
    sig, _, _ = ORIGINAL.partition('"""')
    candidate = (
        sig + '""" >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n'
        '    False\n'
        '    Check if in given list of numbers, are any two numbers closer to each\n'
        '    other than given threshold.\n'
        '    """\n'
    )
    assert gate(candidate, family="reorder") is None


# ---------------------------------------------------------------------------
# Rejects — one case per reason
# ---------------------------------------------------------------------------

def test_rejects_byte_identical_no_op():
    # The defect this whole module exists for: a no-op prompt produces the same
    # cache key as `original`, so the cell replays original's completions and
    # scores tau_b = 1.0 without measuring anything.
    assert gate(ORIGINAL) == "identical_to_original"


def test_rejects_empty():
    assert gate("   \n") == "empty"


def test_rejects_changed_signature():
    candidate = ORIGINAL.replace("threshold: float", "tolerance: float")
    assert gate(candidate) == "signature_not_verbatim"


def test_rejects_renamed_function():
    candidate = ORIGINAL.replace(ENTRY, "find_close_pairs")
    assert gate(candidate) == "signature_not_verbatim"


def test_rejects_text_before_signature_outside_persona_family():
    candidate = "As a senior Python engineer, complete this:\n\n" + ORIGINAL
    assert gate(candidate, family="lexical") == "text_before_signature"


def test_rejects_dropped_example():
    candidate = ORIGINAL.replace(
        "    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n    False\n", ""
    )
    assert gate(candidate) == "examples_changed"


def test_rejects_altered_expected_output():
    candidate = ORIGINAL.replace("    False\n", "    True\n")
    assert gate(candidate) == "examples_changed"


TWO_EXAMPLES = (
    'def f(x: int) -> bool:\n'
    '    """ Say whether x is small.\n'
    '    >>> f(1)\n'
    '    True\n'
    '    >>> f(9)\n'
    '    False\n'
    '    """\n'
)


def test_swapping_example_order_is_rejected_outside_the_reorder_family():
    swapped = (
        'def f(x: int) -> bool:\n'
        '    """ Report whether x counts as small.\n'
        '    >>> f(9)\n'
        '    False\n'
        '    >>> f(1)\n'
        '    True\n'
        '    """\n'
    )
    assert structural_gate(TWO_EXAMPLES, swapped, "f", "lexical") == "examples_changed"
    # The reorder family is allowed to change the order — that is its whole point —
    # but not the content, which the multiset comparison still pins down.
    assert structural_gate(TWO_EXAMPLES, swapped, "f", "reorder") is None


def test_rejects_new_numeric_literal():
    candidate = ORIGINAL.replace(
        "than given threshold.",
        "than given threshold. The list has at least 7 elements.",
    )
    assert gate(candidate).startswith("new_numeric_literal:")


def test_rejects_unclosed_docstring():
    candidate = ORIGINAL.rstrip()[: -len('"""')]
    assert gate(candidate) == "does_not_parse"


def test_rejects_written_function_body():
    candidate = ORIGINAL + "    return False\n"
    # A body is not a specification; it hands the answer to the model under test.
    assert gate(candidate) is not None


def test_allows_a_statement_the_original_already_had_inside_the_function():
    # HumanEval/115 puts `import math` inside the function, ahead of its
    # docstring. A "docstring and nothing else" rule would reject every rewrite
    # of that task forever and silently starve it of variants, so the body is
    # compared against the original's own body instead.
    original = (
        'def max_fill(grid, capacity):\n'
        '    import math\n'
        '    """\n'
        '    Empty the wells.\n'
        '    """\n'
    )
    candidate = original.replace("Empty the wells.", "Drain every well.")
    assert structural_gate(original, candidate, "max_fill", "lexical") is None
    # A leaked implementation is still caught on that same shape.
    leaked = candidate.rstrip("\n") + "\n    return 0\n"
    assert structural_gate(original, leaked, "max_fill", "lexical") == "function_body_written"


def test_rejects_extra_def():
    candidate = ORIGINAL + '\n\ndef _helper(x):\n    """helper"""\n'
    assert gate(candidate) == "extra_def_introduced"


def test_rejects_duplicate_of_sibling():
    candidate = ORIGINAL.replace("Check if", "Determine whether")
    assert gate(candidate, seen={candidate}) == "duplicate_of_sibling"


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def test_strip_fence_unwraps_markdown():
    assert strip_fence("```python\ndef f():\n    pass\n```").strip() == "def f():\n    pass"


def test_strip_fence_leaves_unfenced_text_alone():
    assert strip_fence("def f():\n    pass\n") == "def f():\n    pass\n"


# ---------------------------------------------------------------------------
# Corpus file
# ---------------------------------------------------------------------------

def _corpus(tmp_path, n_per_family=3, families=("lexical", "terse")):
    corpus = {
        "manifest": {"corpus_version": "v1", "families": list(families),
                     "n_per_family": n_per_family},
        "tasks": {
            "HumanEval/0": {
                "original": ORIGINAL,
                "variants": [
                    {"variant_id": "llm_lexical_01", "family": "lexical",
                     "text": ORIGINAL.replace("Check if", "Determine whether"),
                     "validation": {"structural": "pass",
                                    "judge_verdict": "EQUIVALENT"}},
                ],
            }
        },
    }
    corpus["manifest"]["sha256"] = tasks_sha256(corpus)
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus), encoding="utf-8")
    return path, corpus


def test_variant_ids_come_from_the_manifest_not_from_the_tasks(tmp_path):
    # A task with a generation gap must not shorten the relation list for every
    # other task; the missing cell is recorded as missing, never imputed.
    path, _ = _corpus(tmp_path)
    ids = corpus_variant_ids(load_corpus(path))
    assert ids == [variant_id(f, i) for f in ("lexical", "terse") for i in (1, 2, 3)]
    assert list(variants_for_task(load_corpus(path), "HumanEval/0")) == ["llm_lexical_01"]


def test_variants_for_an_unknown_task_are_empty(tmp_path):
    path, _ = _corpus(tmp_path)
    assert variants_for_task(load_corpus(path), "HumanEval/999") == {}


def test_verify_corpus_accepts_the_pinned_hash(tmp_path):
    path, corpus = _corpus(tmp_path)
    verify_corpus(load_corpus(path), corpus["manifest"]["sha256"], path)


def test_verify_corpus_rejects_a_different_pinned_hash(tmp_path):
    path, _ = _corpus(tmp_path)
    with pytest.raises(CorpusError, match="corpus_sha256"):
        verify_corpus(load_corpus(path), "0" * 64, path)


def test_verify_corpus_detects_hand_editing(tmp_path):
    path, corpus = _corpus(tmp_path)
    corpus["tasks"]["HumanEval/0"]["variants"][0]["text"] = "tampered\n"
    path.write_text(json.dumps(corpus), encoding="utf-8")
    with pytest.raises(CorpusError, match="manifest"):
        verify_corpus(load_corpus(path), None, path)


def test_missing_corpus_names_the_generator_script(tmp_path):
    with pytest.raises(CorpusError, match="generate_paraphrases"):
        load_corpus(tmp_path / "absent.json")


def test_family_of_parses_variant_ids():
    assert family_of("llm_lexical_02") == "lexical"
    assert family_of("persona") is None
    assert family_of("original") is None


# ---------------------------------------------------------------------------
# Config wiring
# ---------------------------------------------------------------------------

def test_relations_are_derived_from_the_corpus(tmp_path):
    path, _ = _corpus(tmp_path)
    cfg = Config.model_validate({
        "rq2": {"paraphrase_corpus": str(path),
                "template_relations": ["persona", "terse"]},
    })
    assert cfg.rq2.relations == [
        "original", "control_resample", "persona", "terse",
        "llm_lexical_01", "llm_lexical_02", "llm_lexical_03",
        "llm_terse_01", "llm_terse_02", "llm_terse_03",
    ]


def test_relations_without_a_corpus_are_the_template_arm_only():
    cfg = Config.model_validate({"rq2": {}})
    assert cfg.rq2.relations == [
        "original", "control_resample", "persona", "formal", "reorder", "terse",
    ]


def test_control_resample_can_be_switched_off():
    cfg = Config.model_validate({"rq2": {"include_control_resample": False}})
    assert "control_resample" not in cfg.rq2.relations
