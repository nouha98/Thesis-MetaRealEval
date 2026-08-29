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
    _normalize,
    corpus_variant_ids,
    family_of,
    load_corpus,
    signature_prefix,
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

NO_IMPORT_ORIGINAL = (
    '\n\n'
    'def is_palindrome(string: str) -> bool:\n'
    '    """ Test if given string is a palindrome """\n'
    '    return string == string[::-1]\n'
    '\n\n'
    'def make_palindrome(string: str) -> str:\n'
    '    """ Find the shortest palindrome that begins with a supplied string.\n'
    '    >>> make_palindrome(\'cat\')\n'
    '    \'catac\'\n'
    '    """\n'
)


def test_accepts_a_rewrite_of_a_task_with_no_import_statement():
    # 45 of 164 HumanEval prompts have no import and so open with a blank line
    # (verified: `t.prompt.startswith("\n\n")` for 45/164). A chat completion
    # reliably drops that leading blank line as a response-formatting artifact
    # regardless of what the original has (confirmed live against
    # soofi-s-isar-preview) — this must not read as a changed specification.
    # The rewrite touches only the entry point's own docstring — is_palindrome
    # is a helper here, and changing *its* text is a separate invariant
    # (test_signature_prefix_anchors_on_the_entry_point_not_the_first_quote).
    candidate = NO_IMPORT_ORIGINAL.lstrip("\n").replace(
        "Find the shortest palindrome that begins with a supplied string.",
        "Build the shortest palindrome sharing the given string as a prefix.",
    )
    assert structural_gate(NO_IMPORT_ORIGINAL, candidate, "make_palindrome",
                           "lexical") is None


def test_true_no_op_is_still_caught_even_with_leading_blank_line_stripped():
    # The other direction of the same bug: a candidate that is a genuine no-op
    # except for having lost the original's leading blank line must still be
    # rejected — that dropped blank line must not be enough to make it read as
    # "changed".
    stripped_no_op = NO_IMPORT_ORIGINAL.lstrip("\n")
    assert structural_gate(NO_IMPORT_ORIGINAL, stripped_no_op, "make_palindrome",
                           "lexical") == "identical_to_original"


def test_accepts_a_rewrite_that_collapses_blank_lines_between_defs():
    # PEP8 spacing between top-level defs (two blank lines) routinely comes back
    # as one blank line from a chat completion — a formatting artifact, not a
    # content change (confirmed live: reproducible on HumanEval/10). Again, the
    # rewrite touches only the entry point's own docstring.
    original = NO_IMPORT_ORIGINAL.lstrip("\n")
    candidate = original.replace("\n\n\ndef make_palindrome", "\n\ndef make_palindrome")
    candidate = candidate.replace(
        "Find the shortest palindrome that begins with a supplied string.",
        "Build the shortest palindrome sharing the given string as a prefix.",
    )
    assert candidate != original
    assert structural_gate(original, candidate, "make_palindrome", "lexical") is None


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


def test_signature_prefix_anchors_on_the_entry_point_not_the_first_quote():
    # 5 of 164 HumanEval tasks (e.g. HumanEval/32) define a helper function --
    # with its own docstring -- before the entry point. The first `"""` in the
    # prompt then belongs to the helper, not the entry point, so anchoring there
    # would take the helper's docstring as "the signature" and reject every
    # rewrite of these 5 tasks as text_before_signature, forever.
    original = (
        'import math\n\n\n'
        'def helper(x):\n'
        '    """A private helper, not the task."""\n'
        '    return x\n\n\n'
        'def entry(y):\n'
        '    """ The real specification.\n'
        '    >>> entry(1)\n'
        '    1\n'
        '    """\n'
    )
    prefix = signature_prefix(original, "entry")
    # The prefix must reach entry's own docstring open, not stop at helper's --
    # the old code anchored on the first `"""` in the whole prompt, which
    # belongs to helper, and would have truncated the prefix there.
    assert prefix.endswith('def entry(y):\n    """')
    assert prefix.count('"""') == 3          # helper's pair, plus entry's open

    candidate = original.replace("The real specification.", "The actual spec.")
    assert structural_gate(original, candidate, "entry", "lexical") is None


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
    # `seen` holds normalised strings (generate_family populates it that way —
    # see _normalize), so a caller must normalise before adding, not pass the
    # raw text as generated.
    assert gate(candidate, seen={_normalize(candidate)}) == "duplicate_of_sibling"


def test_seen_check_is_insensitive_to_blank_line_count():
    # Two candidates differing only in how many blank lines separate the
    # import from the def are the same rewrite in substance; generate_family's
    # dedup must catch that, not just literal byte-identity.
    candidate = ORIGINAL.replace("Check if", "Determine whether")
    fewer_blank_lines = candidate.replace("\n\n\ndef", "\n\ndef")
    assert fewer_blank_lines != candidate
    assert gate(fewer_blank_lines, seen={_normalize(candidate)}) == "duplicate_of_sibling"


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


# ---------------------------------------------------------------------------
# Blank lines between an example and its output are formatting, not a change
# ---------------------------------------------------------------------------

def test_a_blank_line_before_the_expected_output_is_not_an_example_change():
    """`examples_changed` was the single most common Gate A rejection in the
    pilot, and this shape was one of the ways to earn it spuriously: the
    expected-output line was read only from the immediately following line, so a
    rewrite that spaced its examples out lost that line from *its* list alone and
    failed the comparison.  Skipping blanks is a no-op on all 164 original
    HumanEval prompts, so it removes the false rejection without loosening the
    real check -- which the next test pins down."""
    spaced = (
        'def f(x: int) -> bool:\n'
        '    """ Report whether x counts as small.\n'
        '    >>> f(1)\n'
        '\n'
        '    True\n'
        '\n'
        '    >>> f(9)\n'
        '\n'
        '    False\n'
        '    """\n'
    )
    assert structural_gate(TWO_EXAMPLES, spaced, "f", "lexical") is None


def test_blank_line_tolerance_does_not_hide_an_altered_output():
    spaced_and_wrong = (
        'def f(x: int) -> bool:\n'
        '    """ Report whether x counts as small.\n'
        '    >>> f(1)\n'
        '\n'
        '    False\n'
        '    >>> f(9)\n'
        '\n'
        '    False\n'
        '    """\n'
    )
    assert structural_gate(TWO_EXAMPLES, spaced_and_wrong, "f",
                           "lexical") == "examples_changed"
