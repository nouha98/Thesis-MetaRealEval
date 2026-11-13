"""Audit of the stored whole-source LLM mutants (extensions plan rev. 8, Stage 1b).

    python scripts/audit_llm_mutants.py --config config/tier2_realclasseval.yaml \
        --results results/results_tier2_runs/full_v4/combined \
        --out results_tier2_ext/audit/llm_mutants

Read-only on the results: it reads ``rq1/generate/<task>/llm_mutants.json``,
``rq1/evaluate/<task>/{llm_equiv_filter,kill_matrix}.json`` and
``stage0/<task>/mutants.json`` and writes only under ``--out``.

Per LLM mutant it records, against the reference (``bench.mutation_source``):
  * parse status;
  * which functions/methods changed (qualified names such as ``Class.method``;
    docstrings ignored), added or removed, and whether a signature changed;
  * changes outside functions: imports, class-level statements, other
    top-level statements;
  * edit size: changed lines of the normalised source (``ast.unparse``,
    docstrings stripped) and an approximate node edit count (pre-order AST
    labels aligned with difflib, sum of the larger side of every non-equal
    block);
  * whether the ``method`` metadata field is present (the generator never
    sets it for LLM mutants) and the method inferred from the diff;
  * duplicates: within a model, across models, and against operator
    (Stage 0) mutants, both exactly (the generator's own normaliser,
    ``ast.unparse(ast.parse(code))``) and ignoring docstrings;
  * the stored equivalence verdict and kill outcome.

The comparison is generic over functions, so it runs unchanged on Tier 1
(HumanEval functions) and Tier 2 (RealClassEval classes).
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import statistics
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402
from meta_real_eval.core.provenance import write_run_manifest  # noqa: E402

FUNC = (ast.FunctionDef, ast.AsyncFunctionDef)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def parse(code: str) -> Optional[ast.Module]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)      # e.g. '\s' in a stored string literal
        try:
            return ast.parse(code)
        except (SyntaxError, ValueError):
            return None


def normalise(code: str) -> str:
    """The generator's own normaliser (rq1/llm_mutator._normalise)."""
    tree = parse(code)
    return ast.unparse(tree) if tree is not None else code.strip()


def _is_docstring(stmt: ast.stmt) -> bool:
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str))


def strip_docstrings(tree: ast.AST) -> ast.AST:
    """Copy of ``tree`` without docstrings (an emptied body gets ``pass``)."""
    tree = parse(ast.unparse(tree))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, *FUNC)) and node.body and _is_docstring(node.body[0]):
            node.body = node.body[1:] or [ast.Pass()]
    return tree


def normalise_no_doc(code: str) -> str:
    tree = parse(code)
    return ast.unparse(strip_docstrings(tree)) if tree is not None else code.strip()


def functions(tree: ast.Module) -> dict[str, ast.AST]:
    """Qualified name -> function node for module-level functions and (nested) class methods.
    Functions nested inside functions belong to their parent."""
    out: dict[str, ast.AST] = {}

    def visit(body, prefix: str):
        for node in body:
            if isinstance(node, FUNC):
                out[prefix + node.name] = node
            elif isinstance(node, ast.ClassDef):
                visit(node.body, f"{prefix}{node.name}.")
    visit(tree.body, "")
    return out


def _dump(node: Optional[ast.AST]) -> str:
    return "" if node is None else ast.dump(node, include_attributes=False)


def signature(fn: ast.AST) -> str:
    return "|".join([_dump(fn.args), _dump(fn.returns), *(_dump(d) for d in fn.decorator_list)])


def non_function_statements(tree: ast.Module) -> dict[str, list[str]]:
    """Imports, class-level statements and other top-level statements (docstrings excluded)."""
    imports, class_level, other = [], [], []

    def visit_class(cls: ast.ClassDef, prefix: str):
        for node in cls.body:
            if isinstance(node, FUNC) or _is_docstring(node):
                continue
            if isinstance(node, ast.ClassDef):
                visit_class(node, f"{prefix}{node.name}.")
            else:
                class_level.append(f"{prefix}:{_dump(node)}")
        class_level.append(f"{prefix}bases:{'|'.join(_dump(b) for b in cls.bases)}")

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(_dump(node))
        elif isinstance(node, ast.ClassDef):
            visit_class(node, f"{node.name}.")
        elif not isinstance(node, FUNC) and not _is_docstring(node):
            other.append(_dump(node))
    return {"imports": sorted(imports), "class_level": sorted(class_level), "other": sorted(other)}


