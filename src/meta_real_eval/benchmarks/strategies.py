"""Hypothesis strategies from task contracts (extensions plan rev. 9, Stage 2).

Generates **scenario data** in the existing scenario format (``scenarios.py``):
a constructor step binding ``obj`` and up to ``max_calls`` public calls on it,
each binding ``r<i>``. Every step is an API-visible observation by
construction (``api_flags`` all true). Values are drawn inside the contract:
the parameter's type spec, its documented constraints, and its value hints.

Safety and determinism:

* generated strings use :data:`SAFE_ALPHABET` (no path separators, no colon)
  and never contain ``..``: a class that writes files can only do so relative
  to the scenario's temporary working directory;
* set literals are written with sorted elements, so a scenario's source does
  not depend on hash randomisation;
* :func:`generate_scenarios` is seeded per task and pinned to the Hypothesis
  version in ``pyproject.toml``.

Shrinking of distinguishing scenarios is done by the witness engine on this
structured form (``meta``): steps are removed and arguments simplified while
the difference persists.
"""

from __future__ import annotations

import hashlib
import json
import math
import string
from typing import Any, Optional

from hypothesis import HealthCheck, Phase, given, seed, settings
from hypothesis import strategies as st

from .contracts import UNSUPPORTED, value_ok

SAFE_ALPHABET = string.ascii_letters + string.digits + " _-."
OMIT = object()          # an omitted optional argument (never a drawable value)
CTOR_TARGET = "obj"


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------

def _hashable_spec(spec: dict) -> bool:
    return spec["t"] in ("int", "float", "str", "bool", "none", "bytes", "any") or \
        (spec["t"] == "tuple" and not spec.get("variadic") and all(_hashable_spec(s) for s in spec["items"])) or \
        (spec["t"] == "union" and all(_hashable_spec(o) for o in spec["options"]))


def typed_strategy(spec: Optional[dict]) -> Optional[st.SearchStrategy]:
    """A strategy for a type spec, or None if it cannot be generated without hints."""
    if spec is None:
        return None
    t = spec["t"]
    if t == "int":
        return st.integers(min_value=-1000, max_value=1000)
    if t == "float":
        return st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
    if t == "str":
        return st.text(alphabet=SAFE_ALPHABET, max_size=12).filter(lambda s: ".." not in s)
    if t == "bool":
        return st.booleans()
    if t == "none":
        return st.none()
    if t == "bytes":
        return st.binary(max_size=12)
    if t == "union":
        opts = [s for s in (typed_strategy(o) for o in spec["options"]) if s is not None]
        return st.one_of(opts) if opts else None
    if t in ("list", "set"):
        item = typed_strategy(spec["items"]) if spec["items"]["t"] != "any" else _default_items()
        if item is None:
            return None
        if t == "set":
            if not _hashable_spec(spec["items"]):
                return None
            return st.sets(item, max_size=4)
        return st.lists(item, max_size=5)
    if t == "tuple":
        if spec.get("variadic"):
            item = typed_strategy(spec["items"]) if spec["items"]["t"] != "any" else _default_items()
            return None if item is None else st.lists(item, max_size=4).map(tuple)
        parts = [typed_strategy(s) for s in spec["items"]]
        return None if any(p is None for p in parts) else st.tuples(*parts)
    if t == "dict":
        keys = typed_strategy(spec["keys"]) if spec["keys"]["t"] != "any" else typed_strategy({"t": "str"})
        vals = typed_strategy(spec["values"]) if spec["values"]["t"] != "any" else _default_items()
        if keys is None or vals is None or not _hashable_spec(spec["keys"] if spec["keys"]["t"] != "any" else {"t": "str"}):
            return None
        return st.dictionaries(keys, vals, max_size=4)
    return None        # any (without hints), self, unsupported


def _default_items() -> st.SearchStrategy:
    """Items of a container whose element type the documentation leaves open: small ints or
    safe strings (recorded as ``unspecified_items`` in the contract for the reviewer)."""
    return st.one_of(st.integers(min_value=-100, max_value=100),
                     st.text(alphabet=SAFE_ALPHABET, max_size=6).filter(lambda s: ".." not in s))


def param_strategy(p: dict) -> Optional[st.SearchStrategy]:
    """Values for one parameter: contract-valid hints and/or typed values, filtered by constraints."""
    spec, cons = p["type"], p.get("constraints") or {}
    hints = [h for h in p.get("hints", []) if value_ok(h, spec if spec["t"] not in ("any", UNSUPPORTED) else None, cons)]
    typed = typed_strategy(spec) if spec["t"] not in ("any", UNSUPPORTED) else None
    parts = ([st.sampled_from(hints)] if hints else []) + ([typed] if typed is not None else [])
    if not parts:
        return None
    s = st.one_of(parts)
    if cons:
        s = s.filter(lambda v: value_ok(v, None, cons))
    return s


# ---------------------------------------------------------------------------
# Calls and scenarios
# ---------------------------------------------------------------------------

