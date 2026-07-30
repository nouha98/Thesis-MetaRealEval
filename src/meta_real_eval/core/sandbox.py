"""Sandboxed code execution via subprocess."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field


@dataclass
class ExecutionResult:
    passed: bool
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


def execute(solution_code: str, test_code: str, timeout_s: float = 10.0) -> ExecutionResult:
    """Run solution_code followed by test_code in an isolated subprocess.

    The test is expected to raise an exception on failure (e.g. AssertionError).
    A non-zero exit code → not passed.  Timeout → timed_out=True, not passed.

    We pass the full os.environ so the subprocess can find the Python stdlib and
    any installed packages, but add PYTHONDONTWRITEBYTECODE to keep things clean.
    """
    combined = solution_code + "\n" + test_code
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    try:
        proc = subprocess.run(
            [sys.executable, "-c", combined],
            capture_output=True,
            timeout=timeout_s,
            env=env,
        )
        return ExecutionResult(
            passed=proc.returncode == 0,
            stdout=proc.stdout.decode(errors="replace"),
            stderr=proc.stderr.decode(errors="replace"),
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(passed=False, timed_out=True)


def build_test_driver(task_prompt: str, solution_body: str, test_block: str, entry_point: str) -> tuple[str, str]:
    """Return (solution_code, test_code) ready to pass to execute().

    solution_code = prompt (signature + docstring) + solution_body
    test_code     = test_block + newline + check(entry_point) call
    """
    solution_code = task_prompt + solution_body
    test_code = test_block + f"\ncheck({entry_point})\n"
    return solution_code, test_code
