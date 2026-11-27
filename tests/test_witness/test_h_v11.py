"""H v1.1 (decisions 10.8): Fix A (object fields follow their own R7 level), the unchanged v1 comparison path,
the subset rule, the Fix B annotation mapping and the cluster C exception-caused flag."""

import ast
import sys
from pathlib import Path

from meta_real_eval.benchmarks.observe import api_diff
from meta_real_eval.oracles.regression import expected_tokens, restrict_fields
from meta_real_eval.oracles.spec import spec_diff

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import grade_hidden as gh  # noqa: E402
import h_v11  # noqa: E402

OBJ = ["obj", "m.C", {"prop": ["str", "Property"], "payload()": ["map", "builtins.dict", []], "attr": ["int", "1"]}]
LEVELS = {"prop": "none", "payload": "type"}


def test_fix_a_restricts_fields_and_drops_unspecified_attributes():
    r = restrict_fields(OBJ, LEVELS)
    assert r == ["obj", "m.C", {"prop": ["@any"], "payload()": ["@type", ["map"]]}]
    assert restrict_fields(["str", "x"], LEVELS) == ["str", "x"]                 # not an object: unchanged
    entry = {"scenario": {"steps": [{"src": "module_0.C()"}], "api_flags": [True]}, "ref": {"tokens": {"api:s0": OBJ}},
             "api_mask": [], "valid_prefix": 1}
    assert expected_tokens(entry, LEVELS, "C")["api:s0"] == OBJ                  # v1 behaviour (no Fix A)
    assert expected_tokens(entry, LEVELS, "C", fix_a=True)["api:s0"] == restrict_fields(OBJ, LEVELS)


def test_v1_tokens_compare_exactly_as_before():
    """The frozen v1 tests import spec_diff at run time: on v1 tokens it must equal api_diff."""
    cands = [OBJ, ["obj", "m.C", {"prop": ["none"], "payload()": ["map", "builtins.dict", []], "attr": ["int", "1"]}],
             ["obj", "m.D", OBJ[2]], ["str", "x"], None, ["exc", ["builtins.ValueError"]]]
    for c in cands:
        assert spec_diff(OBJ, c, None, "k") == api_diff(OBJ, c, None, "k")


def test_restricted_objects_compare_field_by_field():
    exp = restrict_fields(OBJ, LEVELS)
    other = ["obj", "m.C", {"prop": ["none"], "payload()": ["map", "builtins.dict", [[["str", "a"], ["int", "1"]]]]}]
    assert spec_diff(exp, other) is None                                          # other prop value, other dict
    assert "class" in spec_diff(exp, ["obj", "m.D", other[2]])
    assert "expected type" in spec_diff(exp, ["obj", "m.C", {"prop": ["none"], "payload()": ["seq", "builtins.list", []]}])
    assert "missing" in spec_diff(exp, None) and "expected an object" in spec_diff(exp, ["str", "x"])


def test_subset_rule():
    assert h_v11.implied(["@any"], ["str", "x"]) and not h_v11.implied(["@any"], ["exc", ["builtins.ValueError"]])
    assert h_v11.implied(["@type", ["str"]], ["str", "x"]) and not h_v11.implied(["@type", ["seq"]], ["str", "x"])
    assert h_v11.implied(restrict_fields(OBJ, LEVELS), OBJ)
    assert not h_v11.implied(["str", "y"], ["str", "x"]) and h_v11.implied(["str", "x"], ["str", "x"])


def test_annotation_families():
    fam = lambda s: h_v11.annotation_families(ast.parse(s, mode="eval").body)  # noqa: E731
    assert fam("List[str]") == {"seq"} and fam("Set[str]") == {"set"} and fam("Dict[str, int]") == {"map"}
    assert fam("Optional[str]") == {"str", "none"} and fam("str | None") == {"str", "none"}
    assert fam("Union[int, str]") == {"number", "str"} and fam("'Foo'") == {"class:Foo"} and fam("None") == {"none"}
    assert fam("Any") is None and fam("Iterable[str]") is None
    assert h_v11.family_allowed(("object", "snippet_1.Foo"), {"class:Foo"})
    assert not h_v11.family_allowed(("set",), {"seq"})             # post_165: the reference's set vs -> List[str]


def test_type_entries_cover_steps_and_object_fields():
    a2 = {"final_tests": [{"steps": [{"src": "module_0.C()"}, {"src": "obj.get()"}, {"src": "obj.size()"}],
                           "expected": {"api:s0": ["obj", "m.C", {"payload()": ["map", "builtins.dict", []]}],
                                        "api:s1": ["@type", ["set"]], "api:s2": ["@type", ["number"]]}}]}
    found = h_v11.type_entries(a2, {"get": "type", "payload": "type"}, "C")
    assert found["get"]["families"] == {("set",)} and found["payload"]["families"] == {("map",)}
    assert found["size"]["defaulted"] is True                                     # not listed: the default level


def test_exception_caused():
    t = {"steps": [{"src": "module_0.C()"}, {"src": "obj.f()"}, {"src": "obj.g()"}],
         "expected": {"api:s1": ["@any"], "api:s2": ["str", "x"]}}
    assert gh.exception_caused(t, {"tokens": {"s0": "obj", "s1": "EXC:builtins.ValueError"}}, {})
    assert not gh.exception_caused(t, {"tokens": {"s1": "ok", "api:s1": ["str", "y"], "s2": "ok",
                                                  "api:s2": ["str", "z"]}}, {})                  # no exception at all
    t2 = {**t, "expected": {"api:s0": ["str", "a"], "api:s2": ["str", "x"]}}
    assert not gh.exception_caused(t2, {"tokens": {"api:s0": ["str", "b"], "s2": "EXC:builtins.KeyError"}}, {})
    t3 = {**t, "expected": {"api:s1": ["exc", ["builtins.ValueError"]]}}
    assert not gh.exception_caused(t3, {"tokens": {"s1": "EXC:builtins.ValueError"}}, {})      # documented raise


def test_multi_kind_annotation_becomes_none(tmp_path, monkeypatch):
    """post_218 `value -> str | None`: the reference returns None; asserting kind none would reject a str."""
    allowed = h_v11.annotation_families(ast.parse("str | None", mode="eval").body)
    assert allowed == {"str", "none"} and len(allowed) > 1          # the build rule then sets the entry to none
