"""Admission and the private-rename control for hidden tests (plan rev. 9.3, Stage 4).

Admission (both arms) of an emitted hidden-test file, run standalone against the reference:
  * compiles (checked at emission) and is collected;
  * every test passes on the reference ``repeats`` times together and once alone
    (repeatable, deterministic, order-independent).
Contract-valid inputs, API-only assertions and non-vacuity hold by construction for A2
(contract strategies, ``api_diff`` on API tokens, and every kept test kills a discovery group);
A3 tests must be checked for them separately.

Control (``private_rename``): the reference with every single-underscore attribute renamed. It
is used only after **validation**: its API observations must equal the reference's on every
valid scenario of the A2 pool. A test that fails on a validated control is over-specified and is
dropped. A variant that fails validation is a transform defect (counted, never used).
"""

from __future__ import annotations

import ast
from typing import Optional

from ..benchmarks.outcomes import ORDINARY_PASS, classify_run, static_test_info
from ..benchmarks.witness import GEN_ALIAS, WitnessSettings, _run, compare
from ..benchmarks.contracts import api_rules
from ..core.sandbox import execute_pytest


def _outcomes(module: str, code: str, test_code: str, names: list[str], timeout_s: float) -> dict[str, str]:
    run = execute_pytest(module, code, test_code, timeout_s=timeout_s, select=names)
    res = classify_run(run, static_test_info(test_code), requested=names)
    return {n: (res[n].outcome if n in res else "missing") for n in names}


def run_tests(module: str, code: str, test_code: str, names: list[str], timeout_s: float) -> dict[str, str]:
    """Outcome per hidden test of one implementation (one pytest run)."""
    return _outcomes(module, code, test_code, names, timeout_s) if names else {}


def admit(module: str, reference: str, test_code: str, names: list[str], timeout_s: float,
          repeats: int = 3) -> dict[str, dict]:
    together = [run_tests(module, reference, test_code, names, timeout_s) for _ in range(repeats)]
    out = {}
    for n in names:
        alone = _outcomes(module, reference, test_code, [n], timeout_s)[n]
        runs = [t[n] for t in together]
        ok = all(o == ORDINARY_PASS for o in runs) and alone == ORDINARY_PASS
        reason = None if ok else ("not repeatable" if ORDINARY_PASS in runs else
                                  "reference fails" if alone != ORDINARY_PASS else "fails only together")
        out[n] = {"together": runs, "alone": alone, "admitted": ok, "reason": reason}
    return out


class _Rename(ast.NodeTransformer):
    def __init__(self, names: set[str]):
        self.names = names

    def visit_Attribute(self, node: ast.Attribute):
        self.generic_visit(node)
        if node.attr in self.names:
            node.attr = node.attr + "_ctl"
        return node


def private_rename(reference: str, class_name: str) -> Optional[str]:
    """The reference with every ``self._x`` attribute (single underscore, not dunder) of the target
    class renamed to ``_x_ctl``; None if the class has none."""
    tree = ast.parse(reference)
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    if cls is None:
        return None
    names = {n.attr for n in ast.walk(cls) if isinstance(n, ast.Attribute)
             and isinstance(n.value, ast.Name) and n.value.id == "self"
             and n.attr.startswith("_") and not n.attr.startswith("__")}
    if not names:
        return None
    _Rename(names).visit(cls)
    return ast.unparse(ast.fix_missing_locations(tree))


def validate_control(module: str, control: str, contract: dict, entries: list[dict], s: WitnessSettings) -> dict:
    """A control is valid only if it agrees with the reference (API level) on every valid A2 scenario."""
    rules = api_rules(contract)
    header = f"import {module} as {GEN_ALIAS}\n"
    cands = _run(module, control, header, [e["scenario"] for e in entries], s, rules)
    bad = []
    for e, c in zip(entries, cands):
        cmp = compare(e, c, rules)
        if cmp["api"] or cmp["nontermination"] or cmp["import_error"]:
            bad.append(e["scenario"]["scenario_id"])
    return {"valid": not bad and bool(entries), "disagreeing_scenarios": bad, "scenarios": len(entries)}
