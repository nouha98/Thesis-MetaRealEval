"""Dump the cached raw completions behind a generation_failed.json entry.

RQ1's generate phase only records *that* a model produced zero usable mutants,
not what it actually said. The responses are still on disk in the LLM response
cache, but that cache is content-addressed (sha256 of the request), so there is
no way to grep it by task id. This script rebuilds the exact cache keys the
generate phase used -- importing the real prompt builders and the real
ResponseCache.key, so the reconstruction cannot drift from what ran -- and
replays each completion through the real _extract_code to show which gate
rejected it.

Usage (from the repo root, where ./cache lives):
    python scripts/diagnose_generation_failures.py
    python scripts/diagnose_generation_failures.py --tasks 69 92 --full
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.config import Config
from meta_real_eval.core.data_loader import load_humaneval
from meta_real_eval.rq1.llm_mutator import (
    _SYSTEM_PROMPT,
    _build_user_message,
    _extract_code,
)
from meta_real_eval.rq1.runner import MAX_GENERATE_ATTEMPTS

# Mirrors the call in llm_mutator.generate_llm_mutants. Kept as named constants
# so a drift between this script and the real call site is obvious rather than
# silently producing cache misses that look like "no data".
N_MUTANTS = 3
TEMPERATURE = 0.9
MAX_TOKENS = 1024


def find_failed_pairs(results_dir: Path) -> list[tuple[str, str]]:
    """Read every generation_failed.json into (task_label, model_id) pairs."""
    pairs = []
    for path in sorted(results_dir.glob("*/generation_failed.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        for failure in record.get("failed_models", []):
            pairs.append((path.parent.name, failure["model_id"]))
    return pairs


def diagnose(task, model_id: str, cache: ResponseCache, full: bool) -> None:
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(task)},
    ]
    canonical = (task.prompt + task.canonical_solution).strip()

    print("=" * 78)
    print(f"{task.task_id}   model={model_id}")
    print("=" * 78)

    found_any = False
    # Attempt 1 of a pre-fix run had no salt at all; later runs salt every
    # attempt. Try both so old and new cache entries are both visible.
    salts = [None] + [f"llm-mutant-attempt-{i}" for i in range(1, MAX_GENERATE_ATTEMPTS + 1)]

    for salt in salts:
        params = {
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "n": N_MUTANTS + 2,
        }
        if salt is not None:
            params["cache_salt"] = salt

        entry = cache.get(cache.key(model_id, messages, **params))
        if entry is None:
            continue
        found_any = True
        print(f"\n--- cache entry: salt={salt!r} ---")

        for idx, raw in enumerate(entry["choices"]):
            code = _extract_code(raw, task.prompt)
            if code is None:
                try:
                    ast.parse(raw.strip())
                    verdict = "REJECTED unparseable (fence-strip left invalid code)"
                except SyntaxError as exc:
                    verdict = f"REJECTED unparseable (SyntaxError: {exc.msg} @ line {exc.lineno})"
            elif code.strip() == canonical:
                verdict = "REJECTED identical to canonical solution"
            else:
                verdict = "ACCEPTED"

            stripped = raw.strip()
            print(f"  [{idx}] len={len(raw):5d}  {verdict}")
            if not stripped:
                print("       <empty string>")
            elif full:
                print("       " + "\n       ".join(stripped.splitlines()))
            else:
                head = stripped.splitlines()[:6]
                for line in head:
                    print(f"       | {line[:110]}")
                if len(stripped.splitlines()) > 6:
                    print(f"       | ... ({len(stripped.splitlines()) - 6} more lines)")

    if not found_any:
        print("\n  No cache entries found for this pair.")
        print("  (The cache lives at the configured llm.cache_dir, relative to the")
        print("   directory you run from -- run this from the same repo root the job did.)")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--tasks", type=int, nargs="*", default=None,
                        help="Task indices to inspect (default: every task with a "
                             "generation_failed.json)")
    parser.add_argument("--full", action="store_true",
                        help="Print each completion in full instead of the first 6 lines")
    args = parser.parse_args()

    cfg = Config.from_yaml(args.config)
    cache = ResponseCache(cfg.llm.cache_dir)
    generate_dir = Path(cfg.project.output_dir) / "rq1" / "generate"

    pairs = find_failed_pairs(generate_dir)
    if not pairs:
        print(f"No generation_failed.json found under {generate_dir}")
        return

    if args.tasks is not None:
        wanted = {f"HumanEval_{i}" for i in args.tasks}
        pairs = [p for p in pairs if p[0] in wanted]

    by_label = {f"HumanEval_{t.task_index}": t for t in load_humaneval()}
    print(f"Inspecting {len(pairs)} failed (task, model) pair(s) "
          f"from {generate_dir}\ncache: {cfg.llm.cache_dir}\n")

    for label, model_id in pairs:
        task = by_label.get(label)
        if task is None:
            print(f"!! {label}: not present in the loaded corpus, skipping\n")
            continue
        diagnose(task, model_id, cache, args.full)


if __name__ == "__main__":
    main()
