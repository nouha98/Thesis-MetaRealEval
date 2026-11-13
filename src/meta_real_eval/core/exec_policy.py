"""Opt-in execution policy for generated code (extensions plan rev. 8).

Generated code (completions, mutants, generated tests) runs in subprocesses
started by ``core.sandbox`` and ``benchmarks.forkserver``. Historically the
child receives the parent's full environment, which includes the gateway API
key loaded from ``.env``. The extensions run many more model-written programs
(test agent, repair agent), so they turn on a minimal policy:

  * credential separation: variables whose names look like secrets (API keys,
    tokens, passwords, provider prefixes such as ``INNKUBE_``/``OPENAI_``/
    ``HF_``) are removed from the child's environment;
  * optional POSIX resource limits (address space, CPU seconds, file size),
    applied in the child before ``exec``; ignored on Windows;
  * optional descendant cleanup (``kill_process_tree``): the child starts in
    its own session (POSIX) or process group (Windows); on timeout the whole
    tree is killed, and on POSIX any process left in the group after the
    child exits is killed too. On Windows a grandchild orphaned by a child
    that exited normally cannot be found any more (that needs a job object);
    the canary (``core/canary.py``) reports this instead of assuming it.

Threat model: accidental leakage and runaway code, not a hostile program
trying to escape (there is no network or filesystem isolation here).

**Off by default.** With no explicit policy and ``MRE_EXEC_POLICY`` unset,
every subprocess gets exactly the environment and limits it got before this
module existed, so historical paths and results are unchanged. An extension
runner calls :meth:`ExecPolicy.activate` once; the policy then travels to
worker processes through the ``MRE_EXEC_POLICY`` variable.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
from dataclasses import asdict, dataclass
from typing import Callable, Mapping, Optional

ENV_VAR = "MRE_EXEC_POLICY"

_SECRET_NAME = re.compile(r"(API_?KEY|TOKEN|SECRET|PASSW|CREDENTIAL|PRIVATE_?KEY|ACCESS_?KEY|AUTH)",
                          re.IGNORECASE)
_SECRET_PREFIXES = ("OPENAI_", "ANTHROPIC_", "INNKUBE_", "HF_", "HUGGING", "AWS_", "AZURE_",
                    "GOOGLE_APPLICATION_CREDENTIALS", "LITELLM", "WANDB_", "GH_", "GITHUB_")


def is_secret_name(name: str) -> bool:
    if name == ENV_VAR:
        return False
    upper = name.upper()
    return upper.startswith(_SECRET_PREFIXES) or bool(_SECRET_NAME.search(upper))


@dataclass(frozen=True)
class ExecPolicy:
    scrub_credentials: bool = True
    memory_limit_mb: Optional[int] = None     # RLIMIT_AS
    cpu_limit_s: Optional[int] = None         # RLIMIT_CPU
    file_size_limit_mb: Optional[int] = None  # RLIMIT_FSIZE
    kill_process_tree: bool = False           # descendant cleanup (see module docstring)
    # HOME / temp / XDG dirs -> the child's working directory, so generated inputs
    # cannot make a class write under the real home. For runs on generated inputs
    # (witness search, A2 construction); grading leaves it off (references may load
    # caches from home).
    isolate_home: bool = False

    # --- environment ----------------------------------------------------------

    def child_env(self, env: Mapping[str, str]) -> dict[str, str]:
        if not self.scrub_credentials:
            return dict(env)
        return {k: v for k, v in env.items() if not is_secret_name(k)}

    # --- resource limits ------------------------------------------------------

    def has_limits(self) -> bool:
        return any(v is not None for v in (self.memory_limit_mb, self.cpu_limit_s, self.file_size_limit_mb))

    def preexec_fn(self) -> Optional[Callable[[], None]]:
        """A ``subprocess`` ``preexec_fn`` that sets the limits, or None (no limits, or not POSIX)."""
        if not self.has_limits() or os.name != "posix":
            return None
        limits = []
        import resource  # POSIX only
        if self.memory_limit_mb is not None:
            limits.append((resource.RLIMIT_AS, self.memory_limit_mb * 1024 * 1024))
        if self.cpu_limit_s is not None:
            limits.append((resource.RLIMIT_CPU, int(self.cpu_limit_s)))
        if self.file_size_limit_mb is not None:
            limits.append((resource.RLIMIT_FSIZE, self.file_size_limit_mb * 1024 * 1024))

        def _apply() -> None:
            for which, value in limits:
                soft, hard = resource.getrlimit(which)
                cap = value if hard == resource.RLIM_INFINITY else min(value, hard)
                resource.setrlimit(which, (cap, hard))
        return _apply

    # --- transport --------------------------------------------------------------

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "ExecPolicy":
        return cls(**json.loads(text))

    def activate(self) -> None:
        """Make this the process-wide policy (inherited by child and worker processes)."""
        os.environ[ENV_VAR] = self.to_json()


def deactivate() -> None:
    os.environ.pop(ENV_VAR, None)


def active_policy(explicit: Optional[ExecPolicy] = None) -> Optional[ExecPolicy]:
    """The explicit policy, else the activated one, else None (historical behaviour)."""
    if explicit is not None:
        return explicit
    text = os.environ.get(ENV_VAR)
    return ExecPolicy.from_json(text) if text else None


HOME_VARS = ("HOME", "USERPROFILE", "TMPDIR", "TEMP", "TMP", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME")


def apply(env: dict[str, str], explicit: Optional[ExecPolicy] = None,
          workdir=None) -> tuple[dict[str, str], Optional[Callable[[], None]]]:
    """(child environment, preexec_fn) for a subprocess. Unchanged ``env`` and None when no policy.
    With ``isolate_home`` and a ``workdir``, home/temp/XDG variables point at ``workdir``."""
    policy = active_policy(explicit)
    if policy is None:
        return env, None
    child = policy.child_env(env)
    if policy.isolate_home and workdir is not None:
        for k in HOME_VARS:
            child[k] = str(workdir)
    return child, policy.preexec_fn()


# ---------------------------------------------------------------------------
# Descendant cleanup
# ---------------------------------------------------------------------------

def _kill_group(pid: int) -> None:
    """Kill every process in the group/tree rooted at ``pid`` (best effort, never raises)."""
    try:
        if os.name == "posix":
            os.killpg(pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    except (ProcessLookupError, PermissionError, OSError, subprocess.SubprocessError):
        pass


def run(args, *, policy: Optional[ExecPolicy] = None, **kwargs) -> subprocess.CompletedProcess:
    """``subprocess.run(args, **kwargs)``; with ``policy.kill_process_tree`` the child runs in its
    own session / process group and its whole tree is killed on timeout (and, on POSIX, any
    leftover group member after it exits). Without that flag this IS ``subprocess.run``."""
    if policy is None or not policy.kill_process_tree:
        return subprocess.run(args, **kwargs)
    timeout = kwargs.pop("timeout", None)
    if kwargs.pop("capture_output", False):
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    if os.name == "posix":
        kwargs["start_new_session"] = True
    else:
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NEW_PROCESS_GROUP
    with subprocess.Popen(args, **kwargs) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc.pid)
            proc.kill()
            out, err = proc.communicate()
            raise subprocess.TimeoutExpired(proc.args, timeout, output=out, stderr=err) from None
        finally:
            if os.name == "posix":
                _kill_group(proc.pid)        # orphans keep the child's process group
    return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)


def pid_alive(pid: int) -> bool:
    """Whether a process with ``pid`` is still running (zombies count as gone)."""
    if os.name == "posix":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        try:   # a reaped-later zombie still answers kill(0); check its state
            with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
                return f.read().split(") ", 1)[1][:1] != "Z"
        except OSError:
            return True
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == 259                         # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)
