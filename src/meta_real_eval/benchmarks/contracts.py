"""Task contracts for the extensions (plan rev. 9, D1-D2).

A contract states, per RealClassEval task, what the specification lets a test
exercise and observe:

* the **public interface**: constructor, public methods, properties, the few
  documented dunders (``__call__``, ``__len__``, ``__str__``, ``__repr__``)
  and documented attributes;
* the **input domain** per parameter: a type spec (from the annotation, else
  the docstring, else literals of P tests the reference passes, else the
  default value), value hints, documented constraints, documented exceptions;
* the **comparison rules** for API observations (``observe.api_diff``):
  float tolerance, numeric equality, container strictness, and how a returned
  instance of the task's own class is compared (``opaque`` by default,
  ``accessors`` = projection onto documented properties/attributes).

Contracts are **drafted** automatically (``draft_contract``) and must be
**reviewed** before they count for primary results (``review.status``).
Support is decided here, before any search, from the draft alone: a task is
outside the supported subset when its parameters cannot be typed, it imports a
non-stdlib or side-effect module, or no P scenario exists. Unsupported tasks are
counted with their reasons, never dropped silently.

Literals from strict-xfail P tests are ignored: those tests are expected to
fail on the reference and often pass inputs outside the documented domain.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import warnings
from pathlib import Path
from typing import Any, Optional

FORMAT = 1
DRAFTER_VERSION = "contracts-v1"

GENERATED_DUNDERS = ("__call__", "__len__", "__str__", "__repr__")
SAFE_BUILTINS = frozenset({"len", "str", "repr", "int", "float", "bool", "list", "tuple", "dict", "set",
                           "frozenset", "sorted", "min", "max", "sum", "abs", "round", "isinstance", "bytes"})
# Imports that make generated calls unsafe or nondeterministic in a scenario
# (network, processes, threads, signals, file-tree removal, raw memory).
SIDE_EFFECT_MODULES = frozenset({"socket", "urllib", "http", "ftplib", "smtplib", "ssl", "subprocess",
                                 "multiprocessing", "threading", "asyncio", "webbrowser", "ctypes",
                                 "signal", "shutil", "concurrent", "selectors", "telnetlib"})
DEFAULT_COMPARISON = {"float_rel_tol": 1e-9, "float_abs_tol": 1e-12, "numeric": "python_eq",
                      "strict_container_types": False, "ordered_mappings": False}
UNSUPPORTED = "unsupported"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse(src: str) -> Optional[ast.Module]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            return ast.parse(src)
        except (SyntaxError, ValueError):
            return None


# ---------------------------------------------------------------------------
# Type specs
# ---------------------------------------------------------------------------

_BASE = {
    "int": {"t": "int"}, "integer": {"t": "int"}, "long": {"t": "int"},
    "float": {"t": "float"}, "double": {"t": "float"}, "real": {"t": "float"},
    "number": {"t": "union", "options": [{"t": "int"}, {"t": "float"}]},
    "numeric": {"t": "union", "options": [{"t": "int"}, {"t": "float"}]},
    "str": {"t": "str"}, "string": {"t": "str"}, "text": {"t": "str"}, "unicode": {"t": "str"},
    "bool": {"t": "bool"}, "boolean": {"t": "bool"},
    "bytes": {"t": "bytes"}, "bytearray": {"t": "bytes"},
    "none": {"t": "none"}, "nonetype": {"t": "none"},
    "list": {"t": "list", "items": {"t": "any"}}, "sequence": {"t": "list", "items": {"t": "any"}},
    "iterable": {"t": "list", "items": {"t": "any"}},
    "tuple": {"t": "tuple", "items": {"t": "any"}, "variadic": True},
    "dict": {"t": "dict", "keys": {"t": "any"}, "values": {"t": "any"}},
    "dictionary": {"t": "dict", "keys": {"t": "any"}, "values": {"t": "any"}},
    "mapping": {"t": "dict", "keys": {"t": "any"}, "values": {"t": "any"}},
    "set": {"t": "set", "items": {"t": "any"}}, "frozenset": {"t": "set", "items": {"t": "any"}},
    "any": {"t": "any"}, "object": {"t": "any"},
}
_CONTAINERS = {"list": "list", "sequence": "list", "iterable": "list", "set": "set", "frozenset": "set",
               "tuple": "tuple", "dict": "dict", "mapping": "dict", "optional": "optional", "union": "union"}


def union(specs: list[dict]) -> dict:
    flat: list[dict] = []
    for s in specs:
        for o in (s["options"] if s.get("t") == "union" else [s]):
            if o not in flat:
                flat.append(o)
    if any(o["t"] == UNSUPPORTED for o in flat):
        return next(o for o in flat if o["t"] == UNSUPPORTED)
    return flat[0] if len(flat) == 1 else {"t": "union", "options": flat}


def spec_from_annotation(node: Optional[ast.AST], class_name: str = "") -> Optional[dict]:
    """A type spec from an annotation node; None if absent, ``unsupported`` if not builtin."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):   # string annotation
        inner = _parse(node.value)
        if inner and isinstance(inner.body[0], ast.Expr):
            return spec_from_annotation(inner.body[0].value, class_name)
        return {"t": UNSUPPORTED, "why": f"annotation {node.value!r}"}
    if isinstance(node, ast.Constant) and node.value is None:
        return {"t": "none"}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return union([spec_from_annotation(node.left, class_name), spec_from_annotation(node.right, class_name)])
    name = ast.unparse(node.value if isinstance(node, ast.Subscript) else node).split(".")[-1]
    if name == class_name:
        return {"t": "self"}
    if isinstance(node, ast.Subscript):
        args = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        sub = [spec_from_annotation(a, class_name) or {"t": "any"} for a in args]
        low = name.lower()
        if low == "optional":
            return union([sub[0], {"t": "none"}])
        if low == "union":
            return union(sub)
        if low in ("list", "sequence", "iterable"):
            return {"t": "list", "items": sub[0]}
        if low in ("set", "frozenset"):
            return {"t": "set", "items": sub[0]}
        if low == "tuple":
            if len(args) == 2 and isinstance(args[1], ast.Constant) and args[1].value is Ellipsis:
                return {"t": "tuple", "items": sub[0], "variadic": True}
            return {"t": "tuple", "items": sub}
        if low in ("dict", "mapping"):
            return {"t": "dict", "keys": sub[0], "values": sub[1] if len(sub) > 1 else {"t": "any"}}
        return {"t": UNSUPPORTED, "why": f"annotation {ast.unparse(node)}"}
    if name.lower() in _BASE:
        return dict(_BASE[name.lower()])
    return {"t": UNSUPPORTED, "why": f"annotation {ast.unparse(node)}"}


