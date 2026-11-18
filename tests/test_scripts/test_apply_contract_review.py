"""scripts/apply_contract_review.py: edits turn a draft into a usable reviewed contract, and the committed
decisions cover every reviewed contract exactly."""

import copy
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import apply_contract_review as acr  # noqa: E402


def draft():
    param = {"name": "x", "kind": "positional", "type": {"t": "any"}, "type_source": "none", "hints": [],
             "constraints": {}, "has_default": False, "default": None, "generate": False, "why": "no type"}
    return {"class_name": "C", "constructor": {"params": []}, "properties": [], "attributes": [],
            "comparison": {"own_classes": {"C": {"kind": "opaque", "attributes": [], "accessors": []}}},
            "methods": {"m": {"kind": "method", "async": False, "generate": False, "raises_documented": [],
                              "why": "a required parameter cannot be generated", "params": [param]}},
            "support": {"supported": False, "reasons": ["no public method or property can be generated"]}}


def test_a_typed_parameter_makes_the_method_generatable_and_the_task_supported():
    c = draft()
    acr.apply_edit(c, {"param": "m.x", "type": "dict[str, int | str]"})
    acr.finish(c)
    p = c["methods"]["m"]["params"][0]
    assert p["type_source"] == "review" and p["generate"] and p["type"]["t"] == "dict"
    assert c["methods"]["m"]["generate"] and c["support"]["supported"]
    assert c["support"]["generatable_methods"] == ["m"] and c["support"]["reasons"] == []


def test_a_method_the_review_ungenerates_stays_ungenerated():
    c = draft()
    acr.apply_edit(c, {"param": "m.x", "type": "int"})
    acr.apply_edit(c, {"method": "m", "generate": False})
    acr.finish(c)
    assert not c["methods"]["m"]["generate"] and not c["support"]["supported"]
    assert "no public method or property can be generated" in c["support"]["reasons"]


def test_untyped_parameter_without_hints_is_refused_and_unknown_names_fail_loudly():
    c = draft()
    with pytest.raises(ValueError):
        acr.apply_edit(c, {"param": "m.x", "type": "any", "hints": []})
    with pytest.raises(KeyError):
        acr.apply_edit(copy.deepcopy(c), {"param": "m.nope", "type": "int"})
    with pytest.raises(KeyError):
        acr.apply_edit(copy.deepcopy(c), {"method": "nope", "generate": False})
    with pytest.raises(ValueError):
        acr.parse_type("SomeFrameworkClass")


def test_added_parameter_own_class_and_opaque_hint():
    c = draft()
    acr.apply_edit(c, {"add_param": "m.y", "type": "str", "hints": ["a"]})
    acr.apply_edit(c, {"param": "m.x", "type": "any", "hints": [None]})
    acr.apply_edit(c, {"own_class": ["role", "content"]})
    acr.finish(c)
    assert [p["name"] for p in c["methods"]["m"]["params"]] == ["y", "x"] and c["methods"]["m"]["generate"]
    assert c["comparison"]["own_classes"]["C"] == {"kind": "accessors", "attributes": ["role", "content"], "accessors": []}
    assert c["attributes"] == ["content", "role"]


def test_committed_decisions_match_the_reviewed_contracts():
    if not acr.DECISIONS.exists():
        pytest.skip("no decisions file")
    decisions = json.loads(acr.DECISIONS.read_text(encoding="utf-8"))
    for label, d in decisions.items():
        c = acr.load_contract(acr.REVIEWED / f"{label}.json")
        assert c["review"]["status"] == "reviewed" and c["review"]["verdict"] == d["verdict"], label
        assert c["support"]["supported"] == (d["verdict"] != "reject"), label