def _label(node: ast.AST) -> str:
    name = type(node).__name__
    for field in ("id", "attr", "name", "arg"):
        v = getattr(node, field, None)
        if isinstance(v, str):
            return f"{name}:{v}"
    if isinstance(node, ast.Constant):
        return f"Constant:{node.value!r}"
    return name


def preorder(node: ast.AST) -> list[str]:
    out = [_label(node)]
    for child in ast.iter_child_nodes(node):
        out.extend(preorder(child))
    return out


def node_edit(a: ast.AST, b: ast.AST) -> int:
    sm = difflib.SequenceMatcher(a=preorder(a), b=preorder(b), autojunk=False)
    return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")


def changed_lines(a: str, b: str) -> int:
    return sum(1 for line in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0)
               if line[:1] in "+-" and not line.startswith(("+++", "---")))


def compare(reference: str, mutant: str) -> dict:
    """Edit scope and size of ``mutant`` against ``reference`` (docstrings ignored)."""
    rt, mt = parse(reference), parse(mutant)
    if mt is None:
        return {"parse_ok": False}
    rt_nd, mt_nd = strip_docstrings(rt), strip_docstrings(mt)
    rf, mf = functions(rt_nd), functions(mt_nd)
    changed = sorted(n for n in rf.keys() & mf.keys() if _dump(rf[n]) != _dump(mf[n]))
    sig_changed = sorted(n for n in rf.keys() & mf.keys() if signature(rf[n]) != signature(mf[n]))
    rs, ms = non_function_statements(rt_nd), non_function_statements(mt_nd)
    outside = {k: rs[k] != ms[k] for k in rs}
    docstring_changed = normalise(reference) != normalise(mutant) and _dump(rt_nd) == _dump(mt_nd)
    n_fn = len(changed) + len(mf.keys() - rf.keys()) + len(rf.keys() - mf.keys())
    if _dump(rt_nd) == _dump(mt_nd):
        scope = "docstring_only" if docstring_changed else "identical"
    elif n_fn == 0:
        scope = "outside_functions_only"
    elif n_fn == 1 and not any(outside.values()):
        scope = "single_function"
    elif n_fn == 1:
        scope = "single_function_plus_outside"
    else:
        scope = "multi_function"
    return {
        "parse_ok": True, "scope": scope,
        "functions_changed": changed,
        "functions_added": sorted(mf.keys() - rf.keys()),
        "functions_removed": sorted(rf.keys() - mf.keys()),
        "n_functions_touched": n_fn,
        "signature_changed": sig_changed,
        "imports_changed": outside["imports"], "class_level_changed": outside["class_level"],
        "other_top_level_changed": outside["other"],
        "inferred_method": changed[0] if scope == "single_function" and changed else None,
        "changed_lines": changed_lines(ast.unparse(rt_nd), ast.unparse(mt_nd)),
        "node_edit": node_edit(rt_nd, mt_nd),
    }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_references(cfg: Config) -> dict[str, str]:
    """label -> mutation source. Tier 2's gate manifest may be absent locally; the corpus holds
    the reference, so fall back to the ungated corpus tasks (labels are the same)."""
    bench = get_benchmark(cfg)
    try:
        tasks = bench.load_tasks()
    except Exception as exc:  # ManifestMissing on a machine without the gate manifest
        corpus_tasks = getattr(bench, "corpus_tasks", None)
        if corpus_tasks is None:
            raise
        print(f"note: {type(exc).__name__}; reading references from the ungated corpus")
        tasks = corpus_tasks()
    return {t.label: bench.mutation_source(t) for t in tasks}


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def audit(results: Path, refs: dict[str, str]) -> tuple[list[dict], dict]:
    records: list[dict] = []
    operator_counts: dict[str, Counter] = {}
    missing_reference: list[str] = []
    for gdir in sorted((results / "rq1" / "generate").iterdir()):
        if not gdir.is_dir():
            continue
        label = gdir.name
        mutants = read_json(gdir / "llm_mutants.json", [])
        if label not in refs:
            missing_reference.append(label)
            continue
        ref = refs[label]
        equiv = {e["mutant_id"]: e for e in read_json(results / "rq1" / "evaluate" / label / "llm_equiv_filter.json", [])}
        kills = {k["mutant_id"]: k["is_killed"]
                 for k in read_json(results / "rq1" / "evaluate" / label / "kill_matrix.json", [])}
        ops = read_json(results / "stage0" / label / "mutants.json", [])
        operator_counts[label] = Counter(m["operator"] for m in ops)
        op_norm = {normalise(m["code"]) for m in ops}
        op_norm_nd = {normalise_no_doc(m["code"]) for m in ops}
        ref_norm, ref_norm_nd = normalise(ref), normalise_no_doc(ref)
        for m in mutants:
            rec = {"task": label, "mutant_id": m["mutant_id"],
                   "model": m.get("source_model") or m["mutant_id"].split("-", 1)[1].rsplit("-", 1)[0],
                   "has_method_metadata": bool(m.get("method")),
                   **compare(ref, m["code"])}
            rec["norm"] = normalise(m["code"])
            rec["norm_nd"] = normalise_no_doc(m["code"])
            rec["equal_to_reference_normalised"] = rec["norm"] == ref_norm
            rec["equal_to_reference_ignoring_docstrings"] = rec["norm_nd"] == ref_norm_nd
            rec["duplicate_of_operator_mutant"] = rec["norm"] in op_norm
            rec["duplicate_of_operator_mutant_ignoring_docstrings"] = rec["norm_nd"] in op_norm_nd
            e = equiv.get(m["mutant_id"])
            rec["equivalence_reason"] = e["reason"] if e else "not_evaluated"
            rec["is_equivalent"] = e["is_equivalent"] if e else None
            rec["is_killed"] = kills.get(m["mutant_id"])
            records.append(rec)
    _mark_duplicates(records)
    for r in records:
        r.pop("norm"), r.pop("norm_nd")
    meta = {"operator_counts": {k: dict(v) for k, v in operator_counts.items()},
            "tasks_without_reference": missing_reference}
    return records, meta


