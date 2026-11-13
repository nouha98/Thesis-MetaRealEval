"""D5: the canonical observation serializer (see the Tier 2 plan, "D5").

Turns any Python value into a deterministic, type-tagged token string so two
implementations can be compared on the same scenario. Stdlib-only, because it
runs inside the scenario subprocess (``forkserver.py``) next to arbitrary
code under test.

Policy, fixed by the plan:

* Every token carries its type: ``VALUE:<module.QualName>:<form>`` -- so
  ``1``, ``1.0`` and ``True`` never compare equal, and neither do two
  different classes that happen to share a ``repr``.
* No rounding. Floats use ``float.hex()`` (exact); NaN is one canonical
  token whatever its sign or payload; ``-0.0`` stays distinct from ``0.0``.
  Rounding would hide exactly the small behavioural differences a mutant
  introduces.
* Containers are serialized element-wise; dict entries and set elements are
  sorted by their *serialized* form, so iteration order never matters.
* Objects are their qualified type name plus their canonical ``__dict__`` /
  ``__slots__``, recursively, up to depth 6, with a cycle guard. Anything
  without inspectable state falls back to ``repr()`` with memory addresses
  stripped, tagged ``OPAQUE`` so its share can be reported -- an OPAQUE token
  is weak evidence and the write-up must say how much of it there is.
* Exceptions are ``EXC:<module.QualName>``. Messages are excluded: they often
  embed object addresses, timestamps or paths.
* Tokens longer than :data:`MAX_TOKEN_CHARS` are replaced by a sha256 digest
  plus length. Equality semantics are preserved (up to hash collision) while
  keeping traces bounded for classes that return large structures.

Masking nondeterministic call sites is :func:`nondeterminism_mask` /
:func:`traces_agree`; a trace is a ``{key: token}`` dict produced by
``forkserver._run_scenario``.
"""

from __future__ import annotations

import collections
import datetime
import decimal
import enum
import fractions
import hashlib
import math
import pathlib
import re
import types
import uuid
from typing import Any

# Stdlib value types whose repr() is exact, deterministic and address-free.
# Without this they would fall through to the OPAQUE fallback (no __dict__)
# and inflate the reported OPAQUE share with tokens that are in fact exact.
_EXACT_REPR_TYPES = (
    datetime.date, datetime.time, datetime.timedelta, datetime.timezone,
    decimal.Decimal, fractions.Fraction, pathlib.PurePath, uuid.UUID,
)

MAX_DEPTH = 6
MAX_TOKEN_CHARS = 10_000

OPAQUE_TAG = "OPAQUE"
# Memory addresses only: the default-repr " at 0x..." form, and bare
# pointer-width (>= 8 hex digit) values. Short hex such as "0xff" can be real
# data and is kept.
_ADDRESS_RE = re.compile(r"\s+at\s+0x[0-9a-fA-F]+|0x[0-9a-fA-F]{8,}")


def type_name(t: type) -> str:
    return f"{getattr(t, '__module__', '?')}.{getattr(t, '__qualname__', getattr(t, '__name__', '?'))}"


def exc_token(exc: BaseException) -> str:
    return f"EXC:{type_name(type(exc))}"


def _opaque(value: Any) -> str:
    try:
        text = repr(value)
    except BaseException as e:  # a user-defined __repr__ can raise anything
        text = f"<repr raised {type_name(type(e))}>"
    return f"{OPAQUE_TAG}<{_ADDRESS_RE.sub('', text)}>"


def _float_form(v: float) -> str:
    return "nan" if math.isnan(v) else float(v).hex()


