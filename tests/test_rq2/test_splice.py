"""Splice, don't ask: split_spec / assemble, and why they exist.

The v1 generation design asked the model to reproduce imports, any helper
function, the entry point's own def line, and the docstring's opening/closing
quotes byte for byte, alongside rewriting prose. A 2-task pilot on the 4
HumanEval tasks that define a helper function ahead of the entry point put 175
candidates through Gate A: 104 (59%) failed `signature_not_verbatim` and 12 (7%)
failed `text_before_signature` -- almost two thirds of all rejections came from
asking the model to retype code it never needed to touch.

v2 cuts that code out of the prompt (`split_spec`) and splices it back in
deterministically after the model rewrites only the docstring's prose and
examples (`assemble`). These tests are the decisive check for that design: the
split must round-trip to the original byte-for-byte on every prompt shape in
HumanEval, and the four rejection reasons split_spec targets must become
unreachable once generate_family runs through it (verified indirectly, via
structural_gate on assembled candidates, since assemble's whole point is that
Gate A never sees a hand-typed signature again).
"""

import pytest

from meta_real_eval.rq2.corpus import (
    _PERSONA_SENTINEL,
    _parse_persona_response,
    assemble,
    signature_prefix,
    split_spec,
    structural_gate,
)

ORDINARY = (
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

NO_IMPORT = (
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

# Shapes HumanEval/10, 32, 38, 50 actually have: a helper function (its own def,
# docstring, and body) defined ahead of the entry point.
HELPER_SIMPLE = (
    'def encode_cyclic(s: str):\n'
    '    """helper that groups elements in 3s"""\n'
    '    groups = [s[3 * i: min(len(s), 3 * i + 3)] for i in range((len(s) + 2) // 3)]\n'
    '    groups = [(group[1:] + group[0]) if len(group) == 3 else group for group in groups]\n'
    '    return "".join(groups)\n'
    '\n\n'
    'def decode_cyclic(s: str):\n'
    '    """\n'
    '    takes as input string encoded with encode_cyclic function. Returns decoded string.\n'
    '    """\n'
)

HELPER_MULTILINE_BODY = (
    'import math\n'
    '\n'
    '\n'
    'def poly(xs: list, x: float):\n'
    '    """\n'
    '    Evaluates polynomial with coefficients xs at point x.\n'
    '    """\n'
    '    return sum([coeff * math.pow(x, i) for i, coeff in enumerate(xs)])\n'
    '\n\n'
    'def find_zero(xs: list):\n'
    '    """ xs are coefficients of a polynomial.\n'
    '    >>> round(find_zero([1, 2]), 2)\n'
    '    -0.5\n'
    '    """\n'
)


# ---------------------------------------------------------------------------
# Round-trip: assemble(*split_spec(prompt)) == prompt, byte for byte
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prompt,entry_point", [
    (ORDINARY, "has_close_elements"),
    (NO_IMPORT, "make_palindrome"),
    (HELPER_SIMPLE, "decode_cyclic"),
    (HELPER_MULTILINE_BODY, "find_zero"),
])
def test_split_and_assemble_round_trip_exactly(prompt, entry_point):
    prefix, body, suffix = split_spec(prompt, entry_point)
    assert assemble(prefix, body, suffix) == prompt


def test_prefix_matches_signature_prefix():
    # split_spec must not duplicate signature_prefix's logic and risk the two
    # drifting apart -- it has to delegate to it.
    prefix, _, _ = split_spec(HELPER_MULTILINE_BODY, "find_zero")
    assert prefix == signature_prefix(HELPER_MULTILINE_BODY, "find_zero")


def test_suffix_is_the_closing_quotes_own_line():
    _, body, suffix = split_spec(ORDINARY, "has_close_elements")
    assert suffix == '    """\n'
    assert body.endswith("False\n")          # body ends cleanly, no dangling indent


def test_body_contains_the_doctest_examples():
    _, body, _ = split_spec(ORDINARY, "has_close_elements")
    assert ">>> has_close_elements([1.0, 2.0, 3.0], 0.5)" in body
    assert "False" in body


