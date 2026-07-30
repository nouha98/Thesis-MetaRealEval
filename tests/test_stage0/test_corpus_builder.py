"""Tests for traditional mutant generation."""

import pytest
from meta_real_eval.stage0.corpus_builder import generate_mutants


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
