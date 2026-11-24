"""Comparison under the R7 output specification (decisions 10.2).

Kept free of heavy imports: emitted hidden tests import it in every graded run.
"""

from __future__ import annotations

from typing import Optional

from ..benchmarks.observe import api_diff

LEVELS = ("value", "type", "none")
DEFAULT_LEVEL = "type"          # a callable the specification does not list (recorded as defaulted)

_FAMILY = {"none": "none", "bool": "bool", "int": "number", "float": "number", "number": "number",
           "complex": "complex", "str": "str", "bytes": "bytes", "seq": "seq", "set": "set", "map": "map",
           "type": "type", "exc_value": "exc_value"}


def type_family(tok) -> Optional[list]:
    """The kind of value an API token describes (None = unknown, e.g. a digest of a large value)."""
    if not tok:
        return None
    if tok[0] in _FAMILY:
        return [_FAMILY[tok[0]]]
    if tok[0] in ("obj", "opaque", "exact", "enum"):
        return ["object", tok[1]]
    return None


def restrict(tok, level: str):
    """The expected token under a specification level (exceptions are always kept)."""
    if tok is None or tok[0] == "exc" or level == "value":
        return tok
    if level == "type":
        fam = type_family(tok)
        return ["@type", fam] if fam is not None else ["@any"]
    return ["@any"]


def spec_diff(exp, cand, rules=None, where: str = "") -> Optional[str]:
    """Difference between a (possibly restricted) expected token and a candidate token; None if they agree."""
    if exp and exp[0] in ("@any", "@type"):
        if cand is None or cand[0] == "exc":
            return f"{where}: expected a normal return, got {cand!r}"
        if exp[0] == "@type" and type_family(cand) != exp[1]:
            return f"{where}: expected type {exp[1]}, got {type_family(cand)}"
        return None
    return api_diff(exp, cand, rules, where=where)
