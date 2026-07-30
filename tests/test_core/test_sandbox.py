"""Tests for sandboxed code execution."""

import pytest
from meta_real_eval.core.sandbox import execute, build_test_driver


def test_passing_code():
    result = execute("x = 1 + 1", "assert x == 2")
    assert result.passed


def test_failing_code():
    result = execute("x = 1", "assert x == 99")
    assert not result.passed


def test_syntax_error_in_code():
    result = execute("def bad syntax:", "")
    assert not result.passed


def test_timeout():
    result = execute("while True: pass", "", timeout_s=0.5)
    assert not result.passed
    assert result.timed_out


def test_canonical_humaneval_style(simple_task):
    """End-to-end: canonical solution passes the test."""
    solution_code = simple_task.prompt + simple_task.canonical_solution
    test_code = simple_task.test + f"\ncheck({simple_task.entry_point})\n"
    result = execute(solution_code, test_code)
    assert result.passed


def test_wrong_solution_fails(simple_task):
    """A deliberately broken solution is caught by the test."""
    broken_body = "    return a - b\n"  # subtraction instead of addition
    solution_code = simple_task.prompt + broken_body
    test_code = simple_task.test + f"\ncheck({simple_task.entry_point})\n"
    result = execute(solution_code, test_code)
    assert not result.passed
