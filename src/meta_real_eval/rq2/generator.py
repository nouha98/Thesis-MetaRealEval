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
import json
import logging
from pathlib import Path

from ..core.cache import ResponseCache
from ..core.checkpoint import clear_done, is_done, mark_done, read_json, task_dir, write_json
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


def _has_real_completion(completions: list[str], finish_reasons: list[str] | None = None) -> bool:
    """True if this cell holds at least one genuine, complete answer.

    A non-empty list of blank strings is not a success: a model that routes
    its answer to a field this client doesn't read (or that exhausts its
    token budget before emitting one) returns exactly that, and a bare
    `if completions:` would accept it as n genuine samples instead of
    retrying -- recording a real pass@1 of 0.0 for a cell that never
    actually got a completion.

    ``finish_reasons`` extends the same principle to *truncation*. A completion
    cut off at the token cap is non-empty but unfinished, so the emptiness check
    alone waves it through and the leaderboard reads a budget shortfall as the
    model getting the answer wrong. A cell where every completion hit the cap
    is an infrastructure failure and is retried; a cell where only some did
    still carries real answers and is kept.
    """
    if not any(c.strip() for c in completions):
        return False
    if finish_reasons and all(r == "length" for r in finish_reasons):
        return False
    return True


async def _complete_with_retries(
    task, relation: str, model_id: str, messages: list[dict],
    cfg: Config, client: InnkubeClient, cache_salt: str | None = None,
) -> tuple[list[str], str | None]:
    """Fetch one (relation, model) cell, retrying while it comes back empty.

    The attempt number is folded into every request's cache salt. Without it,
    a blank first attempt gets cached under the same key `cache_salt` alone
    would produce, and every "retry" is really just client.complete() serving
    that cached blank result back -- confirmed empirically: with a fixed
    salt, 3 configured attempts made exactly 1 real API call. Only the first
    attempt keeps the caller's own `cache_salt` unmodified, so a relation with
    no salt of its own (most of them -- see build_task_variants) still gets
    its ordinary, cacheable request on attempt 1; only a genuine retry adds
    the per-attempt suffix.
    """
    last_error: str | None = None
    for attempt in range(1, MAX_GENERATE_ATTEMPTS + 1):
        attempt_salt = cache_salt if attempt == 1 else f"{cache_salt or relation}-retry-{attempt}"
        finish_reasons: list[str] = []
        try:
            completions, finish_reasons = await client.complete_with_meta(
                model=model_id,
                messages=messages,
                temperature=cfg.rq2.temperature,
                max_tokens=cfg.rq2.max_tokens,
                n=cfg.rq2.n_completions,
                cache_salt=attempt_salt,
            )
        except Exception as exc:
            completions = []
            last_error = f"{type(exc).__name__}: {exc}"

        if _has_real_completion(completions, finish_reasons):
            return completions, None

        if completions and finish_reasons and all(r == "length" for r in finish_reasons):
            last_error = (f"every completion truncated at the {cfg.rq2.max_tokens}-token cap "
                          "(finish_reason=length)")
        last_error = last_error or "model returned zero completions"
        logger.warning("Empty cell %s / %s / %s (attempt %d/%d): %s",
                       task_label(task), relation, model_id,
                       attempt, MAX_GENERATE_ATTEMPTS, last_error)
        if attempt < MAX_GENERATE_ATTEMPTS:
            await asyncio.sleep(GENERATE_RETRY_DELAY_S)

    return [], last_error


def _existing_completions(out) -> dict[str, dict[str, list[str]]]:
    """Whatever completions.json already holds, or {} if there is none."""
    try:
        return read_json(out, "completions.json")   # type: ignore[return-value]
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


async def generate_task(
    task: HumanEvalTask,
    cfg: Config,
    client: InnkubeClient,
    force: bool = False,
    only_model: str | None = None,
) -> None:
    """Generate completions for one task across all (relation, model) combos.

    ``only_model`` regenerates a single model and **merges** the result into the
    existing completions.json, leaving every other model's cells byte-identical.
    Without it, regenerating one model means narrowing llm.models and rewriting
    the file from scratch -- which silently discards the models left out. That
    matters whenever a model has to be re-run for a reason of its own (a token
    budget that truncated its answers, say) and the rest of the corpus is sound
    and expensive to reproduce.
    """
    label = task_label(task)
    out = task_dir(cfg, "rq2", label, phase="generate")

    if force and only_model is None:
        clear_done(out)
    elif force:
        # Keep the file; drop only the marker, so the merge below has something
        # to merge into and the task is still re-processed.
        (out / "_done.marker").unlink(missing_ok=True)

    if is_done(out):
        logger.info("SKIP generate %s", label)
        return

    variants = build_task_variants(task, cfg)
    models = [m for m in cfg.llm.models if only_model is None or m.id == only_model]
    if only_model is not None and not models:
        raise SystemExit(
            f"--only-model {only_model!r} is not in llm.models "
            f"({', '.join(cfg.model_ids())})"
        )

    results: dict[str, dict[str, list[str]]] = {}
    if only_model is not None:
        # Start from what is on disk so untouched models survive verbatim.
        results = _existing_completions(out)
        logger.info("%s: regenerating %s only, merging into %d existing relation(s)",
                    label, only_model, len(results))
    empty_cells: list[dict] = []

    missing = [r for r in cfg.rq2.relations if r not in variants]
    if missing:
        # A generation gap in the corpus, already recorded when it was built.
        # Logged per task so the shortfall is visible in the run log too.
        logger.warning("%s: %d corpus variant(s) absent (%s) — cells left missing, not padded",
                       label, len(missing), ", ".join(missing))

    for relation, (prompt_variant, cache_salt) in variants.items():
        # Under --only-model this preserves the other models' cells for this
        # relation; a plain run starts each relation empty as before.
        results.setdefault(relation, {})
        messages = _build_messages(prompt_variant)

        for model_cfg in models:
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
            label, len(empty_cells), len(variants) * len(models),
            ", ".join(f"{c['relation']}/{c['model_id']}" for c in empty_cells),
        )
        return

    (out / "generation_failed.json").unlink(missing_ok=True)
    mark_done(out)
    logger.info("Generated completions for %s", label)


async def run_generate(cfg: Config, tasks: list[HumanEvalTask], force: bool = False,
                       only_model: str | None = None) -> None:
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
    coros = [generate_task(t, cfg, client, force=force, only_model=only_model)
             for t in tasks]
    await asyncio.gather(*coros)