def _canon(value: Any, depth: int, path: frozenset[int]) -> str:
    """Type-tagged canonical form of ``value``."""
    t = type(value)
    tag = type_name(t)

    # Before the primitives: an IntEnum/StrEnum member is also an int/str.
    if isinstance(value, enum.Enum):
        return f"enum:{tag}.{value.name}"
    if value is None or isinstance(value, (bool, int, str, bytes)):
        # bool is an int subclass; the tag is what keeps True and 1 apart.
        return f"{tag}:{value!r}"
    if isinstance(value, float):
        return f"{tag}:{_float_form(value)}"
    if isinstance(value, complex):
        return f"{tag}:({_float_form(value.real)},{_float_form(value.imag)})"
    if isinstance(value, types.ModuleType):
        return f"module:{value.__name__}"
    if isinstance(value, type):
        return f"type:{type_name(value)}"
    if isinstance(value, (types.FunctionType, types.BuiltinFunctionType,
                          types.MethodType, types.BuiltinMethodType)):
        return f"callable:{getattr(value, '__qualname__', getattr(value, '__name__', '?'))}"
    if isinstance(value, BaseException):
        return f"exception:{tag}"
    if isinstance(value, re.Pattern):
        return f"{tag}:{value.pattern!r}/flags={int(value.flags)}"
    if isinstance(value, _EXACT_REPR_TYPES):
        return f"{tag}:{value!r}"

    if depth >= MAX_DEPTH:
        return f"{tag}:<DEPTH>"
    if id(value) in path:
        return f"{tag}:<CYCLE>"
    path = path | {id(value)}

    if isinstance(value, (list, tuple, collections.deque)):
        inner = ",".join(_canon(v, depth + 1, path) for v in value)
        return f"{tag}:[{inner}]"
    if isinstance(value, (set, frozenset)):
        inner = ",".join(sorted(_canon(v, depth + 1, path) for v in value))
        return f"{tag}:{{{inner}}}"
    if isinstance(value, dict):
        items = sorted(
            (_canon(k, depth + 1, path), _canon(v, depth + 1, path)) for k, v in value.items()
        )
        return f"{tag}:{{{','.join(f'{k}=>{v}' for k, v in items)}}}"

    # numpy arrays (and anything shaped like one): exact via tolist(), which
    # is far more informative than their repr's "..." truncation.
    if hasattr(value, "tolist") and hasattr(value, "dtype"):
        try:
            return f"{tag}[{value.dtype}]:{_canon(value.tolist(), depth + 1, path)}"
        except BaseException:
            pass

    state = _object_state(value)
    if state is not None:
        fields = ",".join(f"{k}={_canon(v, depth + 1, path)}" for k, v in sorted(state.items()))
        return f"{tag}:<{fields}>"
    return f"{tag}:{_opaque(value)}"


def _object_state(value: Any) -> dict | None:
    """``__dict__`` plus any ``__slots__`` values, or None if neither exists.

    Reading ``__dict__`` and slot descriptors runs no user code, except a
    custom ``__getattr__`` on a missing slot -- guarded.
    """
    state: dict | None = None
    d = getattr(value, "__dict__", None)
    if isinstance(d, dict):
        state = {str(k): v for k, v in d.items()}
    for klass in type(value).__mro__:
        slots = klass.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots:
            if name in ("__dict__", "__weakref__"):
                continue
            try:
                v = object.__getattribute__(value, name)
            except BaseException:
                continue
            state = state if state is not None else {}
            state.setdefault(name, v)
    return state


def token(value: Any) -> str:
    """The canonical, type-tagged observation token for ``value``."""
    try:
        form = _canon(value, 0, frozenset())
    except RecursionError:
        form = f"{type_name(type(value))}:<RECURSION>"
    text = f"VALUE:{form}"
    if len(text) > MAX_TOKEN_CHARS:
        digest = hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()
        return f"VALUE:sha256:{digest}:len={len(text)}"
    return text


def is_opaque(tok: str) -> bool:
    return OPAQUE_TAG + "<" in tok


# ---------------------------------------------------------------------------
# API mode (extensions plan rev. 9, D1). Additive: nothing above changes, and
# the scenario runner computes API tokens only when a spec asks for them.
#
# The historical token is a *full trace* of a value: objects include their
# private ``__dict__``. The API token records only what the public contract
# exposes, as a JSON-able structure compared under the task contract's rules
# (``api_diff``): numbers by value with a tolerance, containers by family,
# mappings and sets order-insensitively, instances of the task's own class
# through contract-declared accessors (or not at all), anything else opaque
# (type recorded, never asserted), exceptions by type with isinstance
# semantics. Never repr(), private attributes or object snapshots.
# ---------------------------------------------------------------------------

API_MAX_DEPTH = 6
API_MAX_JSON_CHARS = 20_000

