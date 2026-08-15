"""Tests for traditional mutant generation."""

import ast

import pytest
from meta_real_eval.stage0.corpus_builder import _cmp_slots, generate_mutants


def test_generates_mutants_for_simple_function():
    prompt = "def add(a, b):\n"
    solution = "    return a + b\n"
    mutants = generate_mutants(prompt, solution, "add", operators=["AOR", "ROR", "SDL"])
    assert len(mutants) >= 1


def test_mutant_ids_are_unique():
    prompt = "def add(a, b):\n"
    solution = "    return a + b\n"
    mutants = generate_mutants(prompt, solution, "add", operators=["AOR"])
    ids = [m.mutant_id for m in mutants]
    assert len(ids) == len(set(ids))


def test_sdl_mutant_shorter_than_original():
    prompt = "def foo(x):\n"
    solution = "    y = x + 1\n    z = y * 2\n    return z\n"
    mutants = generate_mutants(prompt, solution, "foo", operators=["SDL"])
    sdl = [m for m in mutants if m.operator == "SDL"]
    assert len(sdl) >= 1
    for m in sdl:
        assert len(m.code) < len(prompt + solution) + 10  # roughly smaller


def test_empty_solution_returns_empty():
    mutants = generate_mutants("", "", "foo", operators=["AOR"])
    assert mutants == []


def test_operators_filter():
    prompt = "def compare(a, b):\n"
    solution = "    return a < b\n"
    aor_only = generate_mutants(prompt, solution, "compare", operators=["AOR"])
    ror_only = generate_mutants(prompt, solution, "compare", operators=["ROR"])
    assert all(m.operator == "AOR" for m in aor_only)
    assert all(m.operator == "ROR" for m in ror_only)


def test_ror_mutates_every_distinct_site_not_just_the_first():
    """Regression: site selection used to be discarded, retargeting the first
    type-matching comparison, so the second `<` here was never mutated."""
    prompt = "def f(a, b, c, d):\n"
    solution = "    x = a < b\n    y = c < d\n    return x and y\n"
    mutants = generate_mutants(prompt, solution, "f", operators=["ROR"], max_per_operator=2)

    original = ast.parse(prompt + solution)
    changed = set()
    for m in mutants:
        mutated = ast.parse(m.code)
        for i, ((na, ia), (nb, ib)) in enumerate(zip(_cmp_slots(original), _cmp_slots(mutated))):
            if type(na.ops[ia]) is not type(nb.ops[ib]):
                changed.add(i)
    assert changed == {0, 1}, f"expected both comparison sites mutated, got {changed}"


def test_ror_produces_no_duplicate_code():
    prompt = "def f(a, b, c, d):\n"
    solution = "    x = a < b\n    y = c < d\n    return x and y\n"
    mutants = generate_mutants(prompt, solution, "f", operators=["ROR"])
    codes = [m.code for m in mutants]
    assert len(codes) == len(set(codes))


def test_sdl_never_deletes_the_docstring():
    """A docstring deletion is equivalent by construction — it must not reach
    the corpus, where it would consume a differential-fuzzing run to prove so."""
    prompt = 'def f(x):\n    """Doc."""\n'
    solution = "    y = x + 1\n    return y\n"
    mutants = generate_mutants(prompt, solution, "f", operators=["SDL"])
    assert mutants, "expected some SDL mutants"
    for m in mutants:
        assert '"""Doc."""' in m.code or "'Doc.'" in m.code, \
            f"docstring was deleted: {m.description}"


def test_sdl_description_records_statement_kind():
    prompt = "def f(x):\n"
    solution = "    y = x + 1\n    return y\n"
    mutants = generate_mutants(prompt, solution, "f", operators=["SDL"])
    kinds = {m.description.split("Delete ")[1].split(" statement")[0] for m in mutants}
    assert kinds <= {"Assign", "Return"} and kinds, kinds


def test_no_mutant_is_identical_to_the_original():
    prompt = "def f(a, b):\n"
    solution = "    return a + b\n"
    original = ast.unparse(ast.parse(prompt + solution))
    mutants = generate_mutants(prompt, solution, "f", operators=["AOR", "ROR", "SDL"])
    assert all(m.code != original for m in mutants)