def spec_from_typestr(text: str) -> Optional[dict]:
    """A type spec from a docstring type such as 'int', 'list of str', 'str or None', 'bool, optional'."""
    if not text:
        return None
    s = text.strip().strip("`").rstrip(".").lower()
    s = re.sub(r",?\s*optional$", "", s).strip()
    s = re.sub(r"\s*\(default[^)]*\)$", "", s).strip()
    if not s:
        return None
    parts = [p.strip() for p in re.split(r"\s+or\s+|\s*\|\s*", s) if p.strip()]
    if len(parts) > 1:
        return union([spec_from_typestr(p) or {"t": UNSUPPORTED, "why": p} for p in parts])
    m = re.match(r"^(list|sequence|iterable|set|tuple)\s+of\s+(.+)$", s)
    if m:
        inner = spec_from_typestr(m.group(2).rstrip("s")) or spec_from_typestr(m.group(2)) \
            or {"t": UNSUPPORTED, "why": m.group(2)}
        kind = _CONTAINERS[m.group(1)]
        return {"t": kind, "items": inner, **({"variadic": True} if kind == "tuple" else {})}
    node = _parse(text.strip().strip("`"))
    if node and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, (ast.Subscript, ast.BinOp)):
        return spec_from_annotation(node.body[0].value)
    if s in _BASE:
        return dict(_BASE[s])
    return {"t": UNSUPPORTED, "why": f"docstring type {text.strip()!r}"}


