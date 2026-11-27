"""H v1.1: the post-hoc corrected hidden suite, a labelled sensitivity (decisions 10.8; H v1 stays primary).

    # 1. Fix B population: every `type` entry an H v1 test asserts (step outputs and object fields), with the
    #    mechanical annotation / protocol check; the rest goes on a blind sheet (no outcome, no completion)
    python scripts/h_v11.py types --config config/tier2_extensions.yaml --hidden results_tier2_ext/hidden_v1 \
        --seen results_tier2_ext/stage5/review/items.csv --out results_tier2_ext/h_v11
    # 2. after the verdicts (keep / none) in fixb_items.csv: the new output specification
    python scripts/h_v11.py spec --out results_tier2_ext/h_v11
    # 3. the same H v1 tests with re-derived expectations (Fix A + output_spec_v1_1), subset check, admission, control
    python scripts/h_v11.py build --config config/tier2_extensions.yaml --hidden results_tier2_ext/hidden_v1 \
        --out results_tier2_ext/a2/full_v2_1 --workers 8
    # 4. freeze: python scripts/freeze_h.py freeze --version tier2-hidden-v1.1 --a2 results_tier2_ext/a2/full_v2_1 \
    #        --audit results_tier2_ext/audit_h/round1 --out results_tier2_ext/hidden_v1_1
"""

from __future__ import annotations

import argparse
import ast
import csv
import dataclasses
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks.contracts import load_contract  # noqa: E402
from meta_real_eval.benchmarks.witness import GEN_ALIAS  # noqa: E402
from meta_real_eval.oracles.spec import type_family  # noqa: E402

SPEC_V1 = ec.PROTOCOL_DIR / "output_spec_v1.json"
SPEC_V11 = ec.PROTOCOL_DIR / "output_spec_v1_1.json"
PROTOCOL_RETURNS = {"__str__": {"str"}, "__repr__": {"str"}, "__format__": {"str"}, "__len__": {"number"},
                    "__bool__": {"bool"}, "__hash__": {"number"}, "__bytes__": {"bytes"}}   # defined by the language
_SEQ = {"List", "list", "Sequence", "MutableSequence", "Tuple", "tuple", "Deque", "deque"}
_SET = {"Set", "set", "FrozenSet", "frozenset", "AbstractSet", "MutableSet"}
_MAP = {"Dict", "dict", "Mapping", "MutableMapping", "OrderedDict", "DefaultDict", "defaultdict"}
_SCALAR = {"str": "str", "bytes": "bytes", "int": "number", "float": "number", "bool": "bool", "complex": "complex"}
_UNKNOWN = {"Any", "object", "Iterable", "Iterator", "Generator", "Callable", "TypeVar", "Self"}


# --- Fix B helpers ----------------------------------------------------------------------------------

