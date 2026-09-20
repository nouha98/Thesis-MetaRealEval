#!/usr/bin/env python
"""Verify that results/rq2/generate/*/completions.json matches the response cache.

Why this exists
---------------
`rq2 generate` serves a (relation, model) cell from the on-disk response cache
whenever the request hashes to an entry that is already there.  So a re-run that
is *meant* to touch only one model will silently re-derive every other cell from
the cache.  If the cache and the recorded completions have drifted apart -- a
code change to how prompts are built, a hand-edited results tree, a cache copied
in from another run -- that re-run rewrites data nobody intended to change, and
nothing in the pipeline would report it.

This script recomputes each cell's cache key exactly the way
`InnkubeClient.complete` does and compares the cached ``choices`` against what
`completions.json` actually holds.  Run it before any regeneration.

The retry ladder is reproduced too: `_complete_with_retries` uses the caller's
salt on attempt 1 and ``f"{salt or relation}-retry-{n}"`` afterwards, so a cell
that was filled on a retry hashes to a different key than the first attempt.
A cell is "matched" if ANY attempt's key reproduces it.

Exit code is non-zero when any cell mismatches, so this can gate a re-run.

Usage:
    .venv/Scripts/python.exe scripts/verify_cache_consistency.py
    .venv/Scripts/python.exe scripts/verify_cache_consistency.py --config config/default.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.cache import ResponseCache            # noqa: E402
from meta_real_eval.core.config import Config                  # noqa: E402
from meta_real_eval.core.data_loader import load_humaneval, task_label  # noqa: E402
from meta_real_eval.rq2.generator import (                     # noqa: E402
    MAX_GENERATE_ATTEMPTS,
    _build_messages,
    build_task_variants,
)

# Mirrors the hardcoded budget in rq2/generator.py::_complete_with_retries.
# If that becomes configurable (rq2.max_tokens), read it from cfg instead.
RQ2_MAX_TOKENS = 1024


def candidate_keys(cache, model_id, messages, relation, cache_salt, cfg):
    """Every cache key this cell could legitimately have been stored under."""
    keys = []
    for attempt in range(1, MAX_GENERATE_ATTEMPTS + 1):
        salt = cache_salt if attempt == 1 else f"{cache_salt or relation}-retry-{attempt}"
        keys.append(cache.key(
            model_id, messages,
            temperature=cfg.rq2.temperature,
            max_tokens=RQ2_MAX_TOKENS,
            n=cfg.rq2.n_completions,
            **({} if salt is None else {"cache_salt": salt}),
        ))
    return keys


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(REPO_ROOT / "config" / "default.yaml"))
    parser.add_argument("--results", default=str(REPO_ROOT / "results"))
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    results = Path(args.results)
    cache = ResponseCache(cfg.llm.cache_dir)
    tasks = load_humaneval()

    verdict = Counter()
    mismatches: list[dict] = []
    missing_tasks: list[str] = []

    for task in tasks:
        label = task_label(task)
        path = results / "rq2" / "generate" / label / "completions.json"
        if not path.exists():
            missing_tasks.append(label)
            continue
        recorded = json.loads(path.read_text(encoding="utf-8"))
        variants = build_task_variants(task, cfg)

        for relation, cells in recorded.items():
            variant = variants.get(relation)
            if variant is None:
                verdict["relation absent from current config"] += 1
                continue
            prompt_variant, cache_salt = variant
            messages = _build_messages(prompt_variant)

            for model_id, completions in cells.items():
                keys = candidate_keys(cache, model_id, messages, relation, cache_salt, cfg)
                hits = [cache.get(k) for k in keys]
                hits = [h for h in hits if h is not None]
                if not hits:
                    verdict["not in cache"] += 1
                    continue
                if any(h["choices"] == completions for h in hits):
                    verdict["match"] += 1
                else:
                    verdict["MISMATCH"] += 1
                    mismatches.append({
                        "task": label, "relation": relation, "model": model_id,
                        "n_recorded": len(completions),
                        "n_cached": [len(h["choices"]) for h in hits],
                        "recorded_head": (completions[0][:120] if completions else ""),
                        "cached_head": (hits[0]["choices"][0][:120] if hits[0]["choices"] else ""),
                    })

    print("=" * 74)
    print("RQ2 cache <-> completions.json consistency")
    print("=" * 74)
    for k, v in verdict.most_common():
        print(f"  {k:34s} {v}")
    if missing_tasks:
        print(f"  tasks with no completions.json  : {len(missing_tasks)}")

    # Distinguish "this cache produced these results and has drifted" from
    # "this is simply a different cache". The pipeline runs on the cluster and
    # only results/ is usually copied back, so a local checkout normally has a
    # small unrelated cache from development -- in which case almost everything
    # is absent rather than mismatched, and there is nothing to repair here.
    total = sum(verdict.values())
    absent = verdict["not in cache"]
    if total and absent / total > 0.5:
        print()
        print(f"  NOTE: {absent}/{total} cells are absent from this cache, so it is not the")
        print("        cache that produced these results (the run's cache lives wherever the")
        print("        pipeline executed). The mismatches below are unrelated development")
        print("        calls that happen to hash to the same key -- not corrupted results.")
        print("        Consequence: regenerating HERE would re-call the API for every model,")
        print("        not just the intended one. Use the --only-model merge path, or run")
        print("        the regeneration where the real cache is.")

    if mismatches:
        print(f"\n  {len(mismatches)} MISMATCHED cell(s) -- first 10:")
        for m in mismatches[:10]:
            print(f"    {m['task']:16s} {m['relation']:18s} {m['model']}")
            print(f"        recorded[0]: {m['recorded_head']!r}")
            print(f"        cached[0]  : {m['cached_head']!r}")
        out = Path(args.results) / "cache_consistency_mismatches.json"
        out.write_text(json.dumps(mismatches, indent=2), encoding="utf-8")
        print(f"\n  Full list: {out}")

    print()
    if mismatches:
        print("FAIL - regenerating would rewrite cells that differ from the cache.")
        raise SystemExit(1)
    print("PASS - every cached cell reproduces what is on disk.")


if __name__ == "__main__":
    main()