def spec_from_value(v: Any) -> dict:
    if v is None:
        return {"t": "none"}
    if isinstance(v, bool):
        return {"t": "bool"}
    if isinstance(v, int):
        return {"t": "int"}
    if isinstance(v, float):
        return {"t": "float"}
    if isinstance(v, str):
        return {"t": "str"}
    if isinstance(v, bytes):
        return {"t": "bytes"}
    if isinstance(v, (list, tuple, set, frozenset)):
        items = union([spec_from_value(x) for x in v]) if v else {"t": "any"}
        kind = "list" if isinstance(v, list) else "set" if isinstance(v, (set, frozenset)) else "tuple"
        return {"t": kind, "items": items, **({"variadic": True} if kind == "tuple" else {})}
    if isinstance(v, dict):
        keys = union([spec_from_value(k) for k in v]) if v else {"t": "any"}
        vals = union([spec_from_value(x) for x in v.values()]) if v else {"t": "any"}
        return {"t": "dict", "keys": keys, "values": vals}
    return {"t": UNSUPPORTED, "why": f"value of type {type(v).__name__}"}


def generatable(spec: Optional[dict], hints: list) -> bool:
    """Can values for this parameter be generated inside the contract?"""
    if spec is None:
        return bool(hints)
    t = spec["t"]
    if t == UNSUPPORTED:
        return False
    if t == "any":
        return bool(hints)
    if t == "union":
        return all(generatable(o, []) or o["t"] == "any" for o in spec["options"]) or bool(hints)
    return True


def value_ok(v: Any, spec: Optional[dict], constraints: Optional[dict] = None) -> bool:
    """Does ``v`` satisfy the type spec and the documented constraints (D2 predicates)?"""
    if spec is not None and not _type_ok(v, spec):
        return False
    c = constraints or {}
    try:
        if "choices" in c and v not in c["choices"]:
            return False
        if "min" in c and v < c["min"]:
            return False
        if "max" in c and v > c["max"]:
            return False
        if c.get("non_empty") and len(v) == 0:
            return False
        if "max_len" in c and len(v) > c["max_len"]:
            return False
    except TypeError:
        return False
    return True


def _type_ok(v: Any, spec: dict) -> bool:
    t = spec["t"]
    if t in ("any", "self"):
        return True
    if t == "union":
        return any(_type_ok(v, o) for o in spec["options"])
    if t == "none":
        return v is None
    if t == "bool":
        return isinstance(v, bool)
    if t == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "float":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "str":
        return isinstance(v, str)
    if t == "bytes":
        return isinstance(v, (bytes, bytearray))
    if t == "list":
        return isinstance(v, list) and all(_type_ok(x, spec["items"]) for x in v)
    if t == "set":
        return isinstance(v, (set, frozenset)) and all(_type_ok(x, spec["items"]) for x in v)
    if t == "tuple":
        if not isinstance(v, tuple):
            return False
        if spec.get("variadic"):
            return all(_type_ok(x, spec["items"]) for x in v)
        return len(v) == len(spec["items"]) and all(_type_ok(x, s) for x, s in zip(v, spec["items"]))
    if t == "dict":
        return isinstance(v, dict) and all(_type_ok(k, spec["keys"]) and _type_ok(x, spec["values"])
                                           for k, x in v.items())
    return False


# ---------------------------------------------------------------------------
# Docstrings
# ---------------------------------------------------------------------------

_SECTION = re.compile(r"^\s*(Args|Arguments|Parameters|Params|Keyword Args|Raises|Attributes|Returns|Yields|"
                      r"Examples?|Notes?|See Also)\s*:?\s*$")


