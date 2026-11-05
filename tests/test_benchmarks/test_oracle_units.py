"""Tier 2 RQ4 oracle units (plan rev. 6, 8.1): which checks are units, and that
weakening one removes only the check -- execution, order and side effects stay."""

from __future__ import annotations

import gzip
import json
import sys
import types
from pathlib import Path

import pytest

from meta_real_eval.benchmarks import oracle_units as ou
from meta_real_eval.benchmarks.oracle_units import (
    ASSERT_UNIT, EXCEPTION_UNIT, OracleUnitError, find_oracle_units, min_units_for_levels,
    n_removed, removal_order, weaken_asserts,
)

SRC = '''\
import pytest
import snippet_1 as module_0
import math as module_1


def test_case_0():
    counter_0 = module_0.Counter(3)
    assert counter_0.add(2) == 5
    assert module_1.pi > 3
    var_0 = counter_0.count
    assert var_0 == 5, "count"


@pytest.mark.xfail(strict=True)
def test_case_1():
    module_0.Counter('x').add(None)


def test_case_2():
    with pytest.raises(ValueError):
        module_0.Counter(1).add(-1)


def test_case_3():
    assert module_0.Counter(0).count == 0


def test_case_4():
    assert module_0.Counter(0).count == 999
'''
BEH, EXC = {"test_case_0", "test_case_3"}, {"test_case_1", "test_case_2"}   # test_case_4: invalid


def test_units_are_class_asserts_of_behavioural_tests_and_whole_exception_tests():
    units = find_oracle_units(SRC, "snippet_1", BEH, EXC)
    assert [(u.unit_id, u.kind) for u in units] == [
        ("test_case_0#a0", ASSERT_UNIT),       # assert counter_0.add(2) == 5
        ("test_case_0#a1", ASSERT_UNIT),       # assert var_0 == 5 (var_0 derives from the class)
        ("test_case_1", EXCEPTION_UNIT),
        ("test_case_2", EXCEPTION_UNIT),
        ("test_case_3#a0", ASSERT_UNIT),
    ]                                          # module_1.pi > 3 is environment; test_case_4 is invalid


def test_weakening_rewrites_only_the_named_asserts_and_keeps_every_other_byte():
    out = weaken_asserts(SRC, "snippet_1", BEH, EXC, ["test_case_0#a1"])
    assert "    (var_0 == 5)\n" in out and "assert var_0" not in out
    assert out.replace("    (var_0 == 5)\n", '    assert var_0 == 5, "count"\n') == SRC


def test_no_assert_unit_named_returns_the_source_itself():
    assert weaken_asserts(SRC, "snippet_1", BEH, EXC, []) is SRC
    # an exception unit leaves through the suite's subset, never by editing the file
    assert weaken_asserts(SRC, "snippet_1", BEH, EXC, ["test_case_1", "test_case_2"]) is SRC


# --- execution is preserved -------------------------------------------------------------

def _module(log: list):
    class Value:
        def __init__(self, v):
            self.v = v

        def __eq__(self, other):              # the comparison operator is part of the evaluation
            log.append(("eq", self.v, other))
            return self.v == other

    class Counter:
        def __init__(self, start=0):
            self.count = start

        def add(self, n):
            log.append(("add", n))
            if n == 13:
                raise RuntimeError("crash")
            self.count += n
            return Value(self.count)

    m = types.ModuleType("snippet_9")
    m.Counter = Counter
    return m


def _run(src: str, fn: str, log: list):
    sys.modules["snippet_9"] = _module(log)
    try:
        ns: dict = {}
        exec(compile(src, "test_snippet_9.py", "exec"), ns)
        ns[fn]()
    finally:
        sys.modules.pop("snippet_9", None)


EXEC_SRC = '''\
import snippet_9 as module_0


def test_value():
    counter_0 = module_0.Counter(1)
    assert counter_0.add(2) == 99, "wrong on purpose"
    assert counter_0.add(1) == 4


def test_crash():
    counter_0 = module_0.Counter(1)
    assert counter_0.add(13) == 14
'''


def test_a_weakened_assert_still_evaluates_its_expression_with_every_side_effect():
    original, weakened = [], []
    with pytest.raises(AssertionError):
        _run(EXEC_SRC, "test_value", original)
    units = [u.unit_id for u in find_oracle_units(EXEC_SRC, "snippet_9", {"test_value", "test_crash"}, set())]
    out = weaken_asserts(EXEC_SRC, "snippet_9", {"test_value", "test_crash"}, set(), units)
    _run(out, "test_value", weakened)                     # the wrong value no longer fails the test ...
    assert original == [("add", 2), ("eq", 3, 99)]         # (the original stopped at the failed check)
    assert weakened == [("add", 2), ("eq", 3, 99), ("add", 1), ("eq", 4, 4)]   # ... and the rest still runs


