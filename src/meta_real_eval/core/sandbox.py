"""Sandboxed code execution via subprocess."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


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


# ---------------------------------------------------------------------------
# Class-level (Tier 2 / RealClassEval) execution: pytest, not a single assert
# block. This is additive -- execute() and build_test_driver() above are
# untouched, so Tier 1 results cannot be affected by anything below.
#
# The one raw fact this module hands upward is "what did pytest itself say
# happened to this test, in this phase, and what exception (if any) escaped
# to it". D1's six-outcome vocabulary -- ordinary_pass / expected_exception /
# ordinary_fail / unexpected_pass / error / timeout -- is a classification of
# these raw facts, and lives in benchmarks/outcomes.py, not here, so this
# module stays a dumb, reusable "run pytest, tell me what happened" primitive.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawTestReport:
    """One phase of one test, exactly as the conftest hook observed it.

    ``pytest_outcome``/``when`` are pytest's own vocabulary (outcome one of
    "passed"/"failed"/"skipped"; when one of "setup"/"call"/"teardown").
    ``wasxfail`` mirrors ``TestReport.wasxfail``: present (even as the empty
    string) for a report pytest's xfail machinery touched, absent (None)
    otherwise -- note this is *not* the same as the test having an xfail
    *marker*; a marker only produces a ``wasxfail`` report when the test
    actually raised (see benchmarks/outcomes.py for why XPASS(strict) shows
    up as wasxfail=None despite the marker being present, confirmed against
    the installed pytest empirically).
    ``exc_type`` is the fully-qualified name of whatever exception escaped to
    pytest during this phase (``call.excinfo``), or None if nothing did --
    including when the test's own ``with pytest.raises(...):`` caught it
    first, which never reaches this hook at all.
    """

    nodeid: str
    when: str
    pytest_outcome: str
    wasxfail: Optional[str] = None
    exc_type: Optional[str] = None


@dataclass
class PytestRunResult:
    reports: dict[str, list[RawTestReport]] = field(default_factory=dict)
    timed_out_nodeids: set[str] = field(default_factory=set)
    stdout: str = ""
    stderr: str = ""


# Reads MRE_OUTCOME_LOG at *runtime* (inside the subprocess), so this string
# needs no per-call formatting and can never collide with braces in the
# solution/test source it sits alongside.
_CONFTEST_SOURCE = '''\
import json
import os

import pytest

_LOG_PATH = os.environ["MRE_OUTCOME_LOG"]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    exc_type = None
    if call.excinfo is not None:
        exc_type = f"{call.excinfo.type.__module__}.{call.excinfo.type.__qualname__}"
    record = {
        "nodeid": report.nodeid,
        "when": report.when,
        "pytest_outcome": report.outcome,
        "wasxfail": getattr(report, "wasxfail", None),
        "exc_type": exc_type,
    }
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\\n")
    return report
'''


def execute_pytest(
    module_name: str,
    solution_code: str,
    test_code: str,
    timeout_s: float = 30.0,
    select: Optional[list[str]] = None,
) -> PytestRunResult:
    """Run ``test_code`` against ``solution_code`` under pytest, in a fresh dir.

    ``module_name`` is what the test file imports (Pynguin suites do
    ``import snippet_N as module_0``, so this is ``"snippet_N"``).
    ``select`` is a list of test *function names* to run. A name that never
    reaches a "call"-phase report is recorded in ``timed_out_nodeids`` only
    if the subprocess was actually killed by ``timeout_s``; a missing report
    from a quick collection error (e.g. the solution fails to import) is left
    out of it, so callers classify that name as an error rather than a
    timeout (see ``benchmarks.outcomes.classify``).

    Note: pytest runs a single file's tests in one process, in source order.
    If an early test hangs, every test after it never runs and is *also*
    reported as timed out here -- callers that need one hang to only affect
    one test must call this with ``select=[that_one_name]``.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / f"{module_name}.py").write_text(solution_code, encoding="utf-8")
        test_filename = f"test_{module_name}.py"
        (tmp_path / test_filename).write_text(test_code, encoding="utf-8")
        (tmp_path / "conftest.py").write_text(_CONFTEST_SOURCE, encoding="utf-8")
        log_path = tmp_path / "outcomes.jsonl"

        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MRE_OUTCOME_LOG": str(log_path)}
        args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        if select:
            args += [f"{test_filename}::{name}" for name in select]
        else:
            args += [test_filename]

        stdout = stderr = ""
        process_timed_out = False
        try:
            proc = subprocess.run(args, cwd=tmp_path, capture_output=True,
                                  timeout=timeout_s, env=env)
            stdout = proc.stdout.decode(errors="replace")
            stderr = proc.stderr.decode(errors="replace")
        except subprocess.TimeoutExpired as e:
            stdout = (e.stdout or b"").decode(errors="replace")
            stderr = (e.stderr or b"").decode(errors="replace")
            process_timed_out = True

        reports: dict[str, list[RawTestReport]] = {}
        if log_path.exists():
            for line in log_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                reports.setdefault(rec["nodeid"], []).append(RawTestReport(**rec))

        # "No report at all" is not by itself evidence of a timeout -- a
        # collection error (e.g. the solution fails to import) also leaves a
        # name with zero reports, and finishes in well under timeout_s. Only
        # a name that never reached its "call" phase *and* the process was
        # actually killed by the timeout counts as TIMEOUT; everything else
        # with no call-phase report is an ERROR (see outcomes.classify).
        timed_out: set[str] = set()
        if process_timed_out and select:
            reached_call = {
                nodeid.rsplit("::", 1)[-1]
                for nodeid, phase_reports in reports.items()
                if any(r.when == "call" for r in phase_reports)
            }
            timed_out = {name for name in select if name not in reached_call}

        return PytestRunResult(reports=reports, timed_out_nodeids=timed_out,
                               stdout=stdout, stderr=stderr)
