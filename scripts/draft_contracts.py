"""Draft task contracts and a review sheet (plan rev. 9, Stage 2, D1-D2).

    python scripts/draft_contracts.py --config config/tier2_extensions.yaml --tasks dev [--ungated]

Writes config/extensions_protocol/contracts_v1/drafts/<task>.json (status "draft") and
doc/extensions/contract_review_<name>.md. Review: copy a draft to contracts_v1/reviewed/, edit
it (types, constraints, documented raises, own-class comparison), and set
review.status = "reviewed" with reviewer and date. Only reviewed contracts count for primary
results; drafts are for the development pilot.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks.contracts import draft_contract, save_contract  # noqa: E402

DRAFTS = ec.PROTOCOL_DIR / "contracts_v1" / "drafts"
REVIEWED = ec.PROTOCOL_DIR / "contracts_v1" / "reviewed"
WEAK_SOURCES = ("p_literals", "default", "none")


def select(cfg, tasks: dict, which: list[str]) -> list[str]:
    if which == ["dev"]:
        return list(cfg.extensions.development_tasks)
    if which == ["all"]:
        return sorted(tasks)
    return which


def fmt_type(spec: dict) -> str:
    t = spec["t"]
    if t == "union":
        return " | ".join(fmt_type(o) for o in spec["options"])
    if t in ("list", "set"):
        return f"{t}[{fmt_type(spec['items'])}]"
    if t == "tuple":
        return f"tuple[{fmt_type(spec['items'])}, ...]" if spec.get("variadic") else \
            "tuple[" + ", ".join(fmt_type(s) for s in spec["items"]) + "]"
    if t == "dict":
        return f"dict[{fmt_type(spec['keys'])}, {fmt_type(spec['values'])}]"
    if t == "unsupported":
        return f"UNSUPPORTED ({spec.get('why', '')})"
    return t


def sheet(contracts: list[dict], name: str) -> str:
    sup = [c for c in contracts if c["support"]["supported"]]
    L = [f"# Contract review sheet: {name}", "",
         f"{len(contracts)} tasks drafted; {len(sup)} supported by the draft. For each **supported** task, check and "
         "mark a verdict: `accept`, `edit` (say what) or `reject` (task leaves the supported subset).", "",
         "Check in particular:",
         "1. **Types** whose source is `p_literals`, `default` or `none` (weak evidence) against the docstring.",
         "2. **Constraints** the docstring states (ranges, non-empty, allowed values); none are drafted automatically.",
         "3. **Documented exceptions**: an exception the docstring describes but the draft misses would wrongly "
         "make inputs domain-uncertain.",
         "4. **Own-class comparison**: `opaque` (returned instances never asserted) or `accessors` (the listed "
         "documented properties/attributes); never private state.",
         "5. Methods the draft does not generate (and why).", "",
         "| # | task | supported | reasons | verdict | note |", "|---|---|---|---|---|---|"]
    for i, c in enumerate(contracts, 1):
        s = c["support"]
        L.append(f"| {i} | {c['task']} | {'yes' if s['supported'] else 'no'} | {'; '.join(s['reasons']) or '-'} | | |")
    for c in sup:
        L += ["", f"## {c['task']} (`{c['class_name']}`)", "",
              f"Own-class comparison: `{json.dumps(c['comparison']['own_classes'])}`; floats rel {c['comparison']['float_rel_tol']}, "
              f"abs {c['comparison']['float_abs_tol']}; numeric `{c['comparison']['numeric']}`. Documented attributes: "
              f"{c['attributes'] or '-'}; properties: {c['properties'] or '-'}.", "",
              "| callable | generated | parameter | kind | type | source | hints | raises (documented) |",
              "|---|---|---|---|---|---|---|---|"]
        rows = [("__init__", True, c["constructor"]["params"], c["constructor"]["raises_documented"])] + \
            [(m, r["generate"], r["params"], r["raises_documented"]) for m, r in sorted(c["methods"].items())]
        for name_, gen, params, raises in rows:
            if not params:
                L.append(f"| {name_} | {gen} | - | - | - | - | - | {', '.join(raises) or '-'} |")
            for p in params:
                weak = " **(weak)**" if p["type_source"] in WEAK_SOURCES else ""
                hints = ", ".join(repr(h) for h in p["hints"][:5])
                L.append(f"| {name_} | {gen} | {p['name']} | {p['kind']} | {fmt_type(p['type'])} | "
                         f"{p['type_source']}{weak} | {hints[:60]} | {', '.join(raises) or '-'} |")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--tasks", nargs="+", default=["dev"], help="dev | all | task labels")
    ap.add_argument("--ungated", action="store_true")
    ap.add_argument("--name", default=None)
    args = ap.parse_args(argv)
    cfg = ec.load_ext_config(args.config)
    ec.pins_ok(cfg)
    tasks, gated = ec.load_tasks(cfg, args.ungated)
    dep = ec.read_json(ec.DEPENDENCY_SCAN, {})
    labels = select(cfg, tasks, args.tasks)
    contracts = []
    for lab in labels:
        c = draft_contract(tasks[lab], dep)
        save_contract(DRAFTS, c)
        contracts.append(c)
    name = args.name or ("dev" if args.tasks == ["dev"] else "custom")
    out = ec.REPO / "doc" / "extensions" / f"contract_review_{name}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(sheet(contracts, name), encoding="utf-8")
    n_sup = sum(c["support"]["supported"] for c in contracts)
    print(f"{len(contracts)} contracts drafted -> {DRAFTS}; {n_sup} supported; review sheet {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