def test_a_crash_inside_a_weakened_assert_still_fails_the_test():
    units = [u.unit_id for u in find_oracle_units(EXEC_SRC, "snippet_9", {"test_value", "test_crash"}, set())]
    out = weaken_asserts(EXEC_SRC, "snippet_9", {"test_value", "test_crash"}, set(), units)
    with pytest.raises(RuntimeError, match="crash"):
        _run(out, "test_crash", [])


SHAPES = '''\
import snippet_9 as module_0


def test_shapes():
    c = module_0.Counter(0)
    assert (c.count ==
            0), "multi-line, parenthesised, with a message"
    assert c.count == \\
        0
    assert c.count == 0  # a trailing comment
    assert c.count != 'café ☕'
    assert not c.count
    assert c.count and c.add(13)
    assert 0 <= c.count < 10
    v = c.count; assert v == 0
'''


def test_every_assert_shape_is_weakened_to_the_same_expression_and_short_circuits_are_kept():
    units = find_oracle_units(SHAPES, "snippet_9", {"test_shapes"}, set())
    assert len(units) == 8
    out = weaken_asserts(SHAPES, "snippet_9", {"test_shapes"}, set(), [u.unit_id for u in units])
    assert "assert" not in out.split("def test_shapes")[1]
    log: list = []
    _run(out, "test_shapes", log)      # c.count is 0: `and` must not evaluate c.add(13), which crashes
    assert log == []


def test_the_self_check_rejects_a_rewrite_that_is_not_the_intended_ast(monkeypatch):
    class Wrong(ou._Weaken):
        def visit_Assert(self, node):
            return node                         # "forgets" to replace: the AST check must catch it
    monkeypatch.setattr(ou, "_Weaken", Wrong)
    with pytest.raises(OracleUnitError):
        weaken_asserts(SRC, "snippet_1", BEH, EXC, ["test_case_0#a0"])


# --- levels ------------------------------------------------------------------------------

def test_levels_round_up_are_nested_and_seeded_per_task():
    units = find_oracle_units(SRC, "snippet_1", BEH, EXC)
    order = removal_order(units, "42|task")
    assert order == removal_order(units, "42|task") and sorted(order) == sorted(u.unit_id for u in units)
    assert [n_removed(5, lv) for lv in (0.0, 0.2, 0.5, 0.8, 1.0)] == [0, 1, 3, 4, 5]
    prefixes = [set(order[:n_removed(5, lv)]) for lv in (0.0, 0.2, 0.5, 0.8)]
    assert all(a <= b for a, b in zip(prefixes, prefixes[1:]))


def test_the_eligibility_threshold_follows_from_the_levels():
    assert min_units_for_levels([0.0, 0.2, 0.5, 0.8]) == 5       # 4 - ceil(3.2) = 0, 5 - ceil(4.0) = 1
    assert min_units_for_levels([0.0, 0.5]) == 2


# --- the real corpus -----------------------------------------------------------------------

CORPUS = Path(__file__).resolve().parents[2] / "data" / "realclasseval" / "realclasseval_v1.jsonl.gz"


@pytest.mark.skipif(not CORPUS.exists(), reason="RealClassEval corpus not staged")
def test_every_real_pynguin_file_survives_every_level():
    """Static, over all staged test files (validity approximated from the source:
    the gate's verdicts live in the manifest on the cluster): every level's rewrite
    passes the AST self-check and compiles."""
    from meta_real_eval.benchmarks.outcomes import static_test_info
    n = 0
    with gzip.open(CORPUS, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            src = row["test_code"]
            if f"import {row['snippet_id']} as" not in src:
                continue                          # never imports the class: not an accepted task
            st = static_test_info(src)
            exc = {t for t, s in st.items() if s.has_xfail_marker or s.has_pytest_raises}
            units = find_oracle_units(src, row["snippet_id"], set(st) - exc, exc)
            order = removal_order(units, f"42|{row['task_id']}")
            for level in (0.2, 0.5, 0.8, 1.0):
                compile(weaken_asserts(src, row["snippet_id"], set(st) - exc, exc,
                                       order[:n_removed(len(units), level)]), "t", "exec")
            n += 1
    assert n > 400
