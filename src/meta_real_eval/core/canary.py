"""Runtime canary preflight (extensions plan rev. 9).

Before an extension run executes any generated code, a canary program is run
through every execution path the run will use, and reports what generated
code would actually see:

  * ``secrets_visible``  -- environment variable names that look like
    credentials (a synthetic ``MRE_CANARY_API_KEY`` is planted in the parent
    for the check, so the test is meaningful even on a node without keys);
  * ``rlimits``          -- effective POSIX resource limits (None on Windows);
  * ``grandchild_survived`` -- the canary spawns a sleeping grandchild and
    then hangs; after the path's timeout kills it, is the grandchild gone?

Paths: ``execute`` (Tier 1 / HumanEval and the HumanEval+ pilot),
``execute_pytest`` (Tier 2 suites, hidden-suite grading) and ``forkserver``
(Tier 2 scenarios, witnesses). The verdict is recorded in the run manifest;
:func:`require_canary` aborts the run when it fails. Nothing is assumed from
configuration: the check observes the running system.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Optional

from . import exec_policy
from .exec_policy import ExecPolicy

PATHS = ("execute", "execute_pytest", "forkserver")
PLANTED_SECRET = "MRE_CANARY_API_KEY"


class CanaryFailed(SystemExit):
    pass


def _program(report: Path, mode: str) -> str:
    """Python source run by the canary: write a report, optionally spawn a grandchild and hang."""
    return f'''
import json, os, subprocess, sys, time
SECRET = __import__("re").compile(r"(API_?KEY|TOKEN|SECRET|PASSW|CREDENTIAL|PRIVATE_?KEY|ACCESS_?KEY|AUTH)", __import__("re").I)
PREFIXES = {exec_policy._SECRET_PREFIXES!r}
names = sorted(k for k in os.environ if k != {exec_policy.ENV_VAR!r} and (k.upper().startswith(PREFIXES) or SECRET.search(k.upper())))
limits = None
try:
    import resource
    limits = {{n: resource.getrlimit(getattr(resource, n))[0] for n in ("RLIMIT_AS", "RLIMIT_CPU", "RLIMIT_FSIZE")}}
except ImportError:
    pass
rep = {{"secrets_visible": names, "rlimits": limits, "grandchild_pid": None}}
if {mode!r} == "tree":
    # detached pipes and cwd: only the grandchild's survival is measured, it must not
    # keep the parent's pipes or temp dir busy (that would hang or crash an unprotected run)
    g = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd={tempfile.gettempdir()!r})   # the parent's temp root, not an isolated home
    rep["grandchild_pid"] = g.pid
with open({str(report)!r}, "w") as f:
    json.dump(rep, f)
if {mode!r} == "tree":
    time.sleep(60)
'''


def _via(path: str, program: str, timeout_s: float) -> str:
    """Run the canary program through ``path``; returns a short diagnostic (stderr tail / status)."""
    from .sandbox import execute, execute_pytest
    if path == "execute":
        r = execute(program, "", timeout_s=timeout_s)
        return f"timed_out={r.timed_out} stderr={r.stderr[-400:]}"
    elif path == "execute_pytest":
        body = "".join("    " + line + "\n" for line in program.splitlines())
        r = execute_pytest("canary_mod", "X = 1\n", "import canary_mod\n\ndef test_canary():\n" + body,
                           timeout_s=timeout_s)
        return f"timed_out={sorted(r.timed_out_nodeids)} stdout={r.stdout[-400:]} stderr={r.stderr[-400:]}"
    elif path == "forkserver":
        from ..benchmarks.forkserver import run_scenarios
        body = "".join("    " + line + "\n" for line in program.splitlines())
        r = run_scenarios("canary_mod", "def canary():\n" + body, "import canary_mod as module_0\n",
                          [{"scenario_id": "canary", "steps": [{"kind": "exec", "src": "module_0.canary()",
                                                               "target": None, "expected_exc": None}]}],
                          timeout_s=timeout_s, import_allowance_s=timeout_s)
        return f"status={r[0].get('status') if r else None}"
    else:
        raise ValueError(f"unknown execution path {path!r}")


@contextmanager
def _planted_secret():
    old = os.environ.get(PLANTED_SECRET)
    os.environ[PLANTED_SECRET] = "canary-not-a-real-key"
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(PLANTED_SECRET, None)
        else:
            os.environ[PLANTED_SECRET] = old


def run_canary(paths: Iterable[str] = PATHS, policy: Optional[ExecPolicy] = None,
               timeout_s: float = 4.0, warmup: bool = False) -> dict:
    """Run the canary through each path under ``policy`` (default: the activated one).
    ``warmup`` first runs a trivial program through each path, unmeasured: the first
    ``python -m pytest`` on a cold cluster node can exceed any reasonable timeout."""
    policy = exec_policy.active_policy(policy)
    saved = os.environ.get(exec_policy.ENV_VAR)
    results: dict[str, dict] = {}
    try:
        if policy is not None:
            policy.activate()                 # every path reads the activated policy
        else:
            exec_policy.deactivate()
        with _planted_secret(), tempfile.TemporaryDirectory() as tmp:
            for path in paths:
                if warmup:
                    _via(path, "pass", max(timeout_s, 120.0))
                env_report = Path(tmp) / f"{path}_env.json"
                t0 = time.monotonic()
                env_diag = _via(path, _program(env_report, "env"), timeout_s)
                env_s = round(time.monotonic() - t0, 2)
                tree_report = Path(tmp) / f"{path}_tree.json"
                tree_diag = _via(path, _program(tree_report, "tree"), timeout_s)
                env = json.loads(env_report.read_text()) if env_report.exists() else None
                tree = json.loads(tree_report.read_text()) if tree_report.exists() else None
                survived = None
                if tree and tree.get("grandchild_pid"):
                    time.sleep(0.5)
                    gpid = tree["grandchild_pid"]
                    survived = exec_policy.pid_alive(gpid)
                    if survived:                  # never leave the canary's grandchild behind
                        exec_policy._kill_group(gpid)
                results[path] = {"ran": env is not None,
                                 "secrets_visible": env["secrets_visible"] if env else None,
                                 "rlimits": env["rlimits"] if env else None,
                                 "grandchild_survived": survived, "env_seconds": env_s}
                if env is None:
                    results[path]["diagnostic_env"] = env_diag
                if tree is None:
                    results[path]["diagnostic_tree"] = tree_diag
    finally:
        if saved is None:
            exec_policy.deactivate()
        else:
            os.environ[exec_policy.ENV_VAR] = saved
    return {"policy": None if policy is None else json.loads(policy.to_json()),
            "os": os.name, "paths": results}


def verdict(report: dict, require_tree_kill: Optional[bool] = None) -> dict:
    """Pass/fail per path: ran, no secret visible, and (where required) no surviving grandchild.
    Tree-kill is required on POSIX by default; on Windows a grandchild orphaned by a normal exit
    cannot be reached without a job object, so it is reported, not required."""
    if require_tree_kill is None:
        require_tree_kill = report["os"] == "posix"
    out = {}
    for path, r in report["paths"].items():
        problems = []
        if not r["ran"]:
            problems.append(f"canary did not run (after {r.get('env_seconds')} s; {r.get('diagnostic_env', '')[:500]})")
        if r["secrets_visible"]:
            problems.append(f"secrets visible: {r['secrets_visible']}")
        if require_tree_kill and r["grandchild_survived"] is not False:
            problems.append(f"grandchild survived={r['grandchild_survived']}")
        out[path] = {"ok": not problems, "problems": problems}
    return {"ok": all(v["ok"] for v in out.values()), "require_tree_kill": require_tree_kill, "paths": out}


def require_canary(paths: Iterable[str] = PATHS, policy: Optional[ExecPolicy] = None,
                   require_tree_kill: Optional[bool] = None, timeout_s: float = 4.0,
                   warmup: bool = False) -> dict:
    """Run the canary and abort (CanaryFailed) unless every path passes. Returns report + verdict.
    ``timeout_s`` bounds each canary run; cluster runs pass their suite timeout, because a cold
    ``python -m pytest`` start on a shared file system can exceed the 4 s default."""
    report = run_canary(paths, policy, timeout_s=timeout_s, warmup=warmup)
    report["verdict"] = verdict(report, require_tree_kill)
    if not report["verdict"]["ok"]:
        raise CanaryFailed(f"ERROR: execution canary failed: {json.dumps(report['verdict'])}")
    return report
