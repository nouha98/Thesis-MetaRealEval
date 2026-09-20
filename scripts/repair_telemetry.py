#!/usr/bin/env python
"""Report how the extraction repair ladder behaves across the recorded corpus.

The ladder in ``rq2/evaluator.py`` tries candidate repairs in turn and takes the
first that assembles cleanly. That is only safe while the rungs do not compete:
if two of them both assemble a completion but produce *different* programs, the
ladder is silently choosing between rival interpretations of what the model
meant, and the pass rate it feeds becomes an artifact of rung ordering.

So this reports two things per model:

  * which rung fired, and how often -- the repair's actual reach, and
  * the ambiguous count: completions where >1 rung assembles cleanly but the
    resulting ASTs differ. This must stay 0. If it ever rises, the ladder needs
    a real disambiguation rule, not a reordering.

Reads only ``results/rq2/generate/*/completions.json``; executes nothing.

Usage:
    .venv/Scripts/python.exe scripts/repair_telemetry.py
    .venv/Scripts/python.exe scripts/repair_telemetry.py --relation original
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.data_loader import load_humaneval, task_label  # noqa: E402
from meta_real_eval.rq2.evaluator import (                              # noqa: E402
    _REPAIR_LADDER,
    _assembles_cleanly,
    _defines_entry_point,
    _extract_function_body,
)


def _is_docstring(node: ast.stmt) -> bool:
    return (isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str))


def _structural_dump(source: str) -> str:
    """AST fingerprint that ignores docstring text.

    Two repairs that differ only in how much whitespace sits inside a docstring
    are not rival readings of the program: a bare string-literal statement is
    evaluated and discarded, so its content cannot change behaviour. Without
    this, a completion that merely echoes the spec back registers as an
    ambiguity -- the indentation lands inside the literal and the raw dumps
    differ -- and buries any genuine structural disagreement in noise.

    Only *docstring* literals are erased. A string the code actually uses (say,
    a returned multi-line literal) keeps its value, because there the
    indentation really is part of the answer.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list):
            for stmt in body:
                if _is_docstring(stmt):
                    stmt.value.value = ""
    return ast.dump(tree)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", default=str(REPO_ROOT / "results"))
    parser.add_argument("--relation", default=None,
                        help="Restrict to one relation (default: every relation)")
    args = parser.parse_args(argv)

    results = Path(args.results)
    rungs: dict[str, Counter] = defaultdict(Counter)
    ambiguous: Counter = Counter()
    module_path: Counter = Counter()

    for task in load_humaneval():
        path = results / "rq2" / "generate" / task_label(task) / "completions.json"
        if not path.exists():
            continue
        recorded = json.loads(path.read_text(encoding="utf-8"))

        for relation, cells in recorded.items():
            if args.relation and relation != args.relation:
                continue
            for model_id, completions in cells.items():
                for raw in completions:
                    body = _extract_function_body(raw, task.entry_point)
                    if _defines_entry_point(body, task.entry_point):
                        module_path[model_id] += 1
                        continue

                    accepted: dict[str, str] = {}
                    fired = None
                    for name, repair in _REPAIR_LADDER:
                        candidate = task.prompt + repair(body)
                        if _assembles_cleanly(candidate, task.entry_point):
                            if fired is None:
                                fired = name
                            try:
                                accepted[name] = _structural_dump(candidate)
                            except (SyntaxError, ValueError):
                                pass
                    rungs[model_id][fired or "unrepaired"] += 1
                    if len({*accepted.values()}) > 1:
                        ambiguous[model_id] += 1

    order = [name for name, _ in _REPAIR_LADDER] + ["unrepaired"]
    print("=" * 78)
    print("Extraction repair ladder -- which rung fires (body-only completions)")
    print("=" * 78)
    header = f"  {'model':32s}" + "".join(f"{n:>12s}" for n in order) + f"{'total':>9s}"
    print(header)
    for model_id in sorted(rungs):
        counts = rungs[model_id]
        total = sum(counts.values())
        row = f"  {model_id:32s}" + "".join(f"{counts[n]:>12d}" for n in order)
        print(row + f"{total:>9d}")

    print()
    print("  repaired = every rung after as-is; these were broken before the fix")
    for model_id in sorted(rungs):
        counts = rungs[model_id]
        repaired = sum(counts[n] for n, _ in _REPAIR_LADDER if n != "as-is")
        broken = repaired + counts["unrepaired"]
        pct = repaired / broken * 100 if broken else 0.0
        print(f"    {model_id:32s} repaired {repaired:5d} of {broken:5d} broken ({pct:.1f}%)"
              f"   [module-path completions: {module_path[model_id]}]")

    print()
    total_ambiguous = sum(ambiguous.values())
    print(f"  AMBIGUOUS (>1 rung assembles, different ASTs): {total_ambiguous}")
    if total_ambiguous:
        for model_id, n in ambiguous.most_common():
            print(f"    ** {model_id}: {n}")
        print("  The ladder is guessing between rival repairs. Investigate before")
        print("  trusting any pass rate computed from it.")
        raise SystemExit(1)
    print("  -> rung order is not deciding any completion's meaning.")


if __name__ == "__main__":
    main()
