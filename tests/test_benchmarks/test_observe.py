"""D5 unit tests: the canonical observation serializer."""

from __future__ import annotations

import enum
import math

import pytest

from meta_real_eval.benchmarks.observe import (
    MAX_TOKEN_CHARS,
    exc_token,
    is_opaque,
    nondeterminism_mask,
    token,
    traces_agree,
)


# --- type tags --------------------------------------------------------------

def test_int_float_bool_are_distinct():
    assert len({token(1), token(1.0), token(True)}) == 3


def test_type_tag_is_qualified():
    assert token(3) == "VALUE:builtins.int:3"


def test_none():
    assert token(None) == "VALUE:builtins.NoneType:None"


# --- floats: exact, no rounding ---------------------------------------------

def test_float_uses_hex_and_does_not_round():
    assert token(0.1) != token(0.1 + 1e-15)
    assert "0x1.999999999999ap-4" in token(0.1)


def test_nan_is_one_canonical_token():
    assert token(float("nan")) == token(-float("nan")) == token(math.nan)


def test_negative_zero_is_distinct():
    assert token(-0.0) != token(0.0)


def test_inf():
    assert token(float("inf")) != token(float("-inf"))


# --- containers: order-insensitive where Python is -------------------------

def test_set_order_does_not_matter():
    assert token({3, 1, 2}) == token({2, 3, 1})


def test_dict_insertion_order_does_not_matter():
    assert token({"a": 1, "b": 2}) == token({"b": 2, "a": 1})


def test_list_order_matters():
    assert token([1, 2]) != token([2, 1])


def test_list_and_tuple_are_distinct():
    assert token([1, 2]) != token((1, 2))


def test_nested_element_types_are_tagged():
    assert token([1]) != token([1.0])


# --- objects ----------------------------------------------------------------

class _Point:
    def __init__(self, x, y):
        self.x, self.y = x, y


class _Slotted:
    __slots__ = ("a",)

    def __init__(self, a):
        self.a = a


def test_object_state_is_serialized():
    assert token(_Point(1, 2)) == token(_Point(1, 2))
    assert token(_Point(1, 2)) != token(_Point(1, 3))


def test_object_type_matters_even_with_same_state():
    class Other:
        def __init__(self, x, y):
            self.x, self.y = x, y
    assert token(_Point(1, 2)) != token(Other(1, 2))


def test_slots_are_serialized():
    assert token(_Slotted(1)) != token(_Slotted(2))


def test_cycle_guard():
    a = _Point(1, 2)
    a.self_ref = a
    tok = token(a)
    assert "<CYCLE>" in tok


def test_depth_limit():
    v: list = []
    for _ in range(20):
        v = [v]
    assert "<DEPTH>" in token(v)


def test_object_without_state_is_opaque_and_address_free():
    tok = token(object())
    assert is_opaque(tok)
    assert "0x" not in tok


def test_opaque_keeps_short_hex_data():
    class R:
        __slots__ = ()

        def __repr__(self):
            return "R(0xff)"
    assert "0xff" in token(R())


def test_enum_member():
    class Color(enum.IntEnum):
        RED = 1
    assert token(Color.RED) != token(1)
    assert "Color.RED" in token(Color.RED)


def test_exact_stdlib_value_types_are_not_opaque():
    import collections
    import datetime
    import decimal
    import re
    for v in (re.compile(r"\W+"), datetime.datetime(2024, 1, 2, 3, 4, 5),
              decimal.Decimal("1.10"), collections.deque([1, 2])):
        assert not is_opaque(token(v)), v
    assert token(re.compile("a")) != token(re.compile("a", re.I))
    assert token(decimal.Decimal("1.1")) != token(decimal.Decimal("1.10"))


def test_numpy_array_is_exact_not_truncated():
    np = pytest.importorskip("numpy")
    a = np.arange(5000)
    b = a.copy()
    b[2500] = -1  # hidden behind "..." in numpy's own repr
    assert token(a) != token(b)


def test_repr_that_raises_does_not_crash():
    class Bad:
        __slots__ = ()

        def __repr__(self):
            raise RuntimeError("no repr for you")
    assert is_opaque(token(Bad()))


def test_long_tokens_are_hashed_but_still_discriminate():
    big = list(range(MAX_TOKEN_CHARS))
    other = big[:-1] + [-1]
    assert token(big).startswith("VALUE:sha256:")
    assert token(big) != token(other)
    assert token(big) == token(list(big))


# --- exceptions -------------------------------------------------------------

def test_exc_token_excludes_message():
    assert exc_token(ValueError("a")) == exc_token(ValueError("b")) == "EXC:builtins.ValueError"


# --- trace comparison -------------------------------------------------------

def test_nondeterminism_mask_and_masked_agreement():
    run1 = {"s0": "VALUE:builtins.int:1", "s1": "VALUE:builtins.float:0x1.0p+0"}
    run2 = {"s0": "VALUE:builtins.int:1", "s1": "VALUE:builtins.float:0x1.8p+0"}
    mask = nondeterminism_mask(run1, run2)
    assert mask == {"s1"}
    other_impl = {"s0": "VALUE:builtins.int:1", "s1": "anything"}
    assert traces_agree(run1, other_impl, mask)
    assert not traces_agree(run1, {"s0": "VALUE:builtins.int:2", "s1": "x"}, mask)


def test_missing_key_is_a_disagreement():
    """An implementation that stops early (exception at s1) disagrees with one
    that runs to s2."""
    assert not traces_agree({"s0": "a", "s1": "b", "s2": "c"}, {"s0": "a", "s1": "EXC:x"})