def _mark_duplicates(records: list[dict]) -> None:
    """Within-model and cross-model duplicate flags, exact and docstring-insensitive.
    The first mutant of a group (in task / id order) is the original; later ones are copies."""
    for key, suffix in (("norm", ""), ("norm_nd", "_ignoring_docstrings")):
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for r in records:
            groups[(r["task"], r[key])].append(r)
        for members in groups.values():
            models = [m["model"] for m in members]
            seen_model: Counter = Counter()
            for i, r in enumerate(members):
                r[f"within_model_copy{suffix}"] = seen_model[r["model"]] > 0
                seen_model[r["model"]] += 1
                r[f"cross_model_shared{suffix}"] = len(set(models)) > 1
                r[f"group_size{suffix}"] = len(members)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _dist(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    q = statistics.quantiles(values, n=4) if len(values) > 1 else [values[0]] * 3
    return {"n": len(values), "median": statistics.median(values), "q1": q[0], "q3": q[2],
            "max": max(values), "mean": statistics.fmean(values)}


def _rate(num: int, den: int) -> Optional[float]:
    return num / den if den else None


def summarise(records: list[dict], meta: dict) -> dict:
    def block(rs: list[dict]) -> dict:
        ok = [r for r in rs if r["parse_ok"]]
        scope = Counter(r["scope"] for r in ok)
        by_scope = {}
        for s in sorted(scope):
            grp = [r for r in ok if r["scope"] == s]
            evaluated = [r for r in grp if r["is_equivalent"] is not None]
            non_eq = [r for r in evaluated if r["is_equivalent"] is False and r["is_killed"] is not None]
            by_scope[s] = {
                "n": len(grp),
                "equivalent_share": _rate(sum(r["is_equivalent"] for r in evaluated), len(evaluated)),
                "n_non_equivalent_with_kill_outcome": len(non_eq),
                "kill_rate": _rate(sum(r["is_killed"] for r in non_eq), len(non_eq)),
            }
        return {
            "n_mutants": len(rs), "n_tasks": len({r["task"] for r in rs}),
            "parse_ok": len(ok),
            "scope": dict(scope), "by_scope": by_scope,
            "n_functions_touched": dict(Counter(min(r["n_functions_touched"], 3) for r in ok)),
            "signature_changed": sum(bool(r["signature_changed"]) for r in ok),
            "imports_changed": sum(r["imports_changed"] for r in ok),
            "class_level_changed": sum(r["class_level_changed"] for r in ok),
            "other_top_level_changed": sum(r["other_top_level_changed"] for r in ok),
            "changed_lines": _dist([r["changed_lines"] for r in ok]),
            "node_edit": _dist([r["node_edit"] for r in ok]),
            "method_metadata_missing": sum(not r["has_method_metadata"] for r in rs),
            "inferred_method_available": sum(r.get("inferred_method") is not None for r in ok),
            "within_model_copies": sum(r["within_model_copy"] for r in rs),
            "within_model_copies_ignoring_docstrings": sum(r["within_model_copy_ignoring_docstrings"] for r in rs),
            "in_cross_model_group": sum(r["cross_model_shared"] for r in rs),
            "in_cross_model_group_ignoring_docstrings": sum(r["cross_model_shared_ignoring_docstrings"] for r in rs),
            "duplicate_of_operator_mutant": sum(r["duplicate_of_operator_mutant"] for r in rs),
            "duplicate_of_operator_mutant_ignoring_docstrings":
                sum(r["duplicate_of_operator_mutant_ignoring_docstrings"] for r in rs),
            "equal_to_reference_ignoring_docstrings": sum(r["equal_to_reference_ignoring_docstrings"] for r in rs),
            "equivalence_reason": dict(Counter(r["equivalence_reason"] for r in rs)),
        }

    models = sorted({r["model"] for r in records})
    per_task = Counter(r["task"] for r in records)
    caps = Counter()
    max_per_op: dict[str, int] = defaultdict(int)
    for counts in meta["operator_counts"].values():
        for op, n in counts.items():
            max_per_op[op] = max(max_per_op[op], n)
            caps[op] += n >= 5
    return {
        "overall": block(records),
        "per_model": {m: block([r for r in records if r["model"] == m]) for m in models},
        "llm_mutants_per_task": _dist(list(per_task.values())),
        "operator_mutants": {"max_per_operator_per_task": dict(max_per_op),
                             "tasks_at_cap_5_per_operator": dict(caps),
                             "n_tasks": len(meta["operator_counts"])},
        "tasks_without_reference": meta["tasks_without_reference"],
    }


def _f(v, d=2) -> str:
    return "n/a" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))


