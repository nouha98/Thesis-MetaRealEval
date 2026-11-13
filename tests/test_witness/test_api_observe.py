"""D1: the API-mode serializer and contract-based comparison (observe.api_token / api_diff)."""

import json

import pytest

from meta_real_eval.benchmarks.observe import api_diff, api_token, exc_api_token


class Box:
    """Stands in for the task's own class."""

    def __init__(self, size, secret):
        self.size = size
        self._secret = secret

    def area(self):
        return self.size * self.size


class Other:
    def __init__(self):
        self.x = 1


OPAQUE = {"own_classes": {"Box": {"kind": "opaque"}}}
ACCESSORS = {"own_classes": {"Box": {"kind": "accessors", "attributes": ["size"], "accessors": ["area"]}}}


def test_tokens_are_json_and_never_carry_private_state():
    tok = api_token({"b": [1, 2.5, None], "a": Box(3, "hidden")}, ACCESSORS)
    text = json.dumps(tok)
    assert "hidden" not in text and "_secret" not in text
    assert "area()" in text and '"size"' in text


def test_own_class_comparison_is_contract_based():
    a, b, c = Box(3, "x"), Box(3, "completely different private state"), Box(4, "x")
    # opaque (default): returned instances are never asserted
    assert api_diff(api_token(a, OPAQUE), api_token(c, OPAQUE), OPAQUE) is None
    # accessors: projection onto documented attributes / accessors, private state ignored
    assert api_diff(api_token(a, ACCESSORS), api_token(b, ACCESSORS), ACCESSORS) is None
    assert api_diff(api_token(a, ACCESSORS), api_token(c, ACCESSORS), ACCESSORS) is not None


def test_unknown_objects_are_opaque_and_not_asserted():
    tok = api_token(Other())
    assert tok[0] == "opaque"
    assert api_diff(tok, api_token(Other()), {}) is None


def test_mappings_and_sets_are_order_insensitive_unless_ordered():
    assert api_diff(api_token({"a": 1, "b": 2}), api_token({"b": 2, "a": 1})) is None
    assert api_diff(api_token({3, 1, 2}), api_token({2, 3, 1})) is None
    rules = {"ordered_mappings": True}
    assert api_diff(api_token({"a": 1, "b": 2}, rules), api_token({"b": 2, "a": 1}, rules), rules) is not None


def test_containers_compare_by_family_unless_strict():
    assert api_diff(api_token([1, 2]), api_token((1, 2))) is None
    strict = {"strict_container_types": True}
    assert api_diff(api_token([1, 2]), api_token((1, 2)), strict) is not None


def test_numbers_use_the_contract_tolerance_and_numeric_rule():
    assert api_diff(api_token(0.1 + 0.2), api_token(0.3)) is not None             # exact by default
    tol = {"float_rel_tol": 1e-9, "float_abs_tol": 1e-12}
    assert api_diff(api_token(0.1 + 0.2), api_token(0.3), tol) is None
    assert api_diff(api_token(2), api_token(2.0)) is None                         # python_eq
    assert api_diff(api_token(2), api_token(2.0), {"numeric": "strict"}) is not None
    assert api_diff(api_token(True), api_token(1)) is not None                    # bool is not a number
    assert api_diff(api_token(float("nan")), api_token(float("nan"))) is None


def test_exceptions_compare_by_isinstance_never_by_message():
    ref = exc_api_token(LookupError("a"))
    assert api_diff(ref, exc_api_token(KeyError("other message"))) is None        # subclass accepted
    assert api_diff(exc_api_token(KeyError("x")), exc_api_token(LookupError("x"))) is not None
    assert api_diff(ref, api_token(3)) is not None
    assert api_diff(api_token(3), exc_api_token(ValueError())) is not None


def test_numpy_arrays_compare_by_value():
    np = pytest.importorskip("numpy")
    tol = {"float_rel_tol": 1e-9}
    assert api_diff(api_token(np.array([1.0, 2.0])), api_token([1.0, 2.0]), tol) is None
    assert api_diff(api_token(np.array([1.0, 2.0])), api_token(np.array([1.0, 2.5]))) is not None


def test_scenario_runner_api_mode_is_additive():
    from meta_real_eval.benchmarks.forkserver import run_scenarios
    code = "class Box:\n    def __init__(self, n):\n        self.n = n\n        self._p = [n]\n    def double(self):\n        return self.n * 2\n"
    sc = {"scenario_id": "s", "steps": [{"kind": "exec", "src": "module_0.Box(2)", "target": "b", "expected_exc": None},
                                        {"kind": "exec", "src": "b.double()", "target": "r", "expected_exc": None}]}
    plain = run_scenarios("box_mod", code, "import box_mod as module_0\n", [sc], timeout_s=10)[0]
    assert not any(k.startswith("api:") for k in plain["tokens"])
    api = run_scenarios("box_mod", code, "import box_mod as module_0\n", [{**sc, "api_flags": [True, True]}],
                        timeout_s=10, api_rules={"own_classes": {"Box": {"kind": "opaque"}}})[0]
    assert {k: v for k, v in api["tokens"].items() if not k.startswith("api:")} == plain["tokens"]
    assert api["tokens"]["api:s0"] == ["opaque", "box_mod.Box"] and api["tokens"]["api:s1"] == ["int", "4"]
