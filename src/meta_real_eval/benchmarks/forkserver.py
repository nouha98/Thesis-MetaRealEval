"""D6: isolated scenario execution (see the Tier 2 plan, "D6").

Two modes, meant to be observationally identical:

``fork``   (Linux compute nodes) One runner process imports the
           implementation once -- by executing the test file's import header
           -- then ``os.fork()``s a child per scenario. The child runs the
           scenario on a copy-on-write copy of the freshly imported state,
           writes its trace to a pipe and exits, so scenario B can never see
           scenario A's mutations (instances, class attributes, module
           globals). A timeout SIGKILLs the child.
           Invariant: the runner executes no scenario and starts no threads
           before forking. It *records* ``threading.active_count()`` at fork
           time, because an import can start threads behind our back -- that
           is what the M1 fork-vs-fresh identity check exists to catch.

``single`` (Windows / local fallback) One fresh interpreter per scenario.
           Slower, semantically the same: every scenario again starts from a
           just-imported module.

In both modes the per-scenario timeout covers scenario execution only, not
the import (which happens once before forking in ``fork`` mode, so it must
also be excluded in ``single`` mode for the two to agree).

``PYTHONHASHSEED`` is pinned for scenario runs. Without it, ``single`` mode
draws a fresh string-hash seed per process while ``fork`` children share
one, so any behaviour that depends on set iteration order would differ
between the modes for reasons unrelated to the code under test.

Run as ``python -m meta_real_eval.benchmarks.forkserver`` by
:func:`run_scenarios`; it is not meant to be invoked by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .observe import exc_token, token

PYTHONHASHSEED = "0"
_TIMEOUT_EXIT_CODE = 124
_PACKAGE_SRC = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Child side: run one scenario in a namespace that already holds the header
# ---------------------------------------------------------------------------

def _resolve(expr: Optional[str], ns: dict):
    if not expr:
        return None
    try:
        return eval(compile(expr, "<expected_exc>", "eval"), ns)
    except BaseException:
        return None


def _run_scenario(steps: list[dict], ns: dict) -> dict[str, str]:
    """Execute a scenario's steps in ``ns``; return its trace ``{key: token}``.

    Keys ``s<i>`` hold step observations; ``end:<var>`` hold the bounded
    end-of-scenario state snapshot of every variable the scenario bound.
    Mirrors pytest semantics: the scenario stops at the first exception
    unless it is a ``raises`` step whose exception matches the expected type
    (pytest.raises would have caught it and the test would continue).
    """
    tokens: dict[str, str] = {}
    bound: list[str] = []
    for i, step in enumerate(steps):
        key = f"s{i}"
        try:
            value = eval(compile(step["src"], f"<scenario {key}>", "eval"), ns)
        except BaseException as e:
            tokens[key] = exc_token(e)
            if step["kind"] == "raises":
                expected = _resolve(step.get("expected_exc"), ns)
                if isinstance(expected, type) and isinstance(e, expected):
                    continue
            break
        if step["kind"] == "raises":
            # pytest.raises would fail the test here: no exception happened.
            tokens[key] = "NO_EXC:" + token(value)
            break
        tokens[key] = token(value)
        target = step.get("target")
        if target:
            ns[target] = value
            if target not in bound:
                bound.append(target)

    for var in bound:
        tokens[f"end:{var}"] = token(ns[var])
    return tokens


def _load_header(header: str, workdir: Path) -> tuple[Optional[dict], Optional[str]]:
    sys.path.insert(0, str(workdir))
    ns: dict = {"__name__": "__scenario__"}
    try:
        exec(compile(header, "<header>", "exec"), ns)
    except BaseException as e:
        return None, exc_token(e)
    return ns, None


def _silence_stdio() -> None:
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)


def _fork_one(steps: list[dict], base_ns: dict, timeout_s: float) -> dict:
    import select
    import signal

    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:  # child
        os.close(r)
        try:
            _silence_stdio()
            payload = {"status": "ok", "tokens": _run_scenario(steps, dict(base_ns))}
        except BaseException as e:
            payload = {"status": "crashed", "tokens": {"crash": exc_token(e)}}
        data = memoryview(json.dumps(payload).encode("utf-8"))
        while data:
            data = data[os.write(w, data):]
        os._exit(0)

    os.close(w)
    chunks: list[bytes] = []
    deadline = time.monotonic() + timeout_s
    timed_out = False
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        ready, _, _ = select.select([r], [], [], remaining)
        if not ready:
            timed_out = True
            break
        chunk = os.read(r, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    os.close(r)
    if timed_out:
        os.kill(pid, signal.SIGKILL)
    _, status = os.waitpid(pid, 0)

    if timed_out:
        return {"status": "timeout", "tokens": {}}
    if not chunks:
        sig = os.WTERMSIG(status) if os.WIFSIGNALED(status) else None
        return {"status": "crashed", "tokens": {"crash": f"SIGNAL:{sig}"}}
    return json.loads(b"".join(chunks).decode("utf-8"))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("fork", "single"), required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--index", type=int, default=None)
    args = parser.parse_args(argv)

    spec = json.loads((args.dir / "scenarios.json").read_text(encoding="utf-8"))
    scenarios = spec["scenarios"]

    if args.mode == "single":
        base_ns, import_exc = _load_header(spec["header"], args.dir)
        out = args.dir / f"trace_{args.index}.json"
        if base_ns is None:
            trace = {"status": "import_error", "tokens": {"import": import_exc}}
        else:
            _silence_stdio()
            # A watchdog thread can interrupt a pure-Python infinite loop; the
            # caller's subprocess timeout is the backstop for C-level hangs.
            watchdog = threading.Timer(args.timeout, lambda: os._exit(_TIMEOUT_EXIT_CODE))
            watchdog.daemon = True
            watchdog.start()
            try:
                trace = {"status": "ok", "tokens": _run_scenario(scenarios[args.index]["steps"], base_ns)}
            except BaseException as e:
                trace = {"status": "crashed", "tokens": {"crash": exc_token(e)}}
            watchdog.cancel()
        out.write_text(json.dumps(trace), encoding="utf-8")
        os._exit(0)  # do not wait for the watchdog thread

    base_ns, import_exc = _load_header(spec["header"], args.dir)
    traces: list[dict] = []
    if base_ns is None:
        traces = [{"status": "import_error", "tokens": {"import": import_exc}} for _ in scenarios]
    else:
        threads_at_fork = threading.active_count()
        for s in scenarios:
            trace = _fork_one(s["steps"], base_ns, args.timeout)
            trace["threads_at_fork"] = threads_at_fork
            traces.append(trace)
    (args.dir / "traces.json").write_text(json.dumps(traces), encoding="utf-8")
    return 0


# ---------------------------------------------------------------------------
# Parent side
# ---------------------------------------------------------------------------

def default_mode() -> str:
    return "fork" if hasattr(os, "fork") else "single"


def _env() -> dict:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": PYTHONHASHSEED}
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(_PACKAGE_SRC), os.environ.get("PYTHONPATH", "")) if p
    )
    return env


def run_scenarios(
    module_name: str,
    solution_code: str,
    header: str,
    scenarios: list,
    timeout_s: float = 10.0,
    mode: Optional[str] = None,
    import_allowance_s: float = 60.0,
) -> list[dict]:
    """Run every scenario against ``solution_code``; one trace per scenario.

    A trace is ``{"status": ok|timeout|crashed|import_error, "tokens": {...}}``
    (fork mode adds ``threads_at_fork``). ``scenarios`` are
    :class:`~.scenarios.Scenario` objects (or plain dicts with a ``steps``
    list). ``import_allowance_s`` bounds the header import, which is excluded
    from ``timeout_s`` in both modes.
    """
    mode = mode or default_mode()
    if mode == "fork" and not hasattr(os, "fork"):
        raise RuntimeError("fork mode is unavailable on this platform")

    spec = {
        "header": header,
        "scenarios": [
            s if isinstance(s, dict) else {"scenario_id": s.scenario_id,
                                            "steps": [asdict(st) for st in s.steps]}
            for s in scenarios
        ],
    }
    base = [sys.executable, "-m", "meta_real_eval.benchmarks.forkserver",
            "--timeout", str(timeout_s)]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / f"{module_name}.py").write_text(solution_code, encoding="utf-8")
        (tmp_path / "scenarios.json").write_text(json.dumps(spec), encoding="utf-8")
        env = _env()

        if mode == "fork":
            overall = import_allowance_s + (timeout_s + 1.0) * max(1, len(spec["scenarios"]))
            proc = subprocess.run(base + ["--dir", tmp, "--mode", "fork"], cwd=tmp,
                                  capture_output=True, timeout=overall, env=env)
            out = tmp_path / "traces.json"
            if not out.exists():
                raise RuntimeError(f"fork runner produced no traces:\n"
                                   f"{proc.stderr.decode(errors='replace')[-2000:]}")
            return json.loads(out.read_text(encoding="utf-8"))

        traces: list[dict] = []
        for i in range(len(spec["scenarios"])):
            try:
                proc = subprocess.run(base + ["--dir", tmp, "--mode", "single", "--index", str(i)],
                                      cwd=tmp, capture_output=True, env=env,
                                      timeout=import_allowance_s + timeout_s)
                timed_out = proc.returncode == _TIMEOUT_EXIT_CODE
            except subprocess.TimeoutExpired:
                timed_out = True
            out = tmp_path / f"trace_{i}.json"
            if timed_out:
                traces.append({"status": "timeout", "tokens": {}})
            elif out.exists():
                traces.append(json.loads(out.read_text(encoding="utf-8")))
            else:
                traces.append({"status": "crashed",
                               "tokens": {"crash": f"EXIT:{proc.returncode}"}})
        return traces


if __name__ == "__main__":
    raise SystemExit(main())
