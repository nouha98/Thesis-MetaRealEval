"""R7 review sheet (decisions 10.2): every public callable of the accepted contracts with its SKELETON
docstring (what the coding models saw), and the level currently recorded in output_spec_v1.json.

    python scripts/output_spec_sheet.py --config config/tier2_extensions.yaml --tasks eval \
        --out doc/extensions/output_spec_review_eval.md [--ungated]

Levels: value (the docstring determines the returned value for every contract-valid input) /
type (only the kind of value is promised) / none (no return value is promised). Judge from the
docstring text only, never from the reference body or any outcome.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

REVIEWED = ec.PROTOCOL_DIR / "contracts_v1" / "reviewed"
SPEC = ec.PROTOCOL_DIR / "output_spec_v1.json"


def docstrings(prompt: str, class_name: str) -> dict:
    """{callable name: docstring} of the target class in the skeleton (properties included)."""
    try:
        tree = ast.parse(prompt)
    except SyntaxError:
        return {}
    cls = next((n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    if cls is None:
        return {}
    return {n.name: (ast.get_docstring(n) or "") for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def callables(contract: dict) -> list[str]:
    return sorted(set(contract["methods"]) | {p if isinstance(p, str) else p.get("name") for p in contract.get("properties", [])})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--tasks", nargs="+", default=["eval"], help="dev | eval | labels")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ungated", action="store_true")
    args = ap.parse_args(argv)
    cfg = ec.load_ext_config(args.config)
    tasks, _ = ec.load_tasks(cfg, args.ungated)
    dev = list(cfg.extensions.development_tasks)
    labels = dev if args.tasks == ["dev"] else sorted(set(tasks) - set(dev)) if args.tasks == ["eval"] else args.tasks
    spec = json.loads(SPEC.read_text(encoding="utf-8")).get("tasks", {}) if SPEC.exists() else {}
    L = ["# R7 output specification review", "",
         "Per callable: **value** (the docstring determines the returned value for every contract-valid input) / "
         "**type** (only the kind is promised) / **none** (no return value is promised). Judge from the docstring only.",
         ""]
    n = 0
    for lab in labels:
        p = REVIEWED / f"{lab}.json"
        if not p.exists():
            continue
        c = json.loads(p.read_text(encoding="utf-8"))
        if not c["support"]["supported"]:
            continue
        n += 1
        docs = docstrings(tasks[lab].prompt, c["class_name"])
        entry = spec.get(lab, {})
        L += [f"## {lab} (`{c['class_name']}`) - {entry.get('status', 'not drafted')}", "",
              "| callable | skeleton docstring | level | reason |", "|---|---|---|---|"]
        for name in callables(c):
            d = " ".join(docs.get(name, "").split())[:400].replace("|", "\\|") or "(none)"
            L.append(f"| `{name}` | {d} | {entry.get('levels', {}).get(name, '')} | "
                     f"{entry.get('notes', {}).get(name, '').replace('|', '/')} |")
        L.append("")
    L.insert(2, f"{n} supported tasks.\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{n} tasks -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
