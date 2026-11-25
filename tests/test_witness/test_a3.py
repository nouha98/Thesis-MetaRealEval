"""A3 agent (oracles.agent): static checks, admission on the reference, fault detection and the
bounded repair loop, with a scripted model on the G2 fixture class (real pytest)."""

import asyncio

from meta_real_eval.benchmarks.contracts import draft_contract
from meta_real_eval.core import exec_policy
from meta_real_eval.core.exec_policy import ExecPolicy
from meta_real_eval.oracles import agent

from .fixtures import DEPENDENCY_SCAN, MODULE, MUTANTS, REFERENCE, make_task

GOOD = '''import pytest

def test_a3():
    c = module_0.Counter(0)
    for _ in range(7):
        c.add(1)
    # doc: "Add n and return the new count."
    assert c.add(1) == 8
'''
NO_QUOTE = GOOD.replace('    # doc: "Add n and return the new count."\n', "")
PRIVATE = GOOD.replace("assert c.add(1) == 8", "assert c._history == [1] * 8")
REF_FAILS = GOOD.replace("== 8", "== 9")
WEAK = GOOD.replace("range(7)", "range(1)").replace("== 8", "== 2")      # counts stay below 5: fault invisible


def fenced(code):
    return f"Here is the test:\n```python\n{code}```\n"


def test_static_checks():
    assert agent.static_check(GOOD) is None
    assert agent.static_check(None)[0] == "syntax"
    assert agent.static_check(NO_QUOTE)[0] == "no_doc_quote"
    assert agent.static_check(PRIVATE)[0] == "private_access"
    assert agent.static_check("import os\n\ndef test_a3():\n    pass\n")[0] == "forbidden_import"
    assert agent.static_check('def test_a3():\n    # doc: "x"\n    assert repr(1)\n')[0] == "non_api"
    assert agent.static_check("x = 1\n\ndef test_a3():\n    pass\n")[0] == "syntax"          # import-time code
    assert agent.static_check("def test_a3():\n    pass\n\ndef test_b():\n    pass\n")[0] == "syntax"
    assert agent.extract_code(fenced(GOOD)) == GOOD


def test_prompt_states_the_domain_and_rules():
    c = draft_contract(make_task(), DEPENDENCY_SCAN)
    msgs = agent.first_prompt(make_task().prompt, c, REFERENCE, "-a\n+b\n")
    text = msgs[1]["content"]
    assert "constructor Counter(" in text and "add(n: int" in text and '# doc: "' in text and "-a\n+b" in text


def test_repair_loop_feeds_back_and_admits():
    ExecPolicy(kill_process_tree=True, isolate_home=True).activate()
    try:
        script = [fenced(NO_QUOTE), fenced(REF_FAILS), fenced(GOOD)]
        seen = []

        async def ask(msgs, k):
            seen.append(msgs[-1]["content"])
            return script[k], {"k": k}
        res = asyncio.run(agent.run_target(ask, [{"role": "user", "content": "go"}], MODULE, REFERENCE,
                                           MUTANTS["state_fault"], 30, attempts=3))
        assert [a["verdict"]["check"] for a in res.attempts] == ["no_doc_quote", "reference_fails", None]
        assert res.admitted == GOOD and "`no_doc_quote`" in seen[1] and "`reference_fails`" in seen[2]

        async def weak(msgs, k):
            return fenced(WEAK), {}
        res = asyncio.run(agent.run_target(weak, [], MODULE, REFERENCE, MUTANTS["state_fault"], 30, attempts=2))
        assert res.admitted is None and [a["verdict"]["check"] for a in res.attempts] == ["fault_not_detected"] * 2
    finally:
        exec_policy.deactivate()


def test_a3_targets_and_condition3():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import build_a3 as b3
    assert b3.surviving({"discovery_groups": ["g3", "g1", "g2"], "covered_final": ["g2"]}) == ["g1", "g3"]
    a2 = {("T1", "a"): False, ("T1", "b"): True, ("T2", "c"): False, ("T3", "d"): False}
    a3 = {("T1", "a"): True, ("T1", "b"): True, ("T2", "c"): True, ("T3", "d"): False}
    c3 = b3.condition3(a2, a3)
    assert c3["tasks"] == ["T1", "T2"] and not c3["ok"]
    a3[("T3", "d")] = True
    assert b3.condition3(a2, a3)["ok"]
    assert b3.renamed("def test_a3():\n    pass\n", "test_h_7").startswith("def test_h_7():")