def parse_docstring(doc: str) -> dict:
    """Parameter types, raised exceptions and documented attributes (Google, reST, NumPy)."""
    out: dict = {"params": {}, "raises": [], "attributes": {}}
    if not doc:
        return out
    for m in re.finditer(r":param\s+(?:([^:]+?)\s+)?(\*{0,2}\w+)\s*:", doc):
        out["params"].setdefault(m.group(2).lstrip("*"), (m.group(1) or "").strip())
    for m in re.finditer(r":type\s+(\*{0,2}\w+)\s*:\s*([^\n]+)", doc):
        out["params"][m.group(1).lstrip("*")] = m.group(2).strip()
    for m in re.finditer(r":raises?\s+([\w.]+)\s*:", doc):
        out["raises"].append(m.group(1).split(".")[-1])
    lines = doc.splitlines()
    section, numpy_style, entry_indent = None, False, None
    for i, line in enumerate(lines):
        m = _SECTION.match(line)
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        dashed = bool(re.match(r"^\s*-{3,}\s*$", nxt))
        if m and (line.rstrip().endswith(":") or dashed):
            section, numpy_style, entry_indent = m.group(1).lower(), dashed, None
            continue
        if re.match(r"^\s*-{3,}\s*$", line) or section is None or not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if entry_indent is None:
            entry_indent = indent
        if indent > entry_indent:          # continuation of an entry's description
            continue
        if section in ("args", "arguments", "parameters", "params", "keyword args", "attributes"):
            target = "attributes" if section == "attributes" else "params"
            if numpy_style:
                mm = re.match(r"^\s*(\*{0,2}\w+)\s*(?::\s*(.*))?$", line)
                name, typ = (mm.group(1), mm.group(2) or "") if mm else (None, "")
            else:
                mm = re.match(r"^\s*(\*{0,2}\w+)\s*(?:\(([^)]*)\))?\s*:", line)
                name, typ = (mm.group(1), mm.group(2) or "") if mm else (None, "")
            if name:
                name = name.lstrip("*")
                if not out[target].get(name):
                    out[target][name] = typ.strip()
        elif section == "raises":
            mm = re.match(r"^\s*([A-Za-z_]\w*(?:\.\w+)*)\s*(?::|$)", line)
            if mm:
                out["raises"].append(mm.group(1).split(".")[-1])
    out["raises"] = sorted(set(out["raises"]))
    return out


# ---------------------------------------------------------------------------
# P-test literals (only tests the reference passes: strict-xfail tests ignored)
# ---------------------------------------------------------------------------

def p_literals(test_code: str, module_name: str, class_name: str) -> dict:
    """{callable: {param position (int) or keyword (str): [literal values]}} from non-xfail tests."""
    tree = _parse(test_code)
    out: dict = {}
    if tree is None:
        return out
    alias = module_name
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == module_name:
                    alias = a.asname or a.name
    for fn in tree.body:
        if not (isinstance(fn, ast.FunctionDef) and fn.name.startswith("test")):
            continue
        if any("xfail" in ast.unparse(d) for d in fn.decorator_list):
            continue
        consts: dict[str, Any] = {}
        instances: set[str] = set()
        for stmt in ast.walk(fn):
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                name = stmt.targets[0].id
                val = _literal(stmt.value, consts)
                if val is not _NOLIT:
                    consts[name] = val
                    continue
                call = stmt.value
                if isinstance(call, ast.Call) and ast.unparse(call.func) == f"{alias}.{class_name}":
                    instances.add(name)
        for call in ast.walk(fn):
            if not isinstance(call, ast.Call):
                continue
            func = ast.unparse(call.func)
            target = None
            if func == f"{alias}.{class_name}":
                target = "__init__"
            elif isinstance(call.func, ast.Attribute):
                base = ast.unparse(call.func.value)
                if base in instances or base == f"{alias}.{class_name}":
                    target = call.func.attr
            elif isinstance(call.func, ast.Name) and call.func.id in instances:
                target = "__call__"
            if target is None:
                continue
            slots = out.setdefault(target, {})
            pos = 0
            for arg in call.args:
                if isinstance(arg, ast.Starred):
                    val = _literal(arg.value, consts)
                    if isinstance(val, (list, tuple, str)):
                        slots.setdefault("*", []).extend(list(val))
                    pos = None
                    continue
                if pos is None:
                    continue
                val = _literal(arg, consts)
                if val is not _NOLIT:
                    slots.setdefault(pos, []).append(val)
                pos += 1
            for kw in call.keywords:
                if kw.arg is None:
                    continue
                val = _literal(kw.value, consts)
                if val is not _NOLIT:
                    slots.setdefault(kw.arg, []).append(val)
    return out


_NOLIT = object()


def _literal(node: Optional[ast.AST], consts: dict):
    """A literal value, with names bound earlier to literals substituted (Pynguin builds
    ``list_0 = [int_0, int_0]`` from ``int_0 = 594``); _NOLIT when not a literal."""
    if node is None:
        return _NOLIT
    if isinstance(node, ast.Name):
        return consts.get(node.id, _NOLIT)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _literal(node.operand, consts)
        return v if v is _NOLIT or isinstance(node.op, ast.UAdd) else (-v if isinstance(v, (int, float)) else _NOLIT)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        vals = [_literal(e, consts) for e in node.elts]
        if any(v is _NOLIT for v in vals):
            return _NOLIT
        try:
            return list(vals) if isinstance(node, ast.List) else tuple(vals) if isinstance(node, ast.Tuple) else set(vals)
        except TypeError:
            return _NOLIT
    if isinstance(node, ast.Dict):
        if any(k is None for k in node.keys):
            return _NOLIT
        ks = [_literal(k, consts) for k in node.keys]
        vs = [_literal(v, consts) for v in node.values]
        if any(x is _NOLIT for x in ks + vs):
            return _NOLIT
        try:
            return dict(zip(ks, vs))
        except TypeError:
            return _NOLIT
    return _NOLIT


