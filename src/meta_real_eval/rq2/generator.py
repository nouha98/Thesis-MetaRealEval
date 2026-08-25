"""RQ2 generate phase: fetch n completions per (task, relation, model) triple.

All responses are stored in the disk cache by the InnkubeClient.  The
per-task checkpoint (_done.marker) is written only after all (relation,
model) combinations for that task are complete, so a crash mid-task will
re-run the task — but cached API responses mean only the uncached calls
are actually made.

A (relation, model) cell that comes back empty is a *hole in the design*, not a
score: pass@1 over zero samples is 0.0, which is indistinguishable from a model
that answered every prompt wrongly, and RQ2 exists to rank models against each
other.  An empty cell is therefore retried, then recorded in
generation_failed.json and left without a _done.marker so the task is picked up
again, rather than silently entering the leaderboard as a zero.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ..core.cache import ResponseCache
from ..core.checkpoint import clear_done, is_done, mark_done, task_dir, write_json
from ..core.config import BASELINE_RELATION, CONTROL_RELATION, Config
from ..core.data_loader import HumanEvalTask, task_label
from ..core.llm_client import InnkubeClient
from .corpus import load_corpus, variants_for_task, verify_corpus
from .paraphraser import apply_relation

logger = logging.getLogger(__name__)

# Mirrors rq1.runner: a live model can return nothing on one call and succeed on
# a resample. Transient HTTP failures are already retried inside InnkubeClient;
# this is the coarser retry around a whole (relation, model) cell.
MAX_GENERATE_ATTEMPTS = 3
GENERATE_RETRY_DELAY_S = 1.0

_SYSTEM_PROMPT = (
    "You are a Python programming assistant. "
    "Complete the Python function exactly as specified. "
    "Return only the function body (indented implementation), "
    "no markdown fences, no explanation."
)


def _build_messages(prompt_variant: str) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": prompt_variant},
    ]


def build_task_variants(task: HumanEvalTask, cfg: Config) -> dict[str, tuple[str, str | None]]:
    """Return ``{relation: (prompt_text, cache_salt)}`` for one task.

    Three arms share one flat relation namespace, because every downstream
    reader (completions.json, pass_rates.json, rankings.json, RQ3, RQ4) keys on
    an opaque relation string:

    ``original``          the unmodified prompt.
    ``control_resample``  the unmodified prompt again, under a cache salt so it
                          is genuinely re-sampled rather than served from the
                          cache — its tau_b is the sampling-noise floor.
    template relations    the deterministic transforms (control arm).
    ``llm_<family>_NN``   the validated LLM rewrites from the corpus.

    A corpus variant that a task lacks (its family could not be filled during
    generation) is simply absent from the returned mapping.  It is not padded
    with a template: ``rq2/ranking.py`` already treats an absent relation as
    missing data, and padding would reintroduce exactly the tautological cells
    the corpus exists to remove.
    """
    variants: dict[str, tuple[str, str | None]] = {BASELINE_RELATION: (task.prompt, None)}

    if cfg.rq2.include_control_resample:
        variants[CONTROL_RELATION] = (task.prompt, CONTROL_RELATION)

    for relation in cfg.rq2.template_relations:
        variants[relation] = (apply_relation(task.prompt, relation), None)

    if cfg.rq2.paraphrase_corpus is not None:
        corpus = load_corpus(cfg.rq2.paraphrase_corpus)
        for variant_id, text in variants_for_task(corpus, task.task_id).items():
            variants[variant_id] = (text, None)

    return variants


async def _complete_with_retries(
    task, relation: str, model_id: str, messages: list[dict],
    cfg: Config, client: InnkubeClient, cache_salt: str | None = None,
) -> tuple[list[str], str | None]:
    """Fetch one (relation, model) cell, retrying while it comes back empty."""
    last_error: str | None = None
    for attempt in range(1, MAX_GENERATE_ATTEMPTS + 1):
        try:
            completions = await client.complete(
                model=model_id,
                messages=messages,
                temperature=cfg.rq2.temperature,
                max_tokens=1024,
                n=cfg.rq2.n_completions,
                cache_salt=cache_salt,
            )
        except Exception as exc:
            completions = []
            last_error = f"{type(exc).__name__}: {exc}"

        if completions:
            return completions, None

        last_error = last_error or "model returned zero completions"
        logger.warning("Empty cell %s / %s / %s (attempt %d/%d): %s",
                       task_label(task), relation, model_id,
                       attempt, MAX_GENERATE_ATTEMPTS, last_error)
        if attempt < MAX_GENERATE_ATTEMPTS:
            await asyncio.sleep(GENERATE_RETRY_DELAY_S)

    return [], last_error


async def generate_task(
    task: HumanEvalTask,
    cfg: Config,
    client: InnkubeClient,
    force: bool = False,
) -> None:
    """Generate completions for one task across all (relation, model) combos."""
    label = task_label(task)
    out = task_dir(cfg, "rq2", label, phase="generate")

    if force:
        clear_done(out)

    if is_done(out):
        logger.info("SKIP generate %s", label)
        return

    variants = build_task_variants(task, cfg)
    results: dict[str, dict[str, list[str]]] = {}
    empty_cells: list[dict] = []

    missing = [r for r in cfg.rq2.relations if r not in variants]
    if missing:
        # A generation gap in the corpus, already recorded when it was built.
        # Logged per task so the shortfall is visible in the run log too.
        logger.warning("%s: %d corpus variant(s) absent (%s) — cells left missing, not padded",
                       label, len(missing), ", ".join(missing))

    for relation, (prompt_variant, cache_salt) in variants.items():
        results[relation] = {}
        messages = _build_messages(prompt_variant)

        for model_cfg in cfg.llm.models:
            model_id = model_cfg.id
            completions, error = await _complete_with_retries(
                task, relation, model_id, messages, cfg, client, cache_salt=cache_salt
            )
            if not completions:
                empty_cells.append({"relation": relation, "model_id": model_id,
                                    "attempts": MAX_GENERATE_ATTEMPTS,
                                    "last_error": error})

            results[relation][model_id] = completions
            logger.debug("  %s / %s / %s → %d completions",
                         label, relation, model_id, len(completions))

    # Partial output is still written — it is real data and the cache means a
    # re-run is cheap — but the task stays unmarked so it gets retried.
    write_json(out, "completions.json", results)

    if empty_cells:
        write_json(out, "generation_failed.json", {
            "task_id": task.task_id,
            "task_label": label,
            "empty_cells": empty_cells,
        })
        logger.error(
            "Generation incomplete for %s: %d/%d (relation, model) cell(s) empty "
            "(%s) — NOT marking done; re-run to retry. Evaluating this task now "
            "would score those models 0.0 for an infrastructure failure.",
            label, len(empty_cells), len(variants) * len(cfg.llm.models),
            ", ".join(f"{c['relation']}/{c['model_id']}" for c in empty_cells),
        )
        return

    (out / "generation_failed.json").unlink(missing_ok=True)
    mark_done(out)
    logger.info("Generated completions for %s", label)


async def run_generate(cfg: Config, tasks: list[HumanEvalTask], force: bool = False) -> None:
    """Dispatch all tasks concurrently (semaphore + rate limiter handle throttling)."""
    if cfg.rq2.paraphrase_corpus is not None:
        # Verified once, up front, before any budget is spent: a corpus that
        # drifted since the pinned hash would give different models different
        # prompts, which makes their pass rates incomparable — the exact confound
        # the committed corpus exists to prevent. Abort, never regenerate.
        corpus = load_corpus(cfg.rq2.paraphrase_corpus)
        verify_corpus(corpus, cfg.rq2.corpus_sha256, cfg.rq2.paraphrase_corpus)
        logger.info("Paraphrase corpus %s: %d tasks, %d variant slots",
                    cfg.rq2.paraphrase_corpus, len(corpus["tasks"]),
                    len(cfg.rq2.relations))

    cache = ResponseCache(cfg.llm.cache_dir)
    client = InnkubeClient(cfg.llm, cache, mock=cfg.project.mock)
    coros = [generate_task(t, cfg, client, force=force) for t in tasks]
    await asyncio.gather(*coros)
