"""A3 v2 (decisions 10.6): v1 pinned byte for byte; v2 has no reference in the prompt, a diff without context
lines and value-free reference-failure feedback (real pytest on the G2 fixture class)."""

import asyncio
import hashlib
import inspect
import json
import sys
from pathlib import Path

from meta_real_eval.benchmarks.contracts import draft_contract
from meta_real_eval.core import exec_policy
from meta_real_eval.core.exec_policy import ExecPolicy
from meta_real_eval.oracles import agent

from .fixtures import DEPENDENCY_SCAN, MODULE, MUTANTS, REFERENCE, make_task
from .test_a3 import GOOD, REF_FAILS, WEAK, fenced

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import build_a3 as b3  # noqa: E402

BOX = {"class_name": "Box", "constructor": {"params": [{"name": "size", "type": {"t": "int"}, "constraints": {"min": 0}}]},
       "methods": {"put": {"params": [{"name": "x", "type": {"t": "str"}, "has_default": True}]}, "get": {"params": []}}}
BOX_REF = "class Box:\n    def __init__(self, size):\n        self.size = size\n    def get(self):\n        return self.size\n"
BOX_BAD = BOX_REF.replace("return self.size", "return self.size + 1")
SECRET = "class Counter"                                      # a line only the reference implementation contains


def sha(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()


def test_v1_is_pinned_byte_for_byte():
    """Computed from the pilot's code (commit 1d42220) before v2 was added."""
    msgs = agent.first_prompt("class Box:\n    '''A box.'''\n", BOX, BOX_REF, b3.fault_diff(BOX_REF, BOX_BAD))
    assert sha(json.dumps(msgs)) == "1be415dcd13b5dfa83ef97292a9cadd27f545dfad369320a4bafef5d548333de"
    assert sha(b3.fault_diff(BOX_REF, BOX_BAD)) == "c3ef871bfe6c4e95d9fbe527a9212388de2b0dcf2d6c12c5991157c1d67a8e7e"
    assert sha(agent.SYSTEM + agent.RULES) == "74bb65ac6f19e22a3a9fd620b1a478e03c17322c7bb1229cd0c06558a6c3dd4f"
    src = {f.__name__: sha(inspect.getsource(f)) for f in (agent.check, agent.first_prompt, agent.static_check,
                                                           agent.domain_text)}
    assert src == {"check": "6f154fff499a8df7d7e954a5a32ac2d90f0c1a43cf7b85a2334222db3bfa16ce",
                   "first_prompt": "0447f3d21288ede4ad2b138811c1f55c551493098dab0500e11a0ed9f887c909",
                   "static_check": "6fcdf8348ef946e0a662d342499a1d7f9825a8fb2aa5e3b9b8da4c0ba6dded5f",
                   "domain_text": "f1cda11d302bea84add7e693e8a8aea5282324393ea9f3e08035f2a8b0c229ce"}


def test_v2_prompt_has_no_reference_and_no_diff_context():
    c = draft_contract(make_task(), DEPENDENCY_SCAN)
    diff = b3.fault_diff(REFERENCE, MUTANTS["state_fault"], n=0)
    text = agent.first_prompt_v2(make_task().prompt, c, diff)[1]["content"]
    v1 = agent.first_prompt(make_task().prompt, c, REFERENCE, b3.fault_diff(REFERENCE, MUTANTS["state_fault"]))[1]["content"]
    assert "Reference implementation" not in text and REFERENCE.strip() not in text
    assert all(not ln.startswith(" ") for ln in diff.splitlines())                 # -U0: only changed lines
    assert "@@" in diff and "Reference implementation" in v1
    assert text.endswith(agent.RULES) and "constructor Counter(" in text


def test_v2_reference_failure_feedback_is_value_free():
    ExecPolicy(kill_process_tree=True, isolate_home=True).activate()
    try:
        v1 = agent.check(MODULE, REFERENCE, MUTANTS["state_fault"], REF_FAILS, 30)
        v2 = agent.check_v2(MODULE, REFERENCE, MUTANTS["state_fault"], REF_FAILS, 30)
        assert v1["check"] == v2["check"] == "reference_fails"
        assert "pytest output" in v1["message"] and "8" in v1["message"]           # v1 shows the reference value
        n = REF_FAILS.splitlines().index("    assert c.add(1) == 9") + 1
        assert v2["message"] == ("the test fails on a correct implementation "
                                 f"(AssertionError raised at line {n} of the test: `assert c.add(1) == 9`)")
        assert SECRET not in v2["message"] and "pytest" not in v2["message"]
        weak = agent.check_v2(MODULE, REFERENCE, MUTANTS["state_fault"], WEAK, 30)
        assert weak["message"] == agent.check(MODULE, REFERENCE, MUTANTS["state_fault"], WEAK, 30)["message"]
        assert agent.check_v2(MODULE, REFERENCE, MUTANTS["state_fault"], GOOD, 30)["admitted"]
    finally:
        exec_policy.deactivate()


def test_v2_loop_uses_the_v2_checker_and_the_same_repair_message():
    ExecPolicy(kill_process_tree=True, isolate_home=True).activate()
    try:
        seen = []

        async def ask(msgs, k):
            seen.append(msgs[-1]["content"])
            return [fenced(REF_FAILS), fenced(GOOD)][k], {}
        res = asyncio.run(agent.run_target(ask, [{"role": "user", "content": "go"}], MODULE, REFERENCE,
                                           MUTANTS["state_fault"], 30, attempts=3, checker=agent.check_v2))
        assert res.admitted == GOOD
        assert seen[1] == ("The test was not admitted. Check `reference_fails`: " + res.attempts[0]["verdict"]["message"]
                           + "\nFix it and answer with one ```python block. The rules above still apply.")
        assert "pytest output" not in seen[1]
    finally:
        exec_policy.deactivate()


def test_target_list_is_checked_against_the_frozen_h(tmp_path, monkeypatch):
    import freeze_h
    rec = {"h_v1_sha256": "a" * 64, "cohort": ["T"], "targets": {"T": []}}
    p = tmp_path / "targets.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    monkeypatch.setattr(freeze_h, "verify", lambda d: {"version": "tier2-hidden-v1", "global_sha256": "a" * 64})
    assert b3.load_targets(p, tmp_path)["cohort"] == ["T"]
    monkeypatch.setattr(freeze_h, "verify", lambda d: {"version": "tier2-hidden-v1.1", "global_sha256": "a" * 64})
    import pytest
    with pytest.raises(SystemExit, match="not the frozen H v1"):
        b3.load_targets(p, tmp_path)