DEFAULT_API_RULES: dict = {
    "float_rel_tol": 0.0,
    "float_abs_tol": 0.0,
    "numeric": "python_eq",            # or "strict": int and float never equal
    "strict_container_types": False,   # list vs tuple compare by elements unless True
    "ordered_mappings": False,
    "own_classes": {},                 # qualname -> {"kind": "opaque"|"accessors", "attributes": [], "accessors": []}
}


def exc_api_token(exc: BaseException) -> list:
    """An exception as the list of its MRO type names (for isinstance comparison)."""
    return ["exc", [type_name(t) for t in type(exc).__mro__ if t is not object]]


def api_token(value: Any, rules: dict | None = None) -> list:
    rules = {**DEFAULT_API_RULES, **(rules or {})}
    try:
        tok = _api(value, rules, 0, frozenset())
    except RecursionError:
        tok = ["opaque", type_name(type(value))]
    import json as _json
    text = _json.dumps(tok)
    if len(text) > API_MAX_JSON_CHARS:
        return ["digest", hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest(), len(text)]
    return tok


def _api(value: Any, rules: dict, depth: int, path: frozenset) -> list:
    t = type(value)
    tag = type_name(t)
    if isinstance(value, enum.Enum):
        return ["enum", tag, value.name]
    if value is None:
        return ["none"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, float):
        return ["float", _float_form(value)]
    if isinstance(value, complex):
        return ["complex", _float_form(value.real), _float_form(value.imag)]
    if isinstance(value, (decimal.Decimal, fractions.Fraction)):
        return ["number", tag, str(value)]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, (bytes, bytearray)):
        return ["bytes", bytes(value).hex()]
    if isinstance(value, BaseException):
        return ["exc_value", [type_name(k) for k in t.__mro__ if k is not object]]
    if isinstance(value, _EXACT_REPR_TYPES):
        return ["exact", tag, repr(value)]
    if isinstance(value, type):
        return ["type", type_name(value)]
    if depth >= API_MAX_DEPTH:
        return ["opaque", tag]
    if id(value) in path:
        return ["opaque", tag]
    path = path | {id(value)}
    own = rules["own_classes"].get(t.__qualname__) or rules["own_classes"].get(tag)
    if own is not None:
        return _own(value, own, rules, depth, path, tag)
    if isinstance(value, (list, tuple, collections.deque, range)):
        return ["seq", tag, [_api(v, rules, depth + 1, path) for v in value]]
    if isinstance(value, (set, frozenset)):
        items = [_api(v, rules, depth + 1, path) for v in value]
        return ["set", tag, sorted(items, key=_sort_key)]
    if isinstance(value, dict):
        items = [[_api(k, rules, depth + 1, path), _api(v, rules, depth + 1, path)] for k, v in value.items()]
        if not rules["ordered_mappings"]:
            items.sort(key=lambda kv: _sort_key(kv[0]))
        return ["map", tag, items]
    if hasattr(value, "tolist") and hasattr(value, "dtype"):          # numpy arrays / scalars
        try:
            return _api(value.tolist(), rules, depth + 1, path)
        except BaseException:
            return ["opaque", tag]
    if hasattr(value, "to_dict") and str(getattr(t, "__module__", "")).startswith("pandas"):
        try:
            return _api(value.to_dict(), rules, depth + 1, path)
        except BaseException:
            return ["opaque", tag]
    return ["opaque", tag]


def _own(value: Any, own: dict, rules: dict, depth: int, path: frozenset, tag: str) -> list:
    if own.get("kind") != "accessors":
        return ["opaque", tag]
    fields: dict = {}
    for name in own.get("attributes", []):
        try:
            fields[name] = _api(getattr(value, name), rules, depth + 1, path)
        except BaseException as e:
            fields[name] = exc_api_token(e)
    for name in own.get("accessors", []):
        try:
            fields[name + "()"] = _api(getattr(value, name)(), rules, depth + 1, path)
        except BaseException as e:
            fields[name + "()"] = exc_api_token(e)
    return ["obj", tag, fields]


def _sort_key(tok: list) -> str:
    import json as _json
    return _json.dumps(tok, sort_keys=True)


