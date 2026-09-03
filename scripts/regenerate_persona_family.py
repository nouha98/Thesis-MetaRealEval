#!/usr/bin/env python
"""Regenerate only the persona family of the RQ2 paraphrase corpus.

Scoped fix for a Gate A bug (see rq2/corpus.py's `empty_docstring_body` check,
tests/test_rq2/test_corpus.py's persona regression tests, and
data/paraphrases/review_sheet.md's reviewer note): before the fix, when a
persona response never separated its framing paragraph from the rewritten
docstring (the ``---BODY---`` sentinel was missing), the entire response
landed as framing and the docstring came out blank -- the specification sits
as prose before ``def`` instead of inside the function. The old Gate A only
checked whether the *whole* candidate string was blank, not the docstring
itself, so this slipped through undetected.

Every OTHER family (lexical, reorder, formal, terse) is untouched by this
script and by the Gate A fix -- only persona could have a non-empty preamble
in the first place, which is what made the bug reachable there and nowhere
else.

Cost discipline: each task's EXISTING persona variants are individually
re-checked against the fixed gate. A variant that still passes is KEPT, not
discarded -- only the shortfall (however many of the 3 slots no longer pass,
or were never filled) is freshly generated. A task where all 3 already pass
costs nothing. This matters in practice: spot-checking earlier suggested most
tasks were either "fine" or "broken", but re-checking every slot shows most
affected tasks are a MIX -- e.g. HumanEval/111 has one good persona variant
and two bad ones, not three bad ones.

Usage:
    .venv/bin/python scripts/regenerate_persona_family.py --dry-run   # report only, no LLM calls
    .venv/bin/python scripts/regenerate_persona_family.py             # apply
    .venv/bin/python scripts/regenerate_persona_family.py --corpus data/paraphrases/humaneval_v1.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.cache import ResponseCache            # noqa: E402
from meta_real_eval.core.config import Config                  # noqa: E402
from meta_real_eval.core.data_loader import load_humaneval     # noqa: E402
from meta_real_eval.core.llm_client import InnkubeClient       # noqa: E402
from meta_real_eval.core.logging_setup import setup as setup_logging  # noqa: E402
from meta_real_eval.rq2.corpus import (                        # noqa: E402
    FAMILIES,
    MIN_FAMILIES_COVERED,
    N_PER_FAMILY,
    _normalize,
    generate_family,
    structural_gate,
    tasks_sha256,
    variant_id,
)

logger = logging.getLogger(__name__)

DEFAULT_CORPUS = REPO_ROOT / "data" / "paraphrases" / "humaneval_v1.json"
FAMILY = "persona"


def _resolve_models(cfg: Config, args) -> tuple[str, str]:
    """Same held-out check as generate_paraphrases.py -- deliberately duplicated
    rather than imported, so this script has no import-time dependency on that
    one beyond the already-shared rq2.corpus module."""
    generator = args.generator_model or cfg.rq2.generator_model
    judge = args.judge_model or cfg.rq2.judge_model
    if not generator or not judge:
        raise SystemExit(
            "Set rq2.generator_model and rq2.judge_model in the config (or pass "
            "--generator-model/--judge-model). Both must be models that are NOT "
            "in llm.models."
        )
    under_test = set(cfg.model_ids())
    clash = under_test & {generator, judge}
    if clash:
        raise SystemExit(
            f"generator/judge model(s) {sorted(clash)} are also in llm.models. "
            "The corpus must be held out from the models being ranked."
        )
    return generator, judge


def _surviving_persona_variants(original: str, entry_point: str, variants: list[dict]) -> list[dict]:
    """This task's existing persona variants that still pass the fixed gate.

    Re-runs the FIXED structural_gate against each already-accepted candidate's
    own text. `seen` is passed empty deliberately: sibling-duplication is not
    the question here, only "does the docstring body still hold real content".
    """
    return [
        v for v in variants
        if v["family"] == FAMILY
        and structural_gate(original, v["text"], entry_point, FAMILY, seen=set()) is None
    ]


def _coverage_block(corpus_tasks: dict, n_per_family: int) -> dict:
    """Mirrors generate_paraphrases.py's _coverage_block exactly."""
    per_family_filled = {fam: 0 for fam in FAMILIES}
    n_meeting_threshold = 0
    for entry in corpus_tasks.values():
        families_here = {v["family"] for v in entry["variants"]}
        for fam in families_here:
            per_family_filled[fam] += 1
        if len(families_here) >= MIN_FAMILIES_COVERED:
            n_meeting_threshold += 1

    n_tasks = len(corpus_tasks)
    return {
        "min_families_covered": MIN_FAMILIES_COVERED,
        "n_tasks_meeting_threshold": n_meeting_threshold,
        "n_tasks_total": n_tasks,
        "per_family_tasks_filled": per_family_filled,
        "per_family_expected": n_tasks,
        "per_family_slots_filled": {
            fam: sum(1 for e in corpus_tasks.values()
                     for v in e["variants"] if v["family"] == fam)
            for fam in FAMILIES
        },
        "per_family_slots_expected": n_tasks * n_per_family,
    }