def annotation_families(node) -> set | None:
    """Allowed type families of a return annotation; None when the annotation does not fix one (decisions 10.8)."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        if node.value is None:
            return {"none"}
        if isinstance(node.value, str):                       # a string annotation
            try:
                return annotation_families(ast.parse(node.value, mode="eval").body)
            except SyntaxError:
                return None
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):          # X | Y
        a, b = annotation_families(node.left), annotation_families(node.right)
        return None if a is None or b is None else a | b
    if isinstance(node, (ast.Name, ast.Attribute)):
        name = node.id if isinstance(node, ast.Name) else node.attr
        if name == "None":
            return {"none"}
        if name in _UNKNOWN:
            return None
        if name in _SCALAR:
            return {_SCALAR[name]}
        if name in _SEQ:
            return {"seq"}
        if name in _SET:
            return {"set"}
        if name in _MAP:
            return {"map"}
        return {f"class:{name}"}
    if isinstance(node, ast.Subscript):
        base = node.value.id if isinstance(node.value, ast.Name) else getattr(node.value, "attr", None)
        args = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        if base == "Optional":
            inner = annotation_families(args[0])
            return None if inner is None else inner | {"none"}
        if base == "Union":
            parts = [annotation_families(a) for a in args]
            return None if any(p is None for p in parts) else set().union(*parts)
        if base in _SEQ:
            return {"seq"}
        if base in _SET:
            return {"set"}
        if base in _MAP:
            return {"map"}
        return None
    return None


def family_allowed(fam: list | tuple, allowed: set) -> bool:
    if fam[0] == "object":
        return f"class:{fam[1].split('.')[-1]}" in allowed
    return fam[0] in allowed


def skeleton_members(prompt: str, class_name: str) -> dict:
    """{name: (return annotation node or None, docstring, signature line)} of the skeleton's target class."""
    try:
        tree = ast.parse(prompt)
    except SyntaxError:
        return {}
    cls = next((n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    out = {}
    for n in (cls.body if cls else []):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = f"def {n.name}({ast.unparse(n.args)})" + (f" -> {ast.unparse(n.returns)}" if n.returns else "")
            out[n.name] = (n.returns, ast.get_docstring(n) or "", sig)
    return out


def class_doc(prompt: str, class_name: str) -> str:
    try:
        tree = ast.parse(prompt)
    except SyntaxError:
        return ""
    cls = next((n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    return (ast.get_docstring(cls) or "") if cls else ""


def type_entries(a2: dict, levels: dict, class_name: str) -> dict:
    """{callable: {"families": set, "defaulted": bool}} for every `type`-level output an H v1 test asserts:
    step outputs, and object fields that Fix A will restrict to their own `type` level."""
    from meta_real_eval.oracles.regression import level_of, step_name
    found: dict = {}
    for t in a2["final_tests"]:
        for i, st in enumerate(t["steps"]):
            exp = t["expected"].get(f"api:s{i}")
            if not exp:
                continue
            name = step_name(st["src"], GEN_ALIAS, class_name)
            if exp[0] == "@type" and name not in (None, "__init__") and level_of(levels, name) == "type":
                e = found.setdefault(name, {"families": set(), "defaulted": name not in levels})
                e["families"].add(tuple(exp[1]))
            if exp[0] == "obj":
                for field, ftok in exp[2].items():
                    base = field[:-2] if field.endswith("()") else field
                    fam = type_family(ftok)
                    if levels.get(base) == "type" and fam is not None:
                        found.setdefault(base, {"families": set(), "defaulted": False})["families"].add(tuple(fam))
    return found


def types(args, cfg) -> int:
    tasks, _ = ec.load_tasks(cfg, args.ungated)
    spec = json.loads(SPEC_V1.read_text(encoding="utf-8"))["tasks"]
    seen = set()
    if args.seen and args.seen.is_file():
        with args.seen.open(encoding="utf-8") as f:
            seen = {r["task"] for r in csv.DictReader(f)}
    rows, items = [], []
    L = ["# H v1.1 Fix B: blind review of `type` entries without a usable annotation (decisions 10.8)", "",
         "Per entry: does the **docstring** state or clearly imply this kind of return value? *keep* (assert the "
         "kind) / *none* (assert only a normal return). No grading outcome or completion is shown. Entries on tasks "
         "whose Stage 5 review cases were seen are marked **seen**.", "", "Write `keep` or `none` in `fixb_items.csv`.", ""]
    for d in sorted(p for p in args.hidden.iterdir() if (p / "a2.json").is_file()):
        lab = d.name
        a2 = json.loads((d / "a2.json").read_text(encoding="utf-8"))
        contract = load_contract(ec.REPO / a2["contract"]["path"])
        levels = spec[lab]["levels"]
        members = skeleton_members(tasks[lab].prompt, contract["class_name"])
        for name, e in sorted(type_entries(a2, levels, contract["class_name"]).items()):
            ann, doc, sig = members.get(name, (None, "", f"{name} (not in the skeleton)"))
            fams = sorted(e["families"])
            allowed = PROTOCOL_RETURNS.get(name) or annotation_families(ann)
            basis = "protocol" if name in PROTOCOL_RETURNS else ("annotation" if allowed is not None else None)
            row = {"task": lab, "callable": name, "defaulted": e["defaulted"], "families": fams,
                   "annotation": ast.unparse(ann) if ann is not None else None, "basis": basis}
            if allowed is not None:
                ok = all(family_allowed(f, allowed) for f in fams)
                row.update(decision="type" if ok else "none",
                           reason=f"{basis} allows {sorted(allowed)}; reference shows {['/'.join(f) for f in fams]}")
            else:
                iid = f"B-{len(items) + 1}"
                row.update(decision="review", item=iid)
                items.append({"id": iid, "task": lab, "callable": name, "reference_family": ";".join("/".join(f) for f in fams),
                              "seen_in_stage5_review": lab in seen, "verdict": ""})
                L += [f"## {iid}: {lab} `{name}`{' — **seen**' if lab in seen else ''}", "", "```python", sig,
                      f'    """{doc}"""' if doc else "    (no docstring)", "```", "",
                      f"Class docstring: {class_doc(tasks[lab].prompt, contract['class_name'])[:300] or '(none)'}", "",
                      f"The reference returns a value of kind **{', '.join('/'.join(f) for f in fams)}**.", "",
                      "Verdict (keep / none): ______", ""]
            rows.append(row)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "fixb.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    (args.out / "fixb_sheet.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    with (args.out / "fixb_items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "task", "callable", "reference_family", "seen_in_stage5_review", "verdict"])
        w.writeheader()
        w.writerows(items)
    mech = [r for r in rows if r["decision"] != "review"]
    print(f"type entries: {len(rows)}; mechanical {len(mech)} (to none: {sum(r['decision'] == 'none' for r in mech)}); "
          f"blind review {len(items)} -> {args.out / 'fixb_sheet.md'}")
    return 0


def spec_v11(args) -> int:
    rows = json.loads((args.out / "fixb.json").read_text(encoding="utf-8"))
    with (args.out / "fixb_items.csv").open(encoding="utf-8") as f:
        verdicts = {r["id"]: r["verdict"].strip() for r in csv.DictReader(f)}
    bad = [k for k, v in verdicts.items() if v not in ("keep", "none")]
    if bad:
        raise SystemExit(f"ERROR: missing or unknown verdicts (keep / none): {bad[:10]}")
    spec = json.loads(SPEC_V1.read_text(encoding="utf-8"))
    changes = 0
    for r in rows:
        level = r["decision"] if r["decision"] != "review" else ("type" if verdicts[r["item"]] == "keep" else "none")
        reason = r.get("reason") or f"blind review {r['item']}: {verdicts[r['item']]}"
        entry = spec["tasks"][r["task"]]
        before = entry["levels"].get(r["callable"], "type (default)")
        entry["levels"][r["callable"]] = level
        entry.setdefault("v1_1_changes", []).append({"callable": r["callable"], "from": before, "to": level,
                                                     "basis": r["basis"] or "blind review", "reason": reason})
        changes += before != level
    spec["version"] = "output_spec_v1_1"
    spec["note"] = ("H v1.1 (decisions 10.8): output_spec_v1 with Fix B applied to every type entry an H v1 test asserts; "
                    "a labelled post-hoc correction")
    SPEC_V11.write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(rows)} entries checked, {changes} level change(s) -> {SPEC_V11}")
    return 0


# --- build ------------------------------------------------------------------------------------------

def implied(new, old) -> bool:
    """Is the v1.1 assertion `new` the same as, or weaker than, the v1 assertion `old`? (decisions 10.8)"""
    if new == old:
        return True
    if new is None or old is None:
        return False
    if new[0] == "@any":
        return old[0] != "exc"
    if new[0] == "@type":
        return old[0] not in ("@any", "@type", "exc") and type_family(old) == new[1]
    if new[0] == "obj" and old[0] == "obj" and new[1] == old[1]:
        return all(k in old[2] and implied(v, old[2][k]) for k, v in new[2].items())
    return False


def build_task(lab: str, hidden: Path, out: Path, tasks: dict, spec11: dict, timeout_s: float) -> dict:
    from meta_real_eval.oracles.admission import admit, private_rename, run_tests, validate_control
    from meta_real_eval.oracles.regression import A2Settings, emit, expected_tokens, reference_entries
    a2 = json.loads((hidden / lab / "a2.json").read_text(encoding="utf-8"))
    task = tasks[lab]
    contract = load_contract(ec.REPO / a2["contract"]["path"])
    levels = spec11[lab]["levels"]
    settings = A2Settings(**a2["settings"])
    ws = settings.witness_settings()
    v1 = {t["scenario_id"]: t for t in a2["final_tests"]}
    scs = [{"scenario_id": t["scenario_id"], "steps": t["steps"], "api_flags": t["api_flags"]} for t in a2["final_tests"]]
    entries = {e["scenario"]["scenario_id"]: e for e in reference_entries(task.module_name, task.reference_code, contract,
                                                                          scs, ws)}
    tests, dropped, violations = [], [], []
    for sid, t in v1.items():
        e = entries.get(sid)
        if e is None:
            dropped.append({"scenario_id": sid, "reason": "not valid on the reference re-run"})
            continue
        new = {k: v for k, v in expected_tokens(e, levels, contract["class_name"], fix_a=True).items() if k in t["expected"]}
        violations += [f"{sid}/{k}" for k, v in new.items() if not implied(v, t["expected"][k])]
        if not new:
            dropped.append({"scenario_id": sid, "reason": "no assertion left"})
            continue
        tests.append({**t, "expected": new, "v1_name": t["name"]})
    if violations:
        raise SystemExit(f"ERROR: {lab}: v1.1 assertions not implied by v1: {violations[:5]}")
    for i, t in enumerate(tests):
        t["name"] = f"test_h_{i}"
    kept, adm, control = [], {}, {"kind": "private_rename", "applicable": False}
    if tests:
        code = emit(task.task_id, task.module_name, contract, tests)
        adm = admit(task.module_name, task.reference_code, code, [t["name"] for t in tests], timeout_s)
        kept = [t for t in tests if adm[t["name"]]["admitted"]]
        dropped += [{"scenario_id": t["scenario_id"], "reason": f"admission: {adm[t['name']]['reason']}"}
                    for t in tests if not adm[t["name"]]["admitted"]]
        variant = private_rename(task.reference_code, contract["class_name"])
        if variant is not None and kept:
            ents = [entries[t["scenario_id"]] for t in kept]
            val = validate_control(task.module_name, variant, contract, ents, ws)
            control = {"kind": "private_rename", "applicable": True, **val}
            if val["valid"]:
                for i, t in enumerate(kept):
                    t["name"] = f"test_h_{i}"
                kc = emit(task.task_id, task.module_name, contract, kept)
                outs = run_tests(task.module_name, variant, kc, [t["name"] for t in kept], timeout_s)
                over = [t["scenario_id"] for t in kept if outs[t["name"]] != "ordinary_pass"]
                control["over_specified"] = over
                dropped += [{"scenario_id": s, "reason": "fails the validated control"} for s in over]
                kept = [t for t in kept if t["scenario_id"] not in over]
    for i, t in enumerate(kept):
        t["name"] = f"test_h_{i}"
    final = emit(task.task_id, task.module_name, contract, kept) if kept else ""
    rec = {**{k: v for k, v in a2.items() if k not in ("final_tests", "final_code", "admission", "control")},
           "h_version": "tier2-hidden-v1.1", "output_levels": levels, "final_tests": kept, "final_code": final,
           # every H v1 task stays in v1.1 (same cohort); with no test left its suite is empty (H passes everything)
           "admission": adm, "control": control, "ready": True, "empty_suite": not kept,
           "v1_1": {"v1_tests": len(v1), "kept": len(kept), "dropped": dropped, "subset_check": "passed",
                    "names": {t["v1_name"]: t["name"] for t in kept}}}
    d = out / lab
    d.mkdir(parents=True, exist_ok=True)
    (d / "a2.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    (d / "hidden_tests.py").write_text(final, encoding="utf-8")
    return {"task": lab, "v1_tests": len(v1), "kept": len(kept), "dropped": len(dropped), "ready": bool(kept)}


def build(args, cfg) -> int:
    from meta_real_eval.core import canary
    from meta_real_eval.core.provenance import write_run_manifest
    import freeze_h
    freeze_h.verify(args.hidden)                     # built from the frozen H v1 tests, nothing else
    if not SPEC_V11.is_file():
        raise SystemExit(f"ERROR: {SPEC_V11} missing: run `h_v11.py spec` first")
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"ERROR: {args.out} is not empty")
    policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=True)
    policy.activate()
    report = canary.require_canary(policy=policy, timeout_s=cfg.execution.timeout_s, warmup=True)
    tasks, _ = ec.load_tasks(cfg, args.ungated)
    spec11 = json.loads(SPEC_V11.read_text(encoding="utf-8"))["tasks"]
    labs = sorted(p.name for p in args.hidden.iterdir() if (p / "a2.json").is_file())
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        res = list(ex.map(lambda lab: build_task(lab, args.hidden, args.out, tasks, spec11, cfg.execution.timeout_s), labs))
    summary = {"tasks": len(res), "ready": sum(r["ready"] for r in res), "v1_tests": sum(r["v1_tests"] for r in res),
               "kept": sum(r["kept"] for r in res), "dropped": sum(r["dropped"] for r in res), "per_task": res}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    write_run_manifest(args.out, stage="h_v1_1_build", config_path=args.config,
                       inputs={"hidden_v1": args.hidden, "output_spec_v1_1": SPEC_V11},
                       checks={"canary": report})
    print(json.dumps({k: v for k, v in summary.items() if k != "per_task"}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["types", "spec", "build"])
    ap.add_argument("--config", type=Path)
    ap.add_argument("--hidden", type=Path, help="the frozen H v1 bundle")
    ap.add_argument("--seen", type=Path, help="types: the Stage 5 review items.csv (tasks whose cases were seen)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--ungated", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "spec":
        return spec_v11(args)
    if args.config is None or args.hidden is None:
        raise SystemExit("ERROR: --config and --hidden are required")
    cfg = ec.load_ext_config(args.config)
    return types(args, cfg) if args.cmd == "types" else build(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
