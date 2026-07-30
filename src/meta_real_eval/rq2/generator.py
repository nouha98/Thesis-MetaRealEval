"""RQ2 generate phase: fetch n completions per (task, relation, model) triple.

All responses are stored in the disk cache by the InnkubeClient.  The
per-task checkpoint (_done.marker) is written only after all (relation,
model) combinations for that task are complete, so a crash mid-task will
re-run the task — but cached API responses mean only the uncached calls
are actually made.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ..core.cache import ResponseCache
from ..core.checkpoint import is_done, mark_done, task_dir, write_json
from ..core.config import Config
from ..core.data_loader import HumanEvalTask, task_label
from ..core.llm_client import InnkubeClient
from .paraphraser import apply_all_relations

logger = logging.getLogger(__name__)

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


async def generate_task(
    task: HumanEvalTask,
    cfg: Config,
    client: InnkubeClient,
) -> None:
    """Generate completions for one task across all (relation, model) combos."""
    label = task_label(task)
    out = task_dir(cfg, "rq2", label, phase="generate")

    if is_done(out):
        logger.info("SKIP generate %s", label)
        return

    variants = apply_all_relations(task.prompt, cfg.rq2.relations)
    results: dict[str, dict[str, list[str]]] = {}

    for relation, prompt_variant in variants.items():
        results[relation] = {}
        messages = _build_messages(prompt_variant)

        for model_cfg in cfg.llm.models:
            model_id = model_cfg.id
            try:
                completions = await client.complete(
                    model=model_id,
                    messages=messages,
                    temperature=cfg.rq2.temperature,
                    max_tokens=1024,
                    n=cfg.rq2.n_completions,
                )
            except Exception as exc:
                logger.warning(
                    "FAILED %s / %s / %s: %s", label, relation, model_id, exc
                )
                completions = []

            results[relation][model_id] = completions
            logger.debug("  %s / %s / %s → %d completions",
                         label, relation, model_id, len(completions))

    write_json(out, "completions.json", results)
    mark_done(out)
    logger.info("Generated completions for %s", label)


async def run_generate(cfg: Config, tasks: list[HumanEvalTask]) -> None:
    """Dispatch all tasks concurrently (semaphore + rate limiter handle throttling)."""
    cache = ResponseCache(cfg.llm.cache_dir)
    client = InnkubeClient(cfg.llm, cache, mock=cfg.project.mock)
    coros = [generate_task(t, cfg, client) for t in tasks]
    await asyncio.gather(*coros)
