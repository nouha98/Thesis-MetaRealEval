"""scripts/audit_llm_mutants.py: edit scope, edit size and duplicate flags on synthetic mutants."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import audit_llm_mutants as am  # noqa: E402

REF = '''import math

class Acc:
    """An accumulator."""
    LIMIT = 10

    def __init__(self, start=0):
        """Start value."""
        self.total = start

    def add(self, x):
        if x > 0:
            self.total += x
        return self.total

    def norm(self):
        return math.sqrt(self.total)
'''


def mutate(old, new, src=REF):
    assert old in src
    return src.replace(old, new, 1)


def test_single_method_edit_names_the_method():
    r = am.compare(REF, mutate("if x > 0:", "if x >= 0:"))
    assert r["scope"] == "single_function" and r["functions_changed"] == ["Acc.add"]
    assert r["inferred_method"] == "Acc.add" and r["changed_lines"] == 2 and r["node_edit"] >= 1
    assert not r["signature_changed"] and not r["imports_changed"]


def test_two_methods_and_signature_change():
    m = mutate("if x > 0:", "if x < 0:", mutate("def __init__(self, start=0):", "def __init__(self, start=1):"))
    r = am.compare(REF, m)
    assert r["scope"] == "multi_function" and r["n_functions_touched"] == 2
    assert r["signature_changed"] == ["Acc.__init__"] and r["inferred_method"] is None


def test_docstring_only_is_not_a_code_change():
    r = am.compare(REF, mutate('"""Start value."""', '"""Initial value."""'))
    assert r["scope"] == "docstring_only" and r["changed_lines"] == 0
    assert am.compare(REF, REF)["scope"] == "identical"


def test_changes_outside_functions():
    r = am.compare(REF, mutate("LIMIT = 10", "LIMIT = 11"))
    assert r["scope"] == "outside_functions_only" and r["class_level_changed"]
    r = am.compare(REF, mutate("import math", "import math\nimport os"))
    assert r["scope"] == "outside_functions_only" and r["imports_changed"]
    r = am.compare(REF, mutate("import math", "import cmath as math", mutate("if x > 0:", "if x > 1:")))
    assert r["scope"] == "single_function_plus_outside"


def test_unparseable_mutant():
    assert am.compare(REF, "class Acc(:\n") == {"parse_ok": False}


def test_duplicate_flags_within_and_across_models():
    a = mutate("if x > 0:", "if x >= 0:")
    a_doc = mutate('"""An accumulator."""', '"""Accumulates."""', a)
    recs = [{"task": "t", "model": "m1", "norm": am.normalise(a), "norm_nd": am.normalise_no_doc(a)},
            {"task": "t", "model": "m1", "norm": am.normalise(a_doc), "norm_nd": am.normalise_no_doc(a_doc)},
            {"task": "t", "model": "m2", "norm": am.normalise(a), "norm_nd": am.normalise_no_doc(a)},
            {"task": "u", "model": "m2", "norm": am.normalise(a), "norm_nd": am.normalise_no_doc(a)}]
    am._mark_duplicates(recs)
    assert [r["within_model_copy"] for r in recs] == [False, False, False, False]
    assert [r["within_model_copy_ignoring_docstrings"] for r in recs] == [False, True, False, False]
    assert [r["cross_model_shared"] for r in recs] == [True, False, True, False]
    assert recs[3]["group_size"] == 1                      # other task: never a duplicate
