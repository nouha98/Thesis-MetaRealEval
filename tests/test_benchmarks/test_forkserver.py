"""D6 invariant tests: isolated scenario execution (plan review #15).

Parametrised over every execution mode this platform supports. ``fork`` only
exists on POSIX, so on Windows these exercise ``single`` mode and the
fork-specific tests are skipped -- they must also be run on the Linux
cluster, where fork is the production mode.
"""

from __future__ import annotations

import os

import pytest

from meta_real_eval.benchmarks.forkserver import run_scenarios
from meta_real_eval.benchmarks.observe import traces_agree
from meta_real_eval.benchmarks.scenarios import extract_scenarios

MODES = ["single"] + (["fork"] if hasattr(os, "fork") else [])
needs_fork = pytest.mark.skipif(not hasattr(os, "fork"), reason="fork mode needs POSIX")

MODULE = "snippet_1"

REFERENCE = '''\
class Counter:
    registry = []

    def __init__(self, start=0):
        self.count = start

    def add(self, n):
        if n < 0:
            raise ValueError("negative")
        self.count += n

    def f(self, x):
        return x + 1
'''

# Return values identical to the reference everywhere; only internal state
# differs. Detectable only through the end-of-scenario state snapshot.
STATE_ONLY_MUTANT = REFERENCE.replace("self.count += n", "self.count += n * 2")
RETURN_MUTANT = REFERENCE.replace("return x + 1", "return x + 2")

TESTS = '''\
import pytest
import snippet_1 as module_0


def test_case_0():
    counter_0 = module_0.Counter(3)
    var_0 = counter_0.f(10)
    assert var_0 == 11


def test_case_1():
    counter_0 = module_0.Counter(1)
    var_0 = counter_0.add(5)
    assert var_0 is None


def test_case_2():
    counter_0 = module_0.Counter(1)
    with pytest.raises(ValueError):
        counter_0.add(-5)
    var_0 = counter_0.f(0)
'''


def _run(code, tests=TESTS, mode="single", timeout_s=10.0):
    header, scs = extract_scenarios(tests, MODULE)
    return run_scenarios(MODULE, code, header, scs, timeout_s=timeout_s, mode=mode)


@pytest.mark.parametrize("mode", MODES)
def test_reference_traces_are_stable_across_runs(mode):
    assert _run(REFERENCE, mode=mode) == _run(REFERENCE, mode=mode)


@pytest.mark.parametrize("mode", MODES)
def test_differential_sanity_return_value(mode):
    ref, mut = _run(REFERENCE, mode=mode), _run(RETURN_MUTANT, mode=mode)
    assert not traces_agree(ref[0]["tokens"], mut[0]["tokens"])   # scenario calls f
    assert traces_agree(ref[1]["tokens"], mut[1]["tokens"])       # scenario never calls f


@pytest.mark.parametrize("mode", MODES)
def test_state_only_mutant_detected_by_state_snapshot(mode):
    ref, mut = _run(REFERENCE, mode=mode), _run(STATE_ONLY_MUTANT, mode=mode)
    r, m = ref[1]["tokens"], mut[1]["tokens"]
    # add() returns None in both: the step observation agrees...
    assert r["s1"] == m["s1"]
    # ...but the object's end state does not.
    assert r["end:counter_0"] != m["end:counter_0"]
    assert not traces_agree(r, m)


@pytest.mark.parametrize("mode", MODES)
def test_raises_step_continues_on_matching_exception(mode):
    trace = _run(REFERENCE, mode=mode)[2]
    assert trace["tokens"]["s1"] == "EXC:builtins.ValueError"
    assert "s2" in trace["tokens"]  # execution continued past the raises block


@pytest.mark.parametrize("mode", MODES)
def test_raises_step_stops_when_no_exception(mode):
    no_raise = REFERENCE.replace('raise ValueError("negative")', "pass")
    trace = _run(no_raise, mode=mode)[2]
    assert trace["tokens"]["s1"].startswith("NO_EXC:")
    assert "s2" not in trace["tokens"]


@pytest.mark.parametrize("mode", MODES)
def test_scenarios_are_isolated_from_each_other(mode):
    """Scenario A mutates a *class attribute*; scenario B must still see the
    freshly imported state, whichever order they run in."""
    tests = '''\
import snippet_1 as module_0


def test_mutates():
    var_0 = module_0.Counter.registry.append(1)


def test_observes():
    var_0 = len(module_0.Counter.registry)
'''
    traces = _run(REFERENCE, tests=tests, mode=mode)
    assert traces[1]["tokens"]["s0"] == "VALUE:builtins.int:0"


@pytest.mark.parametrize("mode", MODES)
def test_timeout_is_reported_and_does_not_affect_other_scenarios(mode):
    hangs = REFERENCE.replace("return x + 1", "while True:\n            pass")
    traces = _run(hangs, mode=mode, timeout_s=2.0)
    assert traces[0]["status"] == "timeout"      # scenario 0 calls f
    assert traces[1]["status"] == "ok"           # scenario 1 does not


@pytest.mark.parametrize("mode", MODES)
def test_import_error_is_an_observation_not_a_crash(mode):
    traces = _run("raise ImportError('missing dependency')\n", mode=mode)
    assert all(t["status"] == "import_error" for t in traces)
    assert traces[0]["tokens"]["import"] == "EXC:builtins.ImportError"


@needs_fork
def test_fork_and_fresh_process_traces_are_identical():
    """The M1 identity check, on a fixture: fork mode must be observationally
    equivalent to a completely fresh process, for the reference and mutants."""
    for code in (REFERENCE, RETURN_MUTANT, STATE_ONLY_MUTANT):
        fork = [{k: v for k, v in t.items() if k != "threads_at_fork"} for t in _run(code, mode="fork")]
        assert fork == _run(code, mode="single")


@needs_fork
def test_fork_records_threads_at_fork():
    traces = _run(REFERENCE, mode="fork")
    assert all(t["threads_at_fork"] == 1 for t in traces)
