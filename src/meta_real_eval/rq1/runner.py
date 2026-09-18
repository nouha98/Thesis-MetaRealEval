"""RQ1 runner: fault characterisation and benchmark adequacy.

Phases
------
generate
    Build the LLM (semantic) mutant corpus via Innkube. Every configured
    model is asked for mutants on every task (each attempt retried up to
    MAX_GENERATE_ATTEMPTS times on empty output); a task is only marked
    done once at least one model produced mutants, and generation_failed.json
    records any model(s) that never did, whether or not the task overall
    completed -- see it to find tasks/models that need a re-run.
    Traditional (AOR/ROR/SDL) mutants are already produced by Stage 0's
    corpus_builder; this phase only adds the LLM-specific ones.
    LLM-bound → run as a single SLURM job.

evaluate
    Run the benchmark test suite against all non-equivalent mutants and
    compute kill rates per operator category.
    CPU-bound → SLURM job array, one task per element.

Usage
-----
    python -m meta_real_eval.rq1.runner --config config/default.yaml --phase generate
    python -m meta_real_eval.rq1.runner --config config/default.yaml --phase evaluate --task-index 42
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

from ..core.cache import ResponseCache
from ..core.checkpoint import add_force_arg, clear_done, is_done, mark_done, task_dir, write_json, read_json
from ..core.config import Config
from ..core.data_loader import load_humaneval, task_label
from ..core.llm_client import InnkubeClient
from ..core.logging_setup import setup as setup_logging
from ..core.task_selection import add_task_selection_args, resolve_task_filter
from ..stage0.corpus_builder import Mutant
from ..stage0.equivalence import check_equivalence, compute_canonical_outputs
from .ast_fallback import generate_ast_fallback_mutants
from .kill_rate import compute_kill_matrix, summarise
from .llm_mutator import FAULT_HINTS, generate_llm_mutants

logger = logging.getLogger(__name__)

# Retries are for a *live model* returning zero usable mutants (empty
# completions, all-unparseable output, etc.) -- resampling at temperature 0.9
# can succeed on a later attempt even though nothing changed on our end.
# Transient network errors (429/5xx) are already retried inside InnkubeClient
# itself; this is a coarser, higher-level retry around the whole generation
# call. If every attempt still comes back empty, the task is left incomplete
# (no _done.marker) rather than silently backfilled with AST-based mutants --
# see generation_failed.json for why, and rerun with --task-index once fixed.
MAX_GENERATE_ATTEMPTS = 4
GENERATE_RETRY_DELAY_S = 1.0


# ---------------------------------------------------------------------------
# Generate phase
# ---------------------------------------------------------------------------

async def _generate_with_retries(task, model_id: str, client: InnkubeClient) -> tuple[list, str | None]:
    """Call generate_llm_mutants for one model, retrying on empty output.

    Returns (mutants, None) on success, or ([], last_error) once every
    attempt has come back empty.
    """
    mutants: list = []
    last_error: str | None = None
    for attempt in range(1, MAX_GENERATE_ATTEMPTS + 1):
        try:
            mutants = await generate_llm_mutants(
                task=task, model_id=model_id, client=client, n_mutants=3,
                cache_salt=f"llm-mutant-attempt-{attempt}",
                fault_hint=FAULT_HINTS[(attempt - 1) % len(FAULT_HINTS)],
            )
        except Exception as exc:
            mutants = []
            last_error = f"{type(exc).__name__}: {exc}"

        if mutants:
            return mutants, None

        last_error = last_error or "LLM returned zero usable mutants"
        logger.warning("LLM generation attempt %d/%d empty for %s (model=%s): %s",
                        attempt, MAX_GENERATE_ATTEMPTS, task_label(task), model_id, last_error)
        if attempt < MAX_GENERATE_ATTEMPTS:
            await asyncio.sleep(GENERATE_RETRY_DELAY_S)

    return [], last_error


async def _generate_one(task, cfg: Config, client: InnkubeClient, force: bool = False) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq1", label, phase="generate")

    if force:
        clear_done(out)

    if is_done(out):
        logger.info("SKIP generate %s", label)
        return

    logger.info("Generating LLM mutants for %s", label)

    if cfg.project.mock:
        # Offline dev mode: no network calls at all, by design -- unrelated
        # to the live-generation retry/skip logic below.
        mutants = generate_ast_fallback_mutants(
            task.prompt, task.canonical_solution, seed=cfg.project.seed
        )
        data = [
            {"mutant_id": m.mutant_id, "operator": m.operator,
             "description": m.description, "code": m.code,
             "source_model": "ast_fallback"}
            for m in mutants
        ]
    else:
        # Every configured model contributes mutants to every task. Sourcing
        # each task from a single round-robin model made per-model health
        # invisible at the task level and left RQ1a's "LLM faults form a
        # distinct class" claim resting on only 1/n of the corpus per model.
        model_ids = cfg.model_ids()
        data = []
        failures: list[dict] = []
        for model_id in model_ids:
            mutants, error = await _generate_with_retries(task, model_id, client)
            if mutants:
                data.extend(
                    {"mutant_id": m.mutant_id, "operator": m.operator,
                     "description": m.description, "code": m.code,
                     "source_model": model_id}
                    for m in mutants
                )
            else:
                failures.append({"model_id": model_id, "attempts": MAX_GENERATE_ATTEMPTS, "last_error": error})

        if failures:
            failed_ids = {f["model_id"] for f in failures}
            write_json(out, "generation_failed.json", {
                "task_id": task.task_id,
                "task_label": label,
                "failed_models": failures,
                "succeeded_models": [m for m in model_ids if m not in failed_ids],
            })

        if not data:
            logger.error(
                "LLM generation failed for %s (task_id=%s): all %d model(s) exhausted %d attempts -- "
                "skipping, task left incomplete for re-run",
                label, task.task_id, len(model_ids), MAX_GENERATE_ATTEMPTS,
            )
            return  # no mark_done(): is_done() stays False, so this task is
                     # picked up again on the next run (with or without --force)

        if failures:
            logger.warning(
                "LLM generation partially failed for %s (task_id=%s): %d/%d model(s) failed (%s) -- "
                "marking done with the remaining model(s); see generation_failed.json",
                label, task.task_id, len(failures), len(model_ids),
                ", ".join(f["model_id"] for f in failures),
            )
        else:
            # Clear a stale record from an earlier partial/failed run now
            # that every configured model has succeeded.
            (out / "generation_failed.json").unlink(missing_ok=True)

    write_json(out, "llm_mutants.json", data)
    mark_done(out)
    logger.info("  Saved %d LLM mutants for %s", len(data), label)


async def run_generate(cfg: Config, tasks, force: bool = False) -> None:
    cache = ResponseCache(cfg.llm.cache_dir)
    client = InnkubeClient(cfg.llm, cache, mock=cfg.project.mock)
    coros = [_generate_one(t, cfg, client, force=force) for t in tasks]
    await asyncio.gather(*coros)


# ---------------------------------------------------------------------------
# Evaluate phase
# ---------------------------------------------------------------------------

def _filter_llm_equivalents(task, llm_mutants, cfg: Config, out) -> set[str]:
    """Run Stage 0's equivalence check over the LLM mutant population.

    Returns the set of mutant_ids that are behaviourally identical to the
    canonical solution, and records the full verdicts alongside the kill
    matrix for transparency.
    """
    canon_outs = compute_canonical_outputs(
        task=task,
        n_fuzz_inputs=cfg.stage0.n_fuzz_inputs,
        timeout_s=cfg.execution.timeout_s,
        seed=cfg.project.seed,
        cpu_workers=cfg.execution.cpu_workers,
    )

    verdicts: list[dict] = []
    equivalent: set[str] = set()
    with ProcessPoolExecutor(max_workers=cfg.execution.cpu_workers) as pool:
        futures = {
            pool.submit(
                check_equivalence, task, mutant,
                cfg.stage0.n_fuzz_inputs, cfg.execution.timeout_s,
                cfg.project.seed, canon_outs,
            ): mutant
            for mutant in llm_mutants
        }
        for future in as_completed(futures):
            result = future.result()
            verdicts.append({
                "mutant_id": result.mutant_id,
                "is_equivalent": result.is_equivalent,
                "reason": result.reason,
                "n_inputs_tested": result.n_inputs_tested,
                "diverging_input": result.diverging_input,
            })
            if result.is_equivalent:
                equivalent.add(result.mutant_id)

    write_json(out, "llm_equiv_filter.json", verdicts)
    logger.info("  LLM equivalence: %d/%d flagged equivalent",
                len(equivalent), len(llm_mutants))
    return equivalent


def run_evaluate_one(task, cfg: Config, force: bool = False) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq1", label, phase="evaluate")

    if force:
        clear_done(out)

    if is_done(out):
        logger.info("SKIP evaluate %s", label)
        return

    # Load traditional mutants from Stage 0
    s0_out = task_dir(cfg, "stage0", label)
    try:
        trad_raw = read_json(s0_out, "mutants.json")
        equiv_raw = read_json(s0_out, "equiv_filter.json")
    except FileNotFoundError:
        logger.error("Stage 0 outputs missing for %s — run stage0 first", label)
        return

    # Load LLM mutants from rq1 generate phase
    rq1_gen_out = task_dir(cfg, "rq1", label, phase="generate")
    try:
        llm_raw = read_json(rq1_gen_out, "llm_mutants.json")
    except FileNotFoundError:
        llm_raw = []
        if (rq1_gen_out / "generation_failed.json").exists():
            logger.warning("LLM generation never completed for %s (task_id=%s) — "
                            "using traditional only; see %s/generation_failed.json",
                            label, task.task_id, rq1_gen_out)
        else:
            logger.warning("No LLM mutants found for %s — using traditional only "
                            "(rq1 generate phase not yet run?)", label)

    all_mutants = [
        Mutant(
            mutant_id=m["mutant_id"], operator=m["operator"],
            description=m["description"], code=m["code"],
        )
        for m in (trad_raw + llm_raw)
    ]

    equiv_ids = {
        r["mutant_id"]
        for r in equiv_raw
        if r["is_equivalent"]
    }

    # Stage 0 only sees the traditional population — LLM mutants don't exist
    # yet when it runs — so filter them here.  Without this, RQ1a compares a
    # filtered traditional population against an unfiltered LLM one, inflating
    # the kill-rate gap for a reason unrelated to the fault types themselves.
    llm_mutants = [m for m in all_mutants if m.mutant_id not in equiv_ids
                   and m.operator == "LLM"]
    if llm_mutants:
        equiv_ids |= _filter_llm_equivalents(task, llm_mutants, cfg, out)

    logger.info("Evaluating %s: %d mutants (%d equivalent, skipped)",
                label, len(all_mutants), len(equiv_ids))

    kill_results = compute_kill_matrix(
        task=task,
        mutants=all_mutants,
        equiv_ids=equiv_ids,
        timeout_s=cfg.execution.timeout_s,
        cpu_workers=cfg.execution.cpu_workers,
    )

    summary = summarise(kill_results)
    write_json(out, "kill_matrix.json", [
        {"mutant_id": r.mutant_id, "operator": r.operator, "is_killed": r.is_killed}
        for r in kill_results
    ])
    write_json(out, "kill_rate_summary.json", summary)
    mark_done(out)
    logger.info("  Kill rates: %s", summary)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="RQ1: fault characterisation")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--phase", choices=["generate", "evaluate"], required=True)
    add_task_selection_args(parser)
    add_force_arg(parser)
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    setup_logging("rq1", args.phase, log_dir=Path("logs"))

    tasks = load_humaneval(tasks=resolve_task_filter(args, cfg))
    logger.info("RQ1 phase=%s, %d task(s)%s", args.phase, len(tasks), " (forced)" if args.force else "")

    if args.phase == "generate":
        asyncio.run(run_generate(cfg, tasks, force=args.force))
    else:
        for task in tasks:
            run_evaluate_one(task, cfg, force=args.force)

    logger.info("RQ1 phase=%s complete.", args.phase)


if __name__ == "__main__":
    main()