def _num(tok: list):
    if tok[0] == "int":
        return int(tok[1])
    if tok[0] == "float":
        return float("nan") if tok[1] == "nan" else float.fromhex(tok[1])
    if tok[0] == "bool":
        return int(tok[1])
    if tok[0] == "number":
        return float(fractions.Fraction(tok[2])) if "/" in tok[2] else float(decimal.Decimal(tok[2]))
    raise TypeError(tok)


def api_diff(ref: Any, cand: Any, rules: dict | None = None, where: str = "") -> str | None:
    """None if ``cand`` agrees with the reference token ``ref`` under the contract rules, else
    a short description of the first difference. A reference token that is opaque is not
    asserted (no difference); an exception agrees with a reference exception when the
    candidate's type is the reference type or a subclass of it."""
    rules = {**DEFAULT_API_RULES, **(rules or {})}
    if ref is None or cand is None:
        return None if ref is cand else f"{where}: missing observation"
    kr, kc = ref[0], cand[0]
    if kr == "opaque":
        return None
    if kr == "exc" or kc == "exc":
        if kr == "exc" and kc == "exc":
            return None if ref[1][0] in cand[1] else f"{where}: raised {cand[1][0]} not a {ref[1][0]}"
        return f"{where}: {'raised ' + cand[1][0] if kc == 'exc' else 'no exception, expected ' + ref[1][0]}"
    numeric = ("int", "float", "number")
    if kr in numeric and kc in numeric and (rules["numeric"] == "python_eq" or kr == kc):
        a, b = _num(ref), _num(cand)
        if math.isnan(a) or math.isnan(b):
            return None if math.isnan(a) and math.isnan(b) else f"{where}: {a!r} != {b!r}"
        if a == b or math.isclose(a, b, rel_tol=rules["float_rel_tol"], abs_tol=rules["float_abs_tol"]):
            return None
        return f"{where}: {a!r} != {b!r}"
    if kr != kc:
        return f"{where}: {kr} != {kc}"
    if kr in ("seq", "set", "map"):
        if rules["strict_container_types"] and ref[1] != cand[1]:
            return f"{where}: container type {ref[1]} != {cand[1]}"
        a, b = ref[2], cand[2]
        if len(a) != len(b):
            return f"{where}: length {len(a)} != {len(b)}"
        if kr == "map":
            for (ka, va), (kb, vb) in zip(a, b):
                d = api_diff(ka, kb, rules, f"{where}{{key}}") or api_diff(va, vb, rules, f"{where}[{_sort_key(ka)[:40]}]")
                if d:
                    return d
            return None
        for i, (x, y) in enumerate(zip(a, b)):
            d = api_diff(x, y, rules, f"{where}[{i}]")
            if d:
                return d
        return None
    if kr == "obj":
        if ref[1] != cand[1]:
            return f"{where}: class {ref[1]} != {cand[1]}"
        for name, tok in ref[2].items():
            d = api_diff(tok, cand[2].get(name), rules, f"{where}.{name}")
            if d:
                return d
        return None
    if kr == "complex":
        a, b = complex(float.fromhex(ref[1]), float.fromhex(ref[2])), complex(float.fromhex(cand[1]), float.fromhex(cand[2]))
        return None if a == b or abs(a - b) <= max(rules["float_abs_tol"], rules["float_rel_tol"] * abs(a)) \
            else f"{where}: {a!r} != {b!r}"
    return None if ref == cand else f"{where}: {str(ref)[:60]} != {str(cand)[:60]}"


# ---------------------------------------------------------------------------
# Trace comparison
# ---------------------------------------------------------------------------

def nondeterminism_mask(run_a: dict[str, str], run_b: dict[str, str]) -> set[str]:
    """Keys whose tokens differ between two runs of the *same* implementation
    on the *same* scenario. Keys present in only one run are masked too: an
    implementation that sometimes stops early is nondeterministic there."""
    keys = set(run_a) | set(run_b)
    return {k for k in keys if run_a.get(k) != run_b.get(k)}


def traces_agree(a: dict[str, str], b: dict[str, str], mask: frozenset[str] | set[str] = frozenset()) -> bool:
    """Two implementations agree on a scenario iff their traces are equal
    outside the reference's nondeterminism mask."""
    keys = (set(a) | set(b)) - set(mask)
    return all(a.get(k) == b.get(k) for k in keys)