async def main_async(args) -> None:
    load_dotenv()
    cfg = Config.from_yaml(args.config)
    generator_model, judge_model = _resolve_models(cfg, args)

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    n_per_family = corpus["manifest"].get("n_per_family", N_PER_FAMILY)
    corpus_tasks: dict = corpus["tasks"]

    tasks_by_id = {t.task_id: t for t in load_humaneval()}

    # task_id -> surviving (kept) persona variants, for every task with a
    # shortfall (some variant no longer passes, or the slot was never filled).
    to_regenerate: dict[str, list[dict]] = {}
    for task_id, entry in corpus_tasks.items():
        if task_id not in tasks_by_id:
            continue
        task = tasks_by_id[task_id]
        surviving = _surviving_persona_variants(entry["original"], task.entry_point,
                                                 entry["variants"])
        if len(surviving) < n_per_family:
            to_regenerate[task_id] = surviving

    n_slots_needed = sum(n_per_family - len(s) for s in to_regenerate.values())
    logger.info("%d/%d tasks have a persona shortfall; %d slot(s) to fill",
                len(to_regenerate), len(corpus_tasks), n_slots_needed)

    if args.dry_run:
        for task_id, surviving in to_regenerate.items():
            print(f"{task_id}: keep {len(surviving)}, generate {n_per_family - len(surviving)}")
        print(f"\n{len(to_regenerate)}/{len(corpus_tasks)} tasks affected, "
              f"{n_slots_needed} new completions needed in total "
              f"(vs {len(to_regenerate) * n_per_family} if regenerated from scratch). "
              "No LLM calls made (--dry-run).")
        return

    cache = ResponseCache(cfg.llm.cache_dir)
    client = InnkubeClient(cfg.llm, cache, mock=cfg.project.mock)

    gaps_path = args.corpus.parent / "generation_gaps.json"
    rejections_path = args.corpus.parent / "generation_rejections.json"
    existing_gaps = json.loads(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else []
    existing_rejections = (
        json.loads(rejections_path.read_text(encoding="utf-8")) if rejections_path.exists() else []
    )
    # Drop stale persona records for tasks we're about to redo; every OTHER
    # family's records, and persona records for tasks NOT being touched,
    # are left exactly as they were.
    touched = set(to_regenerate)
    gaps = [g for g in existing_gaps if not (g["family"] == FAMILY and g["task_id"] in touched)]
    rejections = [r for r in existing_rejections
                  if not (r["family"] == FAMILY and r["task_id"] in touched)]

    for i, (task_id, surviving) in enumerate(to_regenerate.items(), start=1):
        task = tasks_by_id[task_id]
        entry = corpus_tasks[task_id]
        n_needed = n_per_family - len(surviving)

        non_persona = [v for v in entry["variants"] if v["family"] != FAMILY]
        seen = {_normalize(v["text"]) for v in non_persona}
        seen |= {_normalize(v["text"]) for v in surviving}

        accepted, rejected = await generate_family(
            task, FAMILY, generator_model, judge_model, client,
            n_per_family=n_needed, seen=seen,
        )
        # Renumber uniformly (kept variants first, in their existing order,
        # then freshly accepted ones) so ids stay a clean 01..n_per_family
        # sequence with no collisions between "kept" and "new" ids.
        combined_persona = []
        for idx, v in enumerate(surviving + accepted, start=1):
            v = {**v, "variant_id": variant_id(FAMILY, idx)}
            combined_persona.append(v)

        entry["variants"] = non_persona + combined_persona
        rejections.extend({**r, "task_id": task.task_id} for r in rejected)
        if len(combined_persona) < n_per_family:
            gaps.append({"task_id": task.task_id, "family": FAMILY,
                         "filled": len(combined_persona), "requested": n_per_family})

        logger.info("[%d/%d] %s: kept %d, generated %d, now %d/%d persona variants",
                    i, len(to_regenerate), task_id, len(surviving), len(accepted),
                    len(combined_persona), n_per_family)

        # Written after every task, same as generate_paraphrases.py's build():
        # a partial file after a crash is worth more than a marginally faster run.
        corpus["manifest"]["generated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        corpus["manifest"]["coverage"] = _coverage_block(corpus_tasks, n_per_family)
        corpus["manifest"]["sha256"] = tasks_sha256(corpus)
        tmp = args.corpus.with_suffix(".tmp")
        tmp.write_text(json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(args.corpus)

    if gaps:
        gaps_path.write_text(json.dumps(gaps, indent=2), encoding="utf-8")
    elif gaps_path.exists():
        gaps_path.unlink()
    rejections_path.write_text(json.dumps(rejections, indent=2, ensure_ascii=False), encoding="utf-8")

    filled = sum(len(t["variants"]) for t in corpus_tasks.values())
    expected = len(corpus_tasks) * len(FAMILIES) * n_per_family
    cov = corpus["manifest"]["coverage"]
    print(f"\nRewrote {args.corpus}")
    print(f"  persona tasks touched : {len(to_regenerate)}/{len(corpus_tasks)}")
    print(f"  variants  : {filled}/{expected} slots filled (all families)")
    print(f"  coverage  : {cov['n_tasks_meeting_threshold']}/{cov['n_tasks_total']} tasks "
          f"meet >= {MIN_FAMILIES_COVERED}/{len(FAMILIES)} families")
    for fam in FAMILIES:
        print(f"    {fam:10s} {cov['per_family_tasks_filled'][fam]:3d}/{cov['per_family_expected']} "
              f"tasks have >=1 variant")
    print(f"  sha256    : {corpus['manifest']['sha256']}")
    print("\nPin it in the config (this WILL have changed from the old value):")
    print(f"  rq2.corpus_sha256: \"{corpus['manifest']['sha256']}\"")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--generator-model", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="List which tasks would be regenerated; make no LLM calls")
    args = parser.parse_args(argv)

    setup_logging("rq2", "regenerate-persona", log_dir=REPO_ROOT / "logs")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
