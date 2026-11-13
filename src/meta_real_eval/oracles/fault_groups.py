"""Fault groups and the frozen discovery / held-out split (extensions plan rev. 9, D4).

A **fault group** is every mutant record of a task with the same
docstring-insensitive normalised program (``ast.unparse`` after stripping
docstrings). Identical faults produced by several models, attempts, operators
or generators are one fault: groups are the unit of splitting, detection rates
and yields. Every member record keeps its provenance.

The **split is frozen before any Stage 2 outcome exists**. It depends only on the
programs: within each (task, group source) stratum, groups are ordered by a
keyed hash and assigned alternately to discovery and held-out (the starting side is a keyed coin per stratum),
so the split is balanced per stratum and reproducible. Confirmation status
(D3) is attached later and never moves a group.

**Site mutants generated later (Stage 3)** are placed by
:func:`place_site_mutant` against the frozen split, never by re-splitting:

* identical to a discovery group  -> ``discovery_overlap``: kept with that
  group's provenance, excluded from every held-out evaluation;
* identical to a held-out group   -> joins that held-out group;
* new program                     -> a new site-only group in the held-out
  site population.
"""

from __future__ import annotations

import ast
import hashlib
import json
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

SOURCES = ("operator", "llm_whole", "llm_site")
DISCOVERY, HELD_OUT = "discovery", "held_out"
FORMAT = 1


def _parse(code: str) -> Optional[ast.Module]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            return ast.parse(code)
        except (SyntaxError, ValueError):
            return None


def normalise_program(code: str) -> str:
    """Docstring-insensitive normal form (the Stage 1 audit's ``normalise_no_doc``)."""
    tree = _parse(code)
    if tree is None:
        return code.strip()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def group_id(task: str, normalised: str) -> str:
    return hashlib.sha256(f"{task}\n{normalised}".encode("utf-8")).hexdigest()[:16]


def build_groups(records: Iterable[dict]) -> dict[str, dict[str, dict]]:
    """``records``: dicts with ``task``, ``record_id``, ``source`` (one of SOURCES), ``code`` and any
    provenance fields. Returns {task: {group_id: {"source", "members", "normalised_sha256"}}}; the
    code itself is not stored (members carry ``code_sha256``)."""
    groups: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in records:
        if r["source"] not in SOURCES:
            raise ValueError(f"unknown source {r['source']!r}")
        norm = normalise_program(r["code"])
        gid = group_id(r["task"], norm)
        g = groups[r["task"]].setdefault(gid, {"sources": set(), "members": [],
                                               "normalised_sha256": hashlib.sha256(norm.encode()).hexdigest()})
        g["sources"].add(r["source"])
        member = {k: v for k, v in r.items() if k not in ("code", "task")}
        member["code_sha256"] = hashlib.sha256(r["code"].encode("utf-8")).hexdigest()
        g["members"].append(member)
    out: dict[str, dict[str, dict]] = {}
    for task, gs in groups.items():
        out[task] = {}
        for gid, g in sorted(gs.items()):
            src = sorted(g["sources"])
            out[task][gid] = {"source": src[0] if len(src) == 1 else "mixed", "sources": src,
                              "normalised_sha256": g["normalised_sha256"],
                              "members": sorted(g["members"], key=lambda m: m["record_id"])}
    return out


def _rank(seed: int, task: str, gid: str) -> str:
    return hashlib.sha256(f"{seed}|split|{task}|{gid}".encode()).hexdigest()


def freeze_split(groups: dict[str, dict[str, dict]], seed: int) -> dict[str, dict[str, str]]:
    """{task: {group_id: discovery|held_out}}, balanced within each (task, source) stratum."""
    split: dict[str, dict[str, str]] = {}
    for task, gs in sorted(groups.items()):
        split[task] = {}
        strata: dict[str, list[str]] = defaultdict(list)
        for gid, g in gs.items():
            strata[g["source"]].append(gid)
        for source in sorted(strata):
            # which side the stratum starts on is a keyed coin, so odd-sized strata (often one
            # group) do not all add their extra group to the same side
            start = int(hashlib.sha256(f"{seed}|start|{task}|{source}".encode()).hexdigest(), 16) % 2
            for i, gid in enumerate(sorted(strata[source], key=lambda x: _rank(seed, task, x))):
                split[task][gid] = DISCOVERY if (i + start) % 2 == 0 else HELD_OUT
    return split


def place_site_mutant(task: str, code: str, groups: dict[str, dict[str, dict]],
                      split: dict[str, dict[str, str]]) -> dict:
    """Where a later (Stage 3) site mutant goes, against the frozen split."""
    gid = group_id(task, normalise_program(code))
    side = split.get(task, {}).get(gid)
    if side == DISCOVERY:
        return {"group_id": gid, "placement": "discovery_overlap", "held_out_eligible": False}
    if side == HELD_OUT:
        return {"group_id": gid, "placement": "joins_held_out_group", "held_out_eligible": True}
    return {"group_id": gid, "placement": "new_site_group", "held_out_eligible": True}


def split_document(groups: dict, split: dict, seed: int, provenance: dict) -> dict:
    """The frozen artifact: groups (with member provenance) and their side, plus counts."""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    tasks = {}
    for task, gs in sorted(groups.items()):
        tasks[task] = {gid: {**g, "side": split[task][gid]} for gid, g in gs.items()}
        for gid, g in gs.items():
            counts[g["source"]][split[task][gid]] += 1
    return {"format": FORMAT, "seed": seed, "rule": "balanced alternation within (task, group source) "
            "ordered by sha256(seed|split|task|group_id); starting side = sha256(seed|start|task|source) mod 2", "provenance": provenance,
            "counts": {s: dict(c) for s, c in sorted(counts.items())}, "tasks": tasks}


def load_split(path: Path) -> tuple[dict, dict]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    groups = {t: {gid: {k: v for k, v in g.items() if k != "side"} for gid, g in gs.items()}
              for t, gs in doc["tasks"].items()}
    split = {t: {gid: g["side"] for gid, g in gs.items()} for t, gs in doc["tasks"].items()}
    return groups, split