def _json_safe(values: list) -> list:
    out = []
    for v in values:
        if isinstance(v, (set, frozenset, bytes, tuple)) or (isinstance(v, float) and v != v):
            continue
        try:
            json.dumps(v)
        except (TypeError, ValueError):
            continue
        if v not in out:
            out.append(v)
    return out[:20]


# ---------------------------------------------------------------------------
# Drafting
# ---------------------------------------------------------------------------

def _top_imports(src: str) -> set[str]:
    tree = _parse(src)
    mods: set[str] = set()
    if tree is None:
        return mods
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            mods.add(node.module.split(".")[0])
    return mods


def _param_records(fn: ast.AST, doc: dict, lits: dict, class_name: str, kind_of: str) -> list[dict]:
    a = fn.args
    positional = list(a.posonlyargs) + list(a.args)
    skip_first = kind_of in ("method", "classmethod", "constructor", "property", "dunder")
    if skip_first and positional:
        positional = positional[1:]
    defaults = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
    recs = []

    def build(name, ann, default_node, kind, lit_key):
        hints = list(lits.get(lit_key, [])) + (list(lits.get(name, [])) if lit_key != name else [])
        has_default = default_node is not None
        default = _literal(default_node, {}) if has_default else _NOLIT
        if default is not _NOLIT:
            hints.append(default)
        spec, source = spec_from_annotation(ann, class_name), "annotation"
        if spec is None or spec["t"] == UNSUPPORTED:
            ds = spec_from_typestr(doc["params"].get(name, ""))
            if ds is not None and (spec is None or ds["t"] != UNSUPPORTED):
                spec, source = ds, "docstring"
        if spec is None or spec["t"] == UNSUPPORTED:
            vals = [h for h in hints if h is not None or has_default]
            if vals:
                vs = union([spec_from_value(v) for v in vals])
                if vs["t"] != UNSUPPORTED:
                    spec, source = vs, ("p_literals" if lits.get(lit_key) or lits.get(name) else "default")
        if spec is None:
            spec, source = {"t": "any"}, "none"
        hints = _json_safe(hints)
        if kind == "varargs":
            hints = _json_safe(list(lits.get("*", [])))
        gen = generatable(spec, hints) if kind != "varkw" else False
        recs.append({"name": name, "kind": kind, "type": spec, "type_source": source, "hints": hints,
                     "has_default": has_default, "default": None if default is _NOLIT else _json_safe([default])[:1],
                     "constraints": {}, "generate": gen or (has_default and kind != "varargs"),
                     "why": None if gen else _why(spec, hints, kind)})

    for i, (p, d) in enumerate(zip(positional, defaults)):
        build(p.arg, p.annotation, d, "positional", i)
    if a.vararg:
        build(a.vararg.arg, a.vararg.annotation, None, "varargs", "*")
    for p, d in zip(a.kwonlyargs, a.kw_defaults):
        build(p.arg, p.annotation, d, "keyword_only", p.arg)
    if a.kwarg:
        build(a.kwarg.arg, a.kwarg.annotation, None, "varkw", "**")
    return recs


def _why(spec: dict, hints: list, kind: str) -> str:
    if kind == "varkw":
        return "**kwargs are not generated (keyword names are not specified)"
    if spec["t"] == UNSUPPORTED:
        return spec.get("why", "unsupported type")
    if spec["t"] == "any":
        return "no type and no valid literal hints"
    return "not generatable"