def literal_src(v: Any) -> str:
    """Python source for a generated value (deterministic: sets sorted, non-finite floats spelled)."""
    if isinstance(v, float) and not math.isfinite(v):
        return f"float({str(v)!r})"
    if isinstance(v, (set, frozenset)):
        if not v:
            return "set()"
        return "{" + ", ".join(sorted((literal_src(x) for x in v))) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(literal_src(x) for x in v) + "]"
    if isinstance(v, tuple):
        return "(" + ", ".join(literal_src(x) for x in v) + ("," if len(v) == 1 else "") + ")"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{literal_src(k)}: {literal_src(x)}" for k, x in v.items()) + "}"
    return repr(v)


def args_strategy(params: list[dict]) -> Optional[st.SearchStrategy]:
    """{"args": [...], "kwargs": {...}} for a callable, or None if a required parameter cannot be generated."""
    pos, kw, star = [], {}, None
    for p in params:
        s = param_strategy(p) if p["kind"] != "varkw" else None
        if p["kind"] == "varargs":
            star = st.lists(s, max_size=3) if s is not None else st.just([])
            continue
        if p["kind"] == "varkw":
            continue
        if s is None:
            if not p["has_default"]:
                return None
            s = st.just(OMIT)
        elif p["has_default"]:
            s = st.one_of(st.just(OMIT), s)
        (kw.__setitem__(p["name"], s) if p["kind"] == "keyword_only" else pos.append((p["name"], s)))

    @st.composite
    def draw(d):
        args, kwargs, omitted = [], {}, False
        for name, s in pos:
            v = d(s)
            if v is OMIT:
                omitted = True          # later positionals go by keyword
                continue
            (kwargs.__setitem__(name, v) if omitted else args.append(v))
        if star is not None and not omitted:
            args += d(star)
        for name, s in kw.items():
            v = d(s)
            if v is not OMIT:
                kwargs[name] = v
        return {"args": args, "kwargs": kwargs}
    return draw()


def call_src(callable_name: str, kind: str, call: Optional[dict], class_ref: str) -> str:
    def arglist(c: dict) -> str:
        parts = [literal_src(a) for a in c["args"]] + [f"{k}={literal_src(v)}" for k, v in c["kwargs"].items()]
        return ", ".join(parts)
    if callable_name == "__init__":
        return f"{class_ref}({arglist(call)})"
    if kind == "property":
        return f"{CTOR_TARGET}.{callable_name}"
    if callable_name == "__call__":
        return f"{CTOR_TARGET}({arglist(call)})"
    if callable_name in ("__len__", "__str__", "__repr__"):
        return f"{callable_name.strip('_')}({CTOR_TARGET})"
    return f"{CTOR_TARGET}.{callable_name}({arglist(call)})"


def build_steps(contract: dict, ctor_call: dict, calls: list[dict], alias: str = "module_0") -> list[dict]:
    """Scenario steps from the structured form (also used by the shrinker)."""
    class_ref = f"{alias}.{contract['class_name']}"
    steps = [{"kind": "exec", "src": call_src("__init__", "constructor", ctor_call, class_ref),
              "target": CTOR_TARGET, "expected_exc": None}]
    for i, c in enumerate(calls, 1):
        kind = "property" if c["callable"] in contract["properties"] else \
            contract["methods"].get(c["callable"], {}).get("kind", "method")
        steps.append({"kind": "exec", "src": call_src(c["callable"], kind, c, class_ref),
                      "target": f"r{i}", "expected_exc": None})
    return steps


def scenario_from_meta(contract: dict, meta: dict, scenario_id: str) -> dict:
    steps = build_steps(contract, meta["ctor"], meta["calls"])
    return {"scenario_id": scenario_id, "steps": steps, "api_flags": [True] * len(steps),
            "origin": "generated", "meta": meta}


def scenario_strategy(contract: dict, max_calls: int) -> Optional[st.SearchStrategy]:
    ctor = args_strategy(contract["constructor"]["params"])
    if ctor is None:
        return None
    options = []
    for name, rec in sorted(contract["methods"].items()):
        if not rec["generate"]:
            continue
        a = args_strategy(rec["params"])
        if a is not None:
            options.append(a.map(lambda c, n=name: {"callable": n, **c}))
    for prop in contract["properties"]:
        options.append(st.just({"callable": prop, "args": [], "kwargs": {}}))
    if not options:
        return None
    return st.fixed_dictionaries({"ctor": ctor, "calls": st.lists(st.one_of(options), min_size=1, max_size=max_calls)})


def task_seed(label: str, base_seed: int) -> int:
    return int(hashlib.sha256(f"{base_seed}|{label}".encode()).hexdigest()[:8], 16)


def generate_scenarios(contract: dict, n: int, base_seed: int, max_calls: int = 6) -> list[dict]:
    """Up to ``n`` distinct contract-valid scenarios, deterministic for (contract, seed, Hypothesis version)."""
    strat = scenario_strategy(contract, max_calls)
    if strat is None:
        return []
    seen: dict[str, dict] = {}

    @settings(max_examples=max(n * 3, 10), database=None, deadline=None, derandomize=False,
              phases=[Phase.generate], suppress_health_check=list(HealthCheck))
    @seed(task_seed(contract["task"], base_seed))
    @given(strat)
    def collect(meta):
        if len(seen) < n:
            key = json.dumps(meta, sort_keys=True, default=literal_src)
            seen.setdefault(key, meta)

    collect()
    return [scenario_from_meta(contract, m, f"gen_{i}") for i, m in enumerate(seen.values())]
