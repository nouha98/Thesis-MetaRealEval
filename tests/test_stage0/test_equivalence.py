"""Tests for Stage 0's differential-execution equivalence check."""

import random

from meta_real_eval.core.data_loader import HumanEvalTask
from meta_real_eval.stage0.corpus_builder import Mutant
from meta_real_eval.stage0.equivalence import (
    _CAPTURE_CACHE,
    _capture_test_inputs,
    _error_signature,
    _extract_test_inputs,
    _mutate_str,
    _run_one,
    _string_pool,
    check_equivalence,
)


# ---------------------------------------------------------------------------
# _error_signature
# ---------------------------------------------------------------------------
#
# Regression: every Python traceback opens with the same ~60-char boilerplate
# regardless of exception type, so comparing stderr[:60] (the old behaviour)
# made a mutant raising IndexError compare equal to a canonical solution
# raising ZeroDivisionError on the same input -- a real divergence silently
# read as "no divergence".

def _traceback_for(code: str) -> str:
    import subprocess
    import sys
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert proc.returncode != 0, "expected the snippet to raise"
    return proc.stderr.decode(errors="replace")


def test_error_signature_distinguishes_different_exception_types():
    zde = _traceback_for("1 / 0")
    ie = _traceback_for("[1, 2, 3][10]")
    assert _error_signature(zde) != _error_signature(ie)


def test_error_signature_is_the_last_nonblank_line():
    tb = _traceback_for("1 / 0")
    assert _error_signature(tb) == "ZeroDivisionError: division by zero"


def test_error_signature_handles_blank_stderr():
    assert _error_signature("") == ""
    assert _error_signature("   \n  \n") == ""


# ---------------------------------------------------------------------------
# End-to-end: check_equivalence must not misclassify a different-exception
# mutant as equivalent.
# ---------------------------------------------------------------------------

def test_mutant_raising_a_different_exception_is_not_equivalent(monkeypatch):
    task = HumanEvalTask(
        task_id="Synthetic/0", task_index=0,
        prompt="def f(a, b):\n",
        canonical_solution="    return a // b\n",  # ZeroDivisionError when b == 0
        test="def check(candidate):\n    pass\n",
        entry_point="f",
    )
    # Always raises IndexError -- a completely different failure mode from
    # the canonical solution's ZeroDivisionError on the same input.
    mutant = Mutant(
        mutant_id="X_0", operator="AOR", description="synthetic",
        code="def f(a, b):\n    return [1, 2, 3][100]\n",
    )

    # Pin the single fuzz input to the divide-by-zero case regardless of the
    # real input generator's own logic -- this test is about the comparison,
    # not about input generation.
    monkeypatch.setattr(
        "meta_real_eval.stage0.equivalence._generate_inputs",
        lambda task, n, seed: [(5, 0)],
    )

    canonical_code = task.prompt + task.canonical_solution
    canon_out = _run_one(canonical_code, task.entry_point, (5, 0), timeout_s=5.0)
    assert canon_out.startswith("__error__:")

    result = check_equivalence(
        task, mutant, n_fuzz_inputs=1, timeout_s=5.0, seed=42,
        canon_outs=[canon_out],
    )
    assert result.is_equivalent is False
    assert result.reason == "diverged"
    # The verdict records which input settled it, so it can be re-examined
    # later without re-deriving the seeded input stream.
    assert result.diverging_input == repr((5, 0))


# ---------------------------------------------------------------------------
# Input capture
# ---------------------------------------------------------------------------
#
# Regression: _extract_test_inputs scrapes literal argument tuples out of the
# check() source, so it recovers nothing when the argument is an expression.
# HumanEval/32, /38 and /50 pass the result of a helper defined in the prompt,
# leaving their equivalence verdicts resting entirely on random padding -- which
# is how mutants that the suite demonstrably kills were filed as "equivalent".

_HELPER_TASK = HumanEvalTask(
    task_id="Synthetic/capture", task_index=0,
    prompt="def encode(s):\n    return s[::-1]\n\n\ndef decode(s):\n",
    canonical_solution="    return s[::-1]\n",
    test=(
        "def check(candidate):\n"
        "    for word in ['alpha', 'beta', 'gamma']:\n"
        "        encoded = encode(word)\n"
        "        assert candidate(encoded) == word\n"
    ),
    entry_point="decode",
)


def test_capture_recovers_inputs_the_regex_scraper_cannot():
    _CAPTURE_CACHE.clear()

    scraped = _extract_test_inputs(_HELPER_TASK.test, _HELPER_TASK.entry_point)
    captured = _capture_test_inputs(_HELPER_TASK)

    assert scraped == []                      # the old path sees nothing at all
    assert captured == [("ahpla",), ("ateb",), ("ammag",)]


def test_capture_is_deterministic_for_a_random_check():
    """check() bodies that draw random inputs must still capture reproducibly."""
    task = HumanEvalTask(
        task_id="Synthetic/random", task_index=0,
        prompt="def f(n):\n", canonical_solution="    return n * 2\n",
        test=("def check(candidate):\n"
              "    import random\n"
              "    for _ in range(5):\n"
              "        assert candidate(random.randint(0, 10**6)) is not None\n"),
        entry_point="f",
    )
    _CAPTURE_CACHE.clear()
    first = _capture_test_inputs(task, seed=42)
    _CAPTURE_CACHE.clear()
    again = _capture_test_inputs(task, seed=42)
    _CAPTURE_CACHE.clear()
    other = _capture_test_inputs(task, seed=7)

    assert first == again                     # same seed, same inputs
    assert first != other                     # and the seed actually drives it


def test_capture_keeps_only_replayable_arguments():
    """_run_one replays an input via repr(), so non-round-trippable args are dropped."""
    task = HumanEvalTask(
        task_id="Synthetic/object", task_index=0,
        prompt="def f(x):\n", canonical_solution="    return 1\n",
        test=("def check(candidate):\n"
              "    candidate(object())\n"       # repr is <object object at 0x...>
              "    candidate(7)\n"),
        entry_point="f",
    )
    _CAPTURE_CACHE.clear()
    assert _capture_test_inputs(task) == [(7,)]


# ---------------------------------------------------------------------------
# Structure-aware padding
# ---------------------------------------------------------------------------
#
# Regression: _random_str draws from "a-z 0-9", which contains no bracket, dot
# or dash, so padding inputs for a bracket-matching or date-parsing task all
# take the same early-exit path and cannot distinguish any mutant.

def test_string_pool_reaches_inside_containers():
    assert sorted(_string_pool([(["()(", ")"],), ("ab",)])) == ["()(", ")", "ab"]


def test_mutated_strings_stay_in_the_example_alphabet():
    rng = random.Random(0)
    alphabet = set("()")
    for _ in range(50):
        assert set(_mutate_str("(()", rng)) <= alphabet
