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
from ..core.config import Config
from ..core.data_loader import HumanEvalTask, task_label
from ..core.llm_client import InnkubeClient
from .paraphraser import apply_all_relations

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


async def _complete_with_retries(
    task, relation: str, model_id: str, messages: list[dict],
    cfg: Config, client: InnkubeClient,
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

    variants = apply_all_relations(task.prompt, cfg.rq2.relations)
    results: dict[str, dict[str, list[str]]] = {}
    empty_cells: list[dict] = []

    for relation, prompt_variant in variants.items():
        results[relation] = {}
        messages = _build_messages(prompt_variant)

        for model_cfg in cfg.llm.models:
            model_id = model_cfg.id
            completions, error = await _complete_with_retries(
                task, relation, model_id, messages, cfg, client
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
            label, len(empty_cells), len(cfg.rq2.relations) * len(cfg.llm.models),
            ", ".join(f"{c['relation']}/{c['model_id']}" for c in empty_cells),
        )
        return

    (out / "generation_failed.json").unlink(missing_ok=True)
    mark_done(out)
    logger.info("Generated completions for %s", label)


async def run_generate(cfg: Config, tasks: list[HumanEvalTask], force: bool = False) -> None:
    """Dispatch all tasks concurrently (semaphore + rate limiter handle throttling)."""
    cache = ResponseCache(cfg.llm.cache_dir)
    client = InnkubeClient(cfg.llm, cache, mock=cfg.project.mock)
    coros = [generate_task(t, cfg, client, force=force) for t in tasks]
    await asyncio.gather(*coros)
