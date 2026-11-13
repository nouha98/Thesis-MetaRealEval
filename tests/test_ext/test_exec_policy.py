"""core/exec_policy.py: credential separation is opt-in and leaves the historical paths unchanged."""

import os

import pytest

from meta_real_eval.core import exec_policy
from meta_real_eval.core.exec_policy import ExecPolicy, active_policy, is_secret_name
from meta_real_eval.core.sandbox import execute, execute_pytest

CHECK_NO_KEY = "import os\nassert 'INNKUBE_API_KEY' not in os.environ\nassert 'HF_TOKEN' not in os.environ\n"


@pytest.fixture(autouse=True)
def _no_active_policy(monkeypatch):
    monkeypatch.delenv(exec_policy.ENV_VAR, raising=False)
    monkeypatch.setenv("INNKUBE_API_KEY", "sk-test")
    monkeypatch.setenv("HF_TOKEN", "hf-test")
    monkeypatch.setenv("MRE_HARMLESS", "1")
    yield
    exec_policy.deactivate()


@pytest.mark.parametrize("name,secret", [
    ("INNKUBE_API_KEY", True), ("INNKUBE_BASE_URL", True), ("HF_TOKEN", True), ("OPENAI_API_KEY", True),
    ("GITHUB_TOKEN", True), ("MY_SERVICE_PASSWORD", True), ("AWS_SECRET_ACCESS_KEY", True),
    ("PATH", False), ("HOME", False), ("PYTHONPATH", False), ("MPLCONFIGDIR", False),
    ("PYTHONHASHSEED", False), ("MRE_OUTCOME_LOG", False), (exec_policy.ENV_VAR, False),
])
def test_secret_names(name, secret):
    assert is_secret_name(name) is secret


def test_without_a_policy_nothing_changes():
    env = {"INNKUBE_API_KEY": "x", "PATH": "p"}
    out, preexec = exec_policy.apply(env)
    assert out is env and preexec is None
    assert active_policy() is None


def test_policy_scrubs_only_secrets_and_travels_through_the_environment():
    ExecPolicy().activate()
    pol = active_policy()
    assert pol == ExecPolicy()
    out = pol.child_env({"INNKUBE_API_KEY": "x", "PATH": "p", exec_policy.ENV_VAR: pol.to_json()})
    assert out == {"PATH": "p", exec_policy.ENV_VAR: pol.to_json()}
    assert ExecPolicy(scrub_credentials=False).child_env({"INNKUBE_API_KEY": "x"}) == {"INNKUBE_API_KEY": "x"}


def test_limits_are_posix_only_and_off_by_default():
    assert ExecPolicy().preexec_fn() is None
    fn = ExecPolicy(cpu_limit_s=30).preexec_fn()
    assert (fn is None) == (os.name != "posix")


def test_execute_keeps_credentials_without_policy_and_drops_them_with_one():
    assert not execute("", CHECK_NO_KEY).passed                     # historical behaviour
    assert execute("", CHECK_NO_KEY, policy=ExecPolicy()).passed
    ExecPolicy().activate()
    assert execute("", CHECK_NO_KEY).passed                         # activated policy


def test_execute_pytest_honours_the_policy():
    test_code = "def test_env():\n" + "".join("    " + line + "\n" for line in CHECK_NO_KEY.splitlines())
    without = execute_pytest("snippet_x", "X = 1\n", test_code)
    with_policy = execute_pytest("snippet_x", "X = 1\n", test_code, policy=ExecPolicy())

    def outcome(res):
        return [r.pytest_outcome for r in res.reports["test_snippet_x.py::test_env"] if r.when == "call"]
    assert outcome(without) == ["failed"]
    assert outcome(with_policy) == ["passed"]