def write_markdown(summary: dict, path: Path, results: Path) -> None:
    o = summary["overall"]
    L = ["# Audit of the stored whole-source LLM mutants", "",
         f"*Generated by `scripts/audit_llm_mutants.py` from `{results.as_posix()}` (read-only).*", "",
         f"- Mutants: **{o['n_mutants']}** on {o['n_tasks']} tasks "
         f"(per task median {_f(summary['llm_mutants_per_task'].get('median'))}, max {summary['llm_mutants_per_task'].get('max')}); "
         f"parse ok {o['parse_ok']}.",
         f"- `method` metadata missing: **{o['method_metadata_missing']} / {o['n_mutants']}**; "
         f"a single changed method can be inferred from the diff for {o['inferred_method_available']}.",
         f"- Signature changed: {o['signature_changed']}; imports changed: {o['imports_changed']}; "
         f"class-level statements changed: {o['class_level_changed']}; other top-level changed: {o['other_top_level_changed']}.",
         f"- Edit size (normalised, docstrings ignored): changed lines median {_f(o['changed_lines'].get('median'), 1)} "
         f"[IQR {_f(o['changed_lines'].get('q1'), 1)}-{_f(o['changed_lines'].get('q3'), 1)}, max {o['changed_lines'].get('max')}]; "
         f"node edits median {_f(o['node_edit'].get('median'), 1)} [IQR {_f(o['node_edit'].get('q1'), 1)}-"
         f"{_f(o['node_edit'].get('q3'), 1)}, max {o['node_edit'].get('max')}].",
         f"- Duplicates: within a model {o['within_model_copies']} (ignoring docstrings {o['within_model_copies_ignoring_docstrings']}); "
         f"in a group shared across models {o['in_cross_model_group']} ({o['in_cross_model_group_ignoring_docstrings']}); "
         f"identical to an operator mutant {o['duplicate_of_operator_mutant']} ({o['duplicate_of_operator_mutant_ignoring_docstrings']}); "
         f"identical to the reference ignoring docstrings {o['equal_to_reference_ignoring_docstrings']}.", "",
         "## Edit scope", "",
         "| Scope | n | equivalent share | non-equivalent with kill outcome | kill rate |",
         "|---|---|---|---|---|"]
    for s, b in o["by_scope"].items():
        L.append(f"| {s} | {b['n']} | {_f(b['equivalent_share'])} | {b['n_non_equivalent_with_kill_outcome']} | {_f(b['kill_rate'])} |")
    L += ["", "Functions touched (3 = three or more): " + ", ".join(f"{k}: {v}" for k, v in sorted(o["n_functions_touched"].items())), "",
          "## Per model", "",
          "| Model | mutants | single function | multi function | outside only | docstring only / identical | median changed lines | cross-model shared | operator duplicate |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m, b in summary["per_model"].items():
        sc = b["scope"]
        L.append(f"| {m} | {b['n_mutants']} | {sc.get('single_function', 0)} | {sc.get('multi_function', 0)} | "
                 f"{sc.get('outside_functions_only', 0) + sc.get('single_function_plus_outside', 0)} | "
                 f"{sc.get('docstring_only', 0) + sc.get('identical', 0)} | {_f(b['changed_lines'].get('median'), 1)} | "
                 f"{b['in_cross_model_group']} | {b['duplicate_of_operator_mutant']} |")
    L += ["", "## Stored equivalence verdicts", "",
          ", ".join(f"{k}: {v}" for k, v in sorted(o["equivalence_reason"].items())), "",
          "## Operator (Stage 0) mutants: per-operator cap", "",
          f"Maximum per operator per task: {summary['operator_mutants']['max_per_operator_per_task']}; "
          f"tasks at the cap of 5: {summary['operator_mutants']['tasks_at_cap_5_per_operator']} "
          f"(of {summary['operator_mutants']['n_tasks']}). `core/config.py` says the Tier 2 config raises "
          "`max_mutants_per_operator`, but `config/tier2_realclasseval.yaml` does not set it, so Tier 2 ran with the default 5.", ""]
    if summary["tasks_without_reference"]:
        L.append(f"Tasks skipped (no reference found): {summary['tasks_without_reference']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True, help="run root holding rq1/ and stage0/")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    cfg = Config.from_yaml(args.config)
    refs = load_references(cfg)
    records, meta = audit(args.results, refs)
    summary = summarise(records, meta)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "per_mutant.json").write_text(json.dumps(records, indent=1), encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    write_markdown(summary, args.out / "summary.md", args.results)
    write_run_manifest(
        args.out, stage="stage1_llm_mutant_audit", config_path=args.config,
        inputs={"rq1_generate": args.results / "rq1" / "generate",
                "rq1_evaluate": args.results / "rq1" / "evaluate",
                "stage0": args.results / "stage0",
                "benchmark_data": [p for p in (cfg.benchmark.data_path,) if p]},
        settings={"results": str(args.results)}, argv=sys.argv if argv is None else argv)
    o = summary["overall"]
    print(f"{o['n_mutants']} mutants on {o['n_tasks']} tasks; scope {o['scope']}; "
          f"method metadata missing {o['method_metadata_missing']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