def draft_contract(task, dependency_scan: Optional[dict] = None) -> dict:
    """Draft a contract for a RealClassEval ``Task`` (status ``draft``)."""
    skeleton = task.prompt
    class_name = task.target
    tree = _parse(skeleton)
    cls = next((n for n in (tree.body if tree else []) if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    lits = p_literals(task.test_code, task.module_name, class_name)
    contract: dict = {
        "format": FORMAT, "task": task.label, "task_id": task.task_id, "class_name": class_name,
        "module_name": task.module_name,
        "sources": {"skeleton_sha256": _sha(skeleton), "reference_sha256": _sha(task.reference_code),
                    "tests_sha256": _sha(task.test_code)},
        "constructor": {"params": [], "raises_documented": [], "documented": False},
        "methods": {}, "properties": [], "attributes": [],
        "comparison": {**DEFAULT_COMPARISON, "own_classes": {class_name: {"kind": "opaque", "attributes": [], "accessors": []}}},
        "support": {}, "review": {"status": "draft", "reviewer": None, "date": None, "notes": ""},
        "drafter": DRAFTER_VERSION,
    }
    reasons: list[str] = []
    if cls is None:
        reasons.append("skeleton has no target class")
    else:
        cdoc = parse_docstring(ast.get_docstring(cls) or "")
        if any(ast.unparse(d).split("(")[0].split(".")[-1] == "dataclass" for d in cls.decorator_list):
            fields = [n for n in cls.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]
            if not fields:
                reasons.append("dataclass whose fields are not in the skeleton (constructor unspecified)")
            else:   # synthesize the generated __init__ from the declared fields
                fake = ast.parse("def __init__(self, " + ", ".join(
                    f"{f.target.id}: {ast.unparse(f.annotation)}" + (f" = {ast.unparse(f.value)}" if f.value else "")
                    for f in fields) + "): pass").body[0]
                contract["constructor"] = {"params": _param_records(fake, cdoc, lits.get("__init__", {}), class_name,
                                                                    "constructor"),
                                           "raises_documented": [], "documented": True, "dataclass": True}
        contract["attributes"] = sorted(n for n in cdoc["attributes"] if not n.startswith("_"))
        for fn in cls.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decos = {ast.unparse(d).split(".")[-1] for d in fn.decorator_list}
            doc = parse_docstring(ast.get_docstring(fn) or "")
            if fn.name == "__init__":
                contract["constructor"] = {"params": _param_records(fn, doc, lits.get("__init__", {}), class_name, "constructor"),
                                           "raises_documented": doc["raises"], "documented": True}
                continue
            if "property" in decos:
                if not fn.name.startswith("_"):
                    contract["properties"].append(fn.name)
                continue
            if fn.name.startswith("_") and fn.name not in GENERATED_DUNDERS:
                continue
            if any(d.endswith("setter") or d.endswith("deleter") for d in decos):
                continue
            kind = "staticmethod" if "staticmethod" in decos else "classmethod" if "classmethod" in decos else \
                "dunder" if fn.name.startswith("__") else "method"
            params = _param_records(fn, doc, lits.get(fn.name, {}), class_name, kind)
            required_ok = all(p["generate"] or p["has_default"] or p["kind"] in ("varargs", "varkw") for p in params)
            contract["methods"][fn.name] = {
                "kind": kind, "params": params, "raises_documented": doc["raises"],
                "async": isinstance(fn, ast.AsyncFunctionDef),
                "generate": required_ok and not isinstance(fn, ast.AsyncFunctionDef),
                "why": None if required_ok else "a required parameter cannot be generated",
            }
        props = contract["properties"]
        if props:   # documented properties: the drafted projection for returned instances (review!)
            contract["comparison"]["own_classes"][class_name] = {"kind": "accessors", "attributes": props, "accessors": []}
    ctor = contract["constructor"]["params"]
    ctor_ok = all(p["generate"] or p["has_default"] or p["kind"] in ("varargs", "varkw") for p in ctor)
    gen_methods = [m for m, r in contract["methods"].items() if r["generate"]]
    deps = (dependency_scan or {}).get("tasks", {}).get(task.task_id, {})
    stdlib_only = deps.get("stdlib_only")
    side = sorted(_top_imports(task.reference_code) & SIDE_EFFECT_MODULES)
    from .scenarios import UnsupportedScenario, extract_scenarios
    try:
        _, scen = extract_scenarios(task.test_code, task.module_name)
        n_p = len(scen)
    except (UnsupportedScenario, SyntaxError):
        n_p = 0
    if stdlib_only is False:
        reasons.append("imports non-stdlib modules")
    elif stdlib_only is None:
        reasons.append("dependency scan has no entry")
    if side:
        reasons.append(f"imports side-effect modules {side}")
    if not ctor_ok:
        reasons.append("constructor parameters cannot be generated")
    if not gen_methods and not contract["properties"]:
        reasons.append("no public method or property can be generated")
    if n_p == 0:
        reasons.append("no P scenario")
    contract["support"] = {"supported": not reasons, "reasons": reasons, "stdlib_only": stdlib_only,
                           "side_effect_imports": side, "n_p_scenarios": n_p,
                           "generatable_methods": gen_methods, "properties": contract["properties"]}
    return contract


# ---------------------------------------------------------------------------
# Using a contract
# ---------------------------------------------------------------------------

def api_rules(contract: dict) -> dict:
    """The comparison rules handed to the scenario runner and ``observe.api_diff``."""
    c = contract["comparison"]
    return {k: c[k] for k in ("float_rel_tol", "float_abs_tol", "numeric", "strict_container_types",
                              "ordered_mappings", "own_classes")}


def api_names(contract: dict) -> set[str]:
    return set(contract["methods"]) | set(contract["properties"]) | set(contract["attributes"])


def documented_raises(contract: dict, callable_name: str) -> set[str]:
    if callable_name == "__init__":
        return set(contract["constructor"]["raises_documented"])
    rec = contract["methods"].get(callable_name)
    return set(rec["raises_documented"]) if rec else set()


def expr_is_api(src: str, names: set[str], alias: str, bound: set[str]) -> bool:
    """Does an expression touch only the public contract? Allowed: literals, the module alias and
    its public names, variables bound by API-visible steps, contract names as attributes, calls
    to those and to a few pure builtins. Type introspection, private or undocumented attributes
    and any other construct make the step non-API."""
    tree = _parse(src)
    if tree is None or not tree.body or not isinstance(tree.body[0], ast.Expr):
        return False

    def ok(node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.Name):
            return node.id == alias or node.id in bound or node.id in SAFE_BUILTINS
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == alias:
                return not node.attr.startswith("_")
            if node.attr.startswith("_") and node.attr not in GENERATED_DUNDERS:
                return False
            return node.attr in names and ok(node.value)
        if isinstance(node, ast.Call):
            return ok(node.func) and all(ok(a.value if isinstance(a, ast.Starred) else a) for a in node.args) \
                and all(ok(k.value) for k in node.keywords)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return all(ok(e) for e in node.elts)
        if isinstance(node, ast.Dict):
            return all(k is None or ok(k) for k in node.keys) and all(ok(v) for v in node.values)
        if isinstance(node, (ast.UnaryOp,)):
            return ok(node.operand)
        if isinstance(node, ast.BinOp):
            return ok(node.left) and ok(node.right)
        if isinstance(node, ast.Compare):
            return ok(node.left) and all(ok(c) for c in node.comparators)
        if isinstance(node, ast.Subscript):
            return ok(node.value) and ok(node.slice)
        return False
    return ok(tree.body[0].value)


def api_flags(steps: list[dict], contract: dict, alias: str) -> list[bool]:
    """Per scenario step: is it an API-visible observation under the contract?"""
    names = api_names(contract) | set(GENERATED_DUNDERS)
    bound: set[str] = set()
    flags = []
    for st in steps:
        f = expr_is_api(st["src"], names, alias, bound)
        flags.append(f)
        if f and st.get("target"):
            bound.add(st["target"])
    return flags


def step_callable(src: str, alias: str, class_name: str) -> Optional[str]:
    """Which contract callable a step invokes ('__init__', a method name, '__call__'), if any."""
    tree = _parse(src)
    if tree is None or not tree.body or not isinstance(tree.body[0], ast.Expr):
        return None
    node = tree.body[0].value
    if not isinstance(node, ast.Call):
        return None
    if ast.unparse(node.func) == f"{alias}.{class_name}":
        return "__init__"
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return "__call__" if node.func.id not in SAFE_BUILTINS else None
    return None


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def contract_sha(contract: dict) -> str:
    return _sha(json.dumps(contract, sort_keys=True))


def save_contract(directory: Path, contract: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{contract['task']}.json"
    path.write_text(json.dumps(contract, indent=1, sort_keys=True), encoding="utf-8")
    return path


def load_contract(path: Path) -> dict:
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    if c.get("format") != FORMAT:
        raise ValueError(f"{path}: contract format {c.get('format')} != {FORMAT}")
    return c
