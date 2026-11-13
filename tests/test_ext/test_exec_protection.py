"""Execution protection: descendant cleanup, protected grading inputs and the runtime canary.
Verified by running programs, never by assuming the policy is active."""

import os
import subprocess
import sys

import pytest

from meta_real_eval.core import artifacts, canary, exec_policy
from meta_real_eval.core.exec_policy import ExecPolicy

POSIX = os.name == "posix"


@pytest.fixture(autouse=True)
def _clean_policy(monkeypatch):
    monkeypatch.delenv(exec_policy.ENV_VAR, raising=False)
    yield
    exec_policy.deactivate()


def test_run_without_tree_kill_is_subprocess_run():
    r = exec_policy.run([sys.executable, "-c", "print(42)"], policy=None, capture_output=True, timeout=30)
    assert isinstance(r, subprocess.CompletedProcess) and r.stdout.strip() == b"42"
    r2 = exec_policy.run([sys.executable, "-c", "print(42)"], policy=ExecPolicy(kill_process_tree=True),
                         capture_output=True, timeout=30)
    assert r2.returncode == 0 and r2.stdout.strip() == b"42"


def test_tree_kill_raises_timeout_with_output():
    prog = "import sys, time; print('started', flush=True); time.sleep(30)"
    with pytest.raises(subprocess.TimeoutExpired) as exc:
        exec_policy.run([sys.executable, "-c", prog], policy=ExecPolicy(kill_process_tree=True),
                        capture_output=True, timeout=2)
    assert b"started" in (exc.value.stdout or b"")


def test_canary_detects_leaks_without_policy_and_none_with_it():
    r = canary.run_canary(paths=("execute", "execute_pytest"), policy=None)
    for path in ("execute", "execute_pytest"):
        assert canary.PLANTED_SECRET in r["paths"][path]["secrets_visible"]
    assert not canary.verdict(r, require_tree_kill=False)["ok"]
    r = canary.run_canary(policy=ExecPolicy(kill_process_tree=True))
    for path in canary.PATHS:
        assert r["paths"][path]["ran"] and r["paths"][path]["secrets_visible"] == []
    assert canary.verdict(r, require_tree_kill=False)["ok"]
    # execute / execute_pytest kill the tree on timeout on every OS
    assert r["paths"]["execute"]["grandchild_survived"] is False
    assert r["paths"]["execute_pytest"]["grandchild_survived"] is False
    assert os.environ.get(exec_policy.ENV_VAR) is None       # the canary restores the caller's state


@pytest.mark.skipif(not POSIX, reason="session/process-group cleanup after a normal exit is POSIX-only")
def test_canary_requires_full_tree_kill_on_posix():
    report = canary.require_canary(policy=ExecPolicy(kill_process_tree=True))
    assert all(r["grandchild_survived"] is False for r in report["paths"].values())


def test_require_canary_aborts_on_a_leak():
    with pytest.raises(canary.CanaryFailed):
        canary.require_canary(paths=("execute",), policy=ExecPolicy(scrub_credentials=False),
                              require_tree_kill=False)


def test_protected_inputs_detect_tampering_and_restore_modes(tmp_path):
    f = tmp_path / "hidden" / "test_h.py"
    f.parent.mkdir()
    f.write_text("def test_h(): pass\n")
    mode = f.stat().st_mode
    with artifacts.protected_inputs([tmp_path / "hidden"]) as hashes:
        assert list(hashes) == [str(f)]
        with pytest.raises(PermissionError):
            f.write_text("tampered")
    assert f.stat().st_mode == mode
    with pytest.raises(artifacts.ArtifactTampered):
        with artifacts.protected_inputs([f]):
            os.chmod(f, mode)
            f.write_text("tampered")
    with pytest.raises(artifacts.ArtifactTampered):
        with artifacts.protected_inputs([tmp_path / "missing.py"]):
            pass


def test_agent_workdir_must_not_hold_hidden_files(tmp_path):
    (tmp_path / "candidate.py").write_bytes(b"X = 1\n")
    artifacts.assert_absent(tmp_path, ["test_h_*", "reference*.py"])
    (tmp_path / "test_h_1.py").write_text("")
    with pytest.raises(artifacts.ArtifactTampered):
        artifacts.assert_absent(tmp_path, ["test_h_*"])
    import hashlib
    secret = hashlib.sha256(b"X = 1\n").hexdigest()
    with pytest.raises(artifacts.ArtifactTampered):
        artifacts.assert_absent(tmp_path, forbidden_hashes=[secret])