# ---------------------------------------------------------------------------
# assemble()
# ---------------------------------------------------------------------------

def test_assemble_adds_a_missing_trailing_newline_to_body():
    prefix, body, suffix = split_spec(ORDINARY, "has_close_elements")
    truncated = body.rstrip("\n")   # simulate a model response with no trailing newline
    assert assemble(prefix, truncated, suffix) == assemble(prefix, body, suffix)


def test_assemble_with_framing_prepends_it_before_the_prefix():
    prefix, body, suffix = split_spec(ORDINARY, "has_close_elements")
    out = assemble(prefix, body, suffix, framing="You are on call tonight.")
    assert out.startswith("You are on call tonight.\n\n" + prefix)


def test_assemble_without_framing_never_adds_a_preamble():
    prefix, body, suffix = split_spec(ORDINARY, "has_close_elements")
    assert assemble(prefix, body, suffix) == prefix + body + suffix
    assert assemble(prefix, body, suffix, framing="") == prefix + body + suffix


# ---------------------------------------------------------------------------
# Persona sentinel parsing
# ---------------------------------------------------------------------------

def test_parse_persona_response_splits_on_the_sentinel():
    raw = f"You are a night-shift engineer.\n{_PERSONA_SENTINEL}\nRewritten docstring text."
    framing, body = _parse_persona_response(raw)
    assert framing == "You are a night-shift engineer."
    assert body == "\nRewritten docstring text."


def test_parse_persona_response_without_sentinel_yields_an_empty_body():
    # Guessing which part is framing and which is body would risk splicing
    # framing text in as if it were the rewritten docstring; an empty body is
    # caught downstream by Gate A (rejected as "empty") instead.
    framing, body = _parse_persona_response("just some text, no marker")
    assert body == ""
    assert framing == "just some text, no marker"


# ---------------------------------------------------------------------------
# The rejection reasons split_spec targets become unreachable through assemble
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prompt,entry_point", [
    (ORDINARY, "has_close_elements"),
    (NO_IMPORT, "make_palindrome"),
    (HELPER_SIMPLE, "decode_cyclic"),
    (HELPER_MULTILINE_BODY, "find_zero"),
])
def test_assembled_candidate_never_fails_on_the_spliced_parts(prompt, entry_point):
    """A rewrite of body ALONE, spliced back in, must never trip
    signature_not_verbatim / text_before_signature / extra_def_introduced /
    function_body_written -- those checks are now only reachable if assemble()
    or split_spec() themselves have a bug, not from anything a generator model
    does to the prose."""
    prefix, body, suffix = split_spec(prompt, entry_point)
    rewritten_body = body.replace("a", "4")   # touch the prose, however badly
    candidate = assemble(prefix, rewritten_body, suffix)
    reason = structural_gate(prompt, candidate, entry_point, "lexical")
    assert reason not in (
        "signature_not_verbatim", "text_before_signature",
        "extra_def_introduced", "function_body_written",
    )


def test_persona_framing_is_the_only_way_to_add_a_preamble():
    prefix, body, suffix = split_spec(ORDINARY, "has_close_elements")
    with_framing = assemble(prefix, body, suffix, framing="A scenario.")
    # Every other family calls assemble() with no framing, so this reason can
    # only ever fire for persona, and never through a code path that supplies one.
    assert structural_gate(ORDINARY, with_framing, "has_close_elements",
                           "lexical") == "text_before_signature"
    assert structural_gate(ORDINARY, with_framing, "has_close_elements",
                           "persona") != "text_before_signature"


def test_a_def_smuggled_into_the_rewritten_body_is_still_caught():
    # extra_def_introduced stays a real defensive check: nothing about the
    # splice prevents a model from writing a `def` inside its rewritten prose.
    prefix, body, suffix = split_spec(ORDINARY, "has_close_elements")
    smuggled = body + "\n\ndef sneaky():\n    pass\n"
    candidate = assemble(prefix, smuggled, suffix)
    assert structural_gate(ORDINARY, candidate, "has_close_elements",
                           "lexical") == "extra_def_introduced"
