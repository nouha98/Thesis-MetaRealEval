#!/usr/bin/env python
"""Build the RQ2 paraphrase corpus: data/paraphrases/humaneval_v1.json.

One-shot, run once on a node with LLM access. Every model under test then reads
the same committed file, so the paraphrases are a fixed property of the
experiment rather than something regenerated per run.

    .venv/bin/python scripts/generate_paraphrases.py --config config/default.yaml
    .venv/bin/python scripts/generate_paraphrases.py --task-range 0-4    # pilot

The run is resumable: generation calls go through the normal ResponseCache, and
``--resume`` (default) keeps tasks already present in the output file. Re-running
after a crash therefore costs only the tasks that had not been written.

When it finishes it prints the SHA-256 of the ``tasks`` block. Paste that into
``rq2.corpus_sha256`` in the config; RQ2's generate phase verifies it and aborts
on a mismatch rather than silently using a different corpus.

Reproducibility note: this procedure is NOT seed-reproducible — InnkubeClient
sends no seed, and an OpenAI-compatible vLLM gateway treats one as best-effort
anyway. What is reproducible is the artifact: the committed JSON plus its hash.
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
    CORPUS_VERSION,
    FAMILIES,
    GENERATION_MAX_TOKENS,
    GENERATION_TEMPERATURE,
    MIN_FAMILIES_COVERED,
    N_PER_FAMILY,
    PROMPT_TEMPLATE_VERSION,
    generate_task_variants,
    tasks_sha256,
)

logger = logging.getLogger(__name__)

DEFAULT_OUT = REPO_ROOT / "data" / "paraphrases" / "humaneval_v1.json"


def _parse_task_range(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(x) for x in spec.split(",")]


def _resolve_models(cfg: Config, args) -> tuple[str, str]:
    """Return (generator_model, judge_model), refusing any model under test.

    A generator or judge drawn from ``llm.models`` would make the corpus a
    function of one of the systems being compared: the judge would be filtering
    on the dependent variable, and the generator would hand its own model
    prompts it is unusually well-tuned to. Both are hard errors, not warnings.
    """
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
            "The corpus must be held out from the models being ranked, or RQ2 "
            "filters on its own dependent variable."
        )
    return generator, judge


async def build(cfg: Config, tasks, generator_model: str, judge_model: str,
                out_path: Path, n_per_family: int, resume: bool) -> dict:
    cache = ResponseCache(cfg.llm.cache_dir)
    client = InnkubeClient(cfg.llm, cache, mock=cfg.project.mock)

    existing: dict = {}
    if resume and out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8")).get("tasks", {})
        logger.info("Resuming: %d task(s) already in %s", len(existing), out_path)

    corpus_tasks: dict = dict(existing)
    gaps: list[dict] = []
    rejections: list[dict] = []

    # Sequential across tasks: each task is already several concurrent-ish LLM
    # calls behind the client's rate limiter, and a partial file after a crash is
    # worth more than a marginally faster run.
    for i, task in enumerate(tasks, start=1):
        if task.task_id in corpus_tasks:
            continue
        entry, task_gaps, task_rejections = await generate_task_variants(
            task, generator_model, judge_model, client, n_per_family=n_per_family,
        )
        corpus_tasks[task.task_id] = entry
        gaps.extend(task_gaps)
        rejections.extend(task_rejections)
        logger.info("[%d/%d] %s: %d/%d variants",
                    i, len(tasks), task.task_id, len(entry["variants"]),
                    len(FAMILIES) * n_per_family)
        _write(out_path, corpus_tasks, generator_model, judge_model,
               n_per_family, cfg)

    _write_sidecars(out_path, gaps, rejections)
    return _write(out_path, corpus_tasks, generator_model, judge_model,
                  n_per_family, cfg)


def _coverage_block(corpus_tasks: dict, n_per_family: int) -> dict:
    """Per-family fill counts and MIN_FAMILIES_COVERED pass/fail, as a manifest field.

    Coverage is a property of the committed artifact, not something every
    reader has to recompute from generation_gaps.json -- scripts/analyze_results.py
    still recomputes it independently from rankings.json (the "recomputed here
    rather than trusted" discipline the rest of that file already follows), but
    this block is what `scripts/paraphrase_report.py` and a human skimming the
    corpus file see without cross-referencing a sidecar.
    """
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
        "per_family_tasks_filled": per_family_filled,   # tasks with >=1 variant in that family
        "per_family_expected": n_tasks,
        "per_family_slots_filled": {
            fam: sum(1 for e in corpus_tasks.values()
                     for v in e["variants"] if v["family"] == fam)
            for fam in FAMILIES
        },
        "per_family_slots_expected": n_tasks * n_per_family,
    }


def _write(out_path: Path, corpus_tasks: dict, generator_model: str,
           judge_model: str, n_per_family: int, cfg: Config) -> dict:
    corpus = {
        "manifest": {
            "corpus_version": CORPUS_VERSION,
            "generator_model": generator_model,
            "judge_model": judge_model,
            "temperature": GENERATION_TEMPERATURE,
            "max_tokens": GENERATION_MAX_TOKENS,
            "prompt_template_version": PROMPT_TEMPLATE_VERSION,
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_tasks": len(corpus_tasks),
            "families": FAMILIES,
            "n_per_family": n_per_family,
            "mock": cfg.project.mock,
            "coverage": _coverage_block(corpus_tasks, n_per_family),
        },
        "tasks": corpus_tasks,
    }
    corpus["manifest"]["sha256"] = tasks_sha256(corpus)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out_path)
    return corpus


def _write_sidecars(out_path: Path, gaps: list[dict], rejections: list[dict]) -> None:
    """Persist unfilled slots and every rejection, so both are reportable.

    Gaps are left as gaps in the corpus itself — a task short of a family simply
    has fewer variants. Recording them here is what makes the shortfall auditable
    instead of invisible.
    """
    if gaps:
        (out_path.parent / "generation_gaps.json").write_text(
            json.dumps(gaps, indent=2), encoding="utf-8")
    (out_path.parent / "generation_rejections.json").write_text(
        json.dumps(rejections, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv=None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Build the RQ2 paraphrase corpus")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--task-range", default=None,
                        help="e.g. 0-4 or 0,1,10 (default: all 164)")
    parser.add_argument("--n-per-family", type=int, default=N_PER_FAMILY)
    parser.add_argument("--generator-model", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--no-resume", action="store_true",
                        help="regenerate every task, ignoring tasks already in --out")
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    setup_logging("rq2", "paraphrase-corpus", log_dir=REPO_ROOT / "logs")
    generator_model, judge_model = _resolve_models(cfg, args)

    tasks = load_humaneval(tasks=_parse_task_range(args.task_range))
    logger.info("Generating paraphrases for %d task(s): generator=%s judge=%s%s",
                len(tasks), generator_model, judge_model,
                " [MOCK]" if cfg.project.mock else "")

    corpus = asyncio.run(build(cfg, tasks, generator_model, judge_model,
                               args.out, args.n_per_family, not args.no_resume))

    filled = sum(len(t["variants"]) for t in corpus["tasks"].values())
    expected = len(corpus["tasks"]) * len(FAMILIES) * args.n_per_family
    cov = corpus["manifest"]["coverage"]
    print(f"\nWrote {args.out}")
    print(f"  tasks     : {len(corpus['tasks'])}")
    print(f"  variants  : {filled}/{expected} slots filled")
    print(f"  coverage  : {cov['n_tasks_meeting_threshold']}/{cov['n_tasks_total']} tasks "
          f"meet >= {MIN_FAMILIES_COVERED}/{len(FAMILIES)} families "
          "(rq2.corpus.MIN_FAMILIES_COVERED)")
    for fam in FAMILIES:
        print(f"    {fam:10s} {cov['per_family_tasks_filled'][fam]:3d}/{cov['per_family_expected']} "
              f"tasks have >=1 variant")
    print(f"  sha256    : {corpus['manifest']['sha256']}")
    try:
        shown = "./" + args.out.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        shown = args.out.as_posix()      # --out pointed outside the repo
    print("\nPin it in the config:")
    print(f"  rq2.paraphrase_corpus: {shown}")
    print(f"  rq2.corpus_sha256: \"{corpus['manifest']['sha256']}\"")


if __name__ == "__main__":
    main()
