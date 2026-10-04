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
