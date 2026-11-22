"""Write reviewed contracts from the confirmed review decisions (plan rev. 4, Stage 2).

    python scripts/apply_contract_review.py                 # write contracts_v1/reviewed/<task>.json
    python scripts/apply_contract_review.py --check         # usability check of every accepted contract
    python scripts/apply_contract_review.py --revise TASK   # re-write a reviewed task after its entry changed

``contracts_v1/review_decisions.json`` holds one entry per reviewed task: verdict (accept, accept with
edits, reject), the rule applied (doc/extensions/contract_prereview_tier*.md), the evidence note and the
edits. An edit is one of

    {"param": "method.name", "type": "<annotation>", "hints": [...], "constraints": {...}, "generate": bool}
    {"add_param": "method.name", "type": ..., "hints": [...]}      (a parameter the draft lost)
    {"method": "name", "generate": false}
    {"own_class": ["attr", ...]}                                    (observe returned instances through attributes)

``method`` is ``__init__`` for the constructor. Types are Python annotations (``dict[str, int | str]``).
Tasks that already have a reviewed contract are never overwritten. ``--check`` loads each accepted
contract, regenerates its primary pool and requires >= 1 valid generated test (the reference runs; no
mutant or solution does). Local runs are ungated and non-authoritative.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import symtable
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks.contracts import generatable, load_contract, save_contract, spec_from_annotation  # noqa: E402

CONTRACTS = ec.PROTOCOL_DIR / "contracts_v1"
DRAFTS, REVIEWED, DECISIONS = CONTRACTS / "drafts", CONTRACTS / "reviewed", CONTRACTS / "review_decisions.json"
REVIEWER = "Claude (proposal); confirmed by the user"
DATE = "2026-11-18"


def parse_type(text: str) -> dict:
    spec = spec_from_annotation(ast.parse(text, mode="eval").body)
    if spec is None or "unsupported" in json.dumps(spec):
        raise ValueError(f"type {text!r} is not a supported type spec: {spec}")
    return spec


def _target(contract: dict, name: str):
    if name == "__init__":
        return contract["constructor"]
    if name not in contract["methods"]:
        raise KeyError(f"no method {name!r} in contract (has {sorted(contract['methods'])})")
    return contract["methods"][name]


def _param(contract: dict, spec: str) -> dict:
    method, pname = spec.rsplit(".", 1)
    params = _target(contract, method)["params"]
    found = [p for p in params if p["name"] == pname]
    if not found:
        raise KeyError(f"no parameter {spec!r} (has {[p['name'] for p in params]})")
    return found[0]


def _refresh(p: dict) -> None:
    """A generated parameter needs a type or hints that can produce values."""
    if p["generate"] and not generatable(p["type"], p["hints"]):
        raise ValueError(f"parameter {p['name']} is not generatable (type {p['type']}, hints {p['hints']})")
    p["why"] = None if p["generate"] else (p["why"] or "review: not generated")


def apply_edit(contract: dict, e: dict) -> None:
    if "own_class" in e:
        cls = contract["class_name"]
        contract["comparison"]["own_classes"][cls] = {"kind": "accessors", "attributes": list(e["own_class"]), "accessors": []}
        contract["attributes"] = sorted(set(contract["attributes"]) | set(e["own_class"]))
        return
    if "method" in e:
        m = _target(contract, e["method"])
        m["generate"], m["why"] = e["generate"], None if e["generate"] else "review: not generated"
        return
    if "add_param" in e:
        method, pname = e["add_param"].rsplit(".", 1)
        params = _target(contract, method)["params"]
        assert all(p["name"] != pname for p in params), f"{e['add_param']} already exists"
        params.insert(0, {"name": pname, "kind": "positional", "type": parse_type(e["type"]), "type_source": "review",
                          "hints": e.get("hints", []), "constraints": e.get("constraints", {}), "has_default": False,
                          "default": None, "generate": True, "why": None})
        return
    p = _param(contract, e["param"])
    if "type" in e:
        p["type"], p["type_source"] = parse_type(e["type"]), "review"
    if "hints" in e:
        p["hints"] = e["hints"]
    if "constraints" in e:
        p["constraints"] = e["constraints"]
    if "generate" in e:
        p["generate"] = e["generate"]
    elif "type" in e:
        p["generate"] = True
    _refresh(p)


def finish(contract: dict) -> None:
    """Recompute method.generate (unless the review fixed it) and the support block after the edits."""
    for name, m in contract["methods"].items():
        if m["why"] == "review: not generated":
            m["generate"] = False
            continue
        ok = all(p["generate"] or p["has_default"] or p["kind"] in ("varargs", "varkw") for p in m["params"])
        m["generate"] = ok and not m["async"]
        m["why"] = None if ok else "a required parameter cannot be generated"
    ctor_ok = all(p["generate"] or p["has_default"] or p["kind"] in ("varargs", "varkw")
                  for p in contract["constructor"]["params"])
    gen = [n for n, m in contract["methods"].items() if m["generate"]]
    sup = contract["support"]
    reasons = [r for r in sup["reasons"] if not r.startswith(("constructor parameters", "no public method"))]
    if not ctor_ok:
        reasons.append("constructor parameters cannot be generated")
    if not gen and not contract["properties"]:
        reasons.append("no public method or property can be generated")
    sup.update({"generatable_methods": gen, "reasons": reasons, "supported": not reasons})


def build(label: str, d: dict) -> dict:
    contract = load_contract(DRAFTS / f"{label}.json")
    if d["verdict"] == "reject":
        contract["support"]["supported"] = False
        contract["support"]["reasons"].append(f"review: rejected - {d['rule']}: {d['notes']}")
    else:
        for e in d.get("edits", []):
            apply_edit(contract, e)
        finish(contract)
        if not contract["support"]["supported"]:
            raise ValueError(f"{label}: unsupported after the edits: {contract['support']['reasons']}")
    note = f"{d['rule']}: {d['notes']}".strip(": ")
    contract["review"] = {"status": "reviewed", "verdict": d["verdict"], "reviewer": REVIEWER, "date": DATE, "notes": note}
    if d.get("revision"):       # a correction after the user's confirmation: not confirmed until the user says so
        contract["review"].update(revision=d["revision"], date=d["revision"][:10],
                                  reviewer="Claude (revision after the usability check); awaiting user confirmation")
    return contract


def undefined_names(src: str) -> list[str]:
    """Names the reference uses that its module never defines or imports (nor builtins): NameError when the
    line runs. A static check, so a name only used on a logging path is reported too (the reviewer decides)."""
    tree = ast.parse(src)
    defined = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__class__", "__builtins__"}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            defined |= {(a.asname or a.name).split(".")[0] for a in n.names}
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            defined.add(n.id)
    used: set[str] = set()

    def walk(tab):
        used.update(s.get_name() for s in tab.get_symbols() if s.is_referenced() and s.is_global())
        for child in tab.get_children():
            walk(child)
    walk(symtable.symtable(src, "m", "exec"))
    return sorted(used - defined)


def write(decisions: dict, revise: list[str]) -> int:
    if revise:      # re-write named, already reviewed tasks from their (revised) decisions
        unknown = [t for t in revise if t not in decisions or not (REVIEWED / f"{t}.json").exists()]
        if unknown:
            print(f"ERROR: --revise needs an existing reviewed contract and a decision: {unknown}")
            return 1
        decisions = {t: decisions[t] for t in revise}
    else:
        supported_drafts = {p.stem for p in DRAFTS.glob("*.json") if load_contract(p)["support"]["supported"]}
        todo = {t for t in supported_drafts if not (REVIEWED / f"{t}.json").exists()}
        missing, extra = sorted(todo - set(decisions)), sorted(set(decisions) - todo)
        if missing or extra:
            print(f"ERROR: decisions do not cover the unreviewed supported drafts\n  no decision: {missing}\n"
                  f"  not pending: {extra} (to change a reviewed task use --revise)")
            return 1
    errors = []
    for label in sorted(decisions):
        try:
            save_contract(REVIEWED, build(label, decisions[label]))
        except (KeyError, ValueError, AssertionError) as exc:
            errors.append(f"{label}: {exc}")
    for line in errors:
        print("ERROR:", line)
    n = {v: sum(d["verdict"] == v for d in decisions.values()) for v in ("accept", "accept with edits", "reject")}
    print(f"wrote {len(decisions) - len(errors)} reviewed contracts {n}; {len(errors)} errors")
    return 1 if errors else 0


def check(cfg, tasks, gated: bool, only: list[str]) -> int:
    from meta_real_eval.benchmarks.detection import prepare_primary
    from meta_real_eval.oracles.coupling import SPEC
    sp = SPEC["primary_pool"]
    bad, warn = [], []
    for path in sorted(REVIEWED.glob("*.json")):
        label = path.stem
        c = load_contract(path)
        if not c["support"]["supported"] or (only and label not in only):
            continue
        if label in cfg.extensions.development_tasks:
            continue
        ctx = prepare_primary(tasks[label], c, sp["n_generated"], cfg.extensions.seed + sp["seed_offset"], set(), gated,
                              sp["timeout_s"], sp["max_calls"])
        n = len(ctx.get("tests", {}))
        by = {"p": sum(s == "p" for s in ctx.get("tests", {}).values()), "gen": sum(s == "gen" for s in ctx.get("tests", {}).values())}
        undef = undefined_names(tasks[label].reference_code)
        print(f"{label}: {n} valid tests {by} supported={ctx['support']['supported']}"
              + (f" UNDEFINED-NAMES={undef}" if undef else ""), flush=True)
        if undef:
            warn.append(label)
        if not ctx["support"]["supported"] or n < 1:
            bad.append(label)
    print(f"usability check: {len(bad)} contract(s) without a valid test: {bad}")
    print(f"undefined names in the reference (review each): {warn}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=Path("config/tier2_extensions.yaml"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--tasks", nargs="*", default=[], help="with --check: only these labels")
    ap.add_argument("--revise", nargs="+", default=[], metavar="TASK",
                    help="re-write these already reviewed tasks from their revised entries in review_decisions.json")
    ap.add_argument("--ungated", action="store_true")
    args = ap.parse_args()
    if not args.check:
        return write(json.loads(DECISIONS.read_text(encoding="utf-8")), args.revise)
    cfg = ec.load_ext_config(args.config)
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    return check(cfg, tasks, gated, args.tasks)


if __name__ == "__main__":
    raise SystemExit(main())
