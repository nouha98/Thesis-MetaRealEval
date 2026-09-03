"""Tests for Stage 0's differential-execution equivalence check."""

from meta_real_eval.core.data_loader import HumanEvalTask
from meta_real_eval.stage0.corpus_builder import Mutant
from meta_real_eval.stage0.equivalence import (
    _error_signature,
    _run_one,
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
