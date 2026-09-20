"""RQ3 runner: metamorphic validation via divergence + SBC scoring.

Phases
------
execute
    Run solutions from RQ2 on shared random inputs; compute pairwise divergence.
    CPU-bound → SLURM job array.

score
    Run SBC reverse generation via Innkube for each unique solution.
    LLM-bound → single SLURM job, async.

Usage
-----
    python -m meta_real_eval.rq3.runner --config config/default.yaml --phase execute --task-index 42
    python -m meta_real_eval.rq3.runner --config config/default.yaml --phase score
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
from pathlib import Path

from dotenv import load_dotenv

from ..core.cache import ResponseCache
from ..core.checkpoint import add_force_arg, clear_done, is_done, mark_done, task_dir, write_json, read_json
from ..core.config import BASELINE_RELATION, CONTROL_RELATION, Config
from ..core.data_loader import load_humaneval, task_label
from ..core.llm_client import InnkubeClient
from ..core.logging_setup import setup as setup_logging
from ..core.task_selection import add_task_selection_args, resolve_task_filter
from ..rq2.evaluator import build_solution_code
from .divergence import _pick_best_completion, compute_divergence
from .sbc_scorer import compute_sbc_score

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Execute phase
# ---------------------------------------------------------------------------

def select_divergence_relations(cfg: Config, label: str, available: list[str]) -> list[str]:
    """Choose which RQ2 relations feed one task's divergence computation.

    RQ3 must not inherit RQ2's full variant count. Divergence costs
    O(n_solutions * n_shared_inputs) subprocess spawns via ``_execute_on_input``;
    at 20 relations x 3 models x 200 inputs x 164 tasks that is roughly two
    million spawns, and it would also silently invalidate the calibrated
    ``tau_div``, which was derived at k=15 solutions.

    So: ``original`` plus ``rq3.variant_sample_per_family`` LLM variants drawn
    from each family, seeded from ``project.seed`` and the task label so the
    choice is deterministic per task but not the same slot for every task.

    Excluded on purpose:
      - the template relations — they are RQ2's control arm, and most of them are
        no-ops on the prompt, so they would contribute near-duplicate solutions;
      - ``control_resample`` — it is the original prompt again, so it would add a
        solution whose divergence measures sampling noise rather than paraphrase.

    If the corpus is not configured there are no LLM variants to sample, and
    every non-control relation is used — the pre-corpus behaviour.
    """
    from ..rq2.corpus import family_of

    by_family: dict[str, list[str]] = {}
    for relation in available:
        family = family_of(relation)
        if family is not None:
            by_family.setdefault(family, []).append(relation)

    if not by_family:
        return [r for r in available if r != CONTROL_RELATION]

    rng = random.Random(f"{cfg.project.seed}:{label}")
    selected = [BASELINE_RELATION] if BASELINE_RELATION in available else []
    for family in sorted(by_family):
        pool = sorted(by_family[family])
        k = min(cfg.rq3.variant_sample_per_family, len(pool))
        selected.extend(rng.sample(pool, k))
    return selected


def run_execute_one(task, cfg: Config, force: bool = False) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq3", label, phase="execute")

    if force:
        clear_done(out)

    if is_done(out):
        logger.info("SKIP execute %s", label)
        return

    gen_out = task_dir(cfg, "rq2", label, phase="generate")
    try:
        completions_data: dict = read_json(gen_out, "completions.json")
    except FileNotFoundError:
        logger.error("RQ2 completions missing for %s — run rq2 generate first", label)
        return

    # RQ2's evaluate phase already ran every completion against the intact
    # suite; reuse those outcomes rather than re-executing them here.
    eval_out = task_dir(cfg, "rq2", label, phase="evaluate")
    try:
        pass_rates: dict | None = read_json(eval_out, "pass_rates.json")
    except FileNotFoundError:
        pass_rates = None
        logger.warning(
            "pass_rates.json missing for %s — re-executing completions to label "
            "them (slower); run rq2 evaluate first to avoid this", label,
        )

    selected = select_divergence_relations(cfg, label, list(completions_data))
    sampled_data = {r: completions_data[r] for r in selected if r in completions_data}

    result = compute_divergence(
        task=task,
        completions_data=sampled_data,
        n_shared_inputs=cfg.rq3.n_shared_inputs,
        timeout_s=cfg.execution.timeout_s,
        seed=cfg.project.seed,
        cpu_workers=cfg.execution.cpu_workers,
        pass_rates=pass_rates,
    )

    # Which variants were sampled is part of the result, not an implementation
    # detail: the divergence rate is only interpretable against the set of
    # solutions it was computed over.
    result["selected_relations"] = selected
    write_json(out, "divergence.json", result)
    mark_done(out)
    rate = result["pairwise_disagreement_rate"]
    logger.info(
        "Divergence %s: %s (%d solutions from %d relations, %d inputs, "
        "%d comparable pair-observations, %d excluded as error)",
        label, f"{rate:.3f}" if rate is not None else "undefined (no comparable outputs)",
        result["n_solutions"], len(sampled_data), result["n_inputs"],
        result.get("n_comparable_pairs", 0), result.get("n_pairs_excluded_error", 0),
    )


# ---------------------------------------------------------------------------
# Score phase
# ---------------------------------------------------------------------------

async def _score_one(task, cfg: Config, client: InnkubeClient, force: bool = False) -> None:
    label = task_label(task)
    out = task_dir(cfg, "rq3", label, phase="score")

    if force:
        clear_done(out)

    if is_done(out):
        logger.info("SKIP score %s", label)
        return

    gen_out = task_dir(cfg, "rq2", label, phase="generate")
    try:
        completions_data: dict = read_json(gen_out, "completions.json")
    except FileNotFoundError:
        logger.warning("Missing RQ2 completions for %s", label)
        return

    # The same pass/fail outcomes the execute phase used to pick its
    # representative solution. Without them this phase scores a different
    # completion than the one whose label the analysis attaches to the score --
    # see the loop below.
    eval_out = task_dir(cfg, "rq2", label, phase="evaluate")
    try:
        pass_rates: dict | None = read_json(eval_out, "pass_rates.json")
    except FileNotFoundError:
        pass_rates = None
        logger.warning(
            "pass_rates.json missing for %s — SBC will score the first completion "
            "rather than the benchmark-passing one; run rq2 evaluate first", label,
        )

    model_id = cfg.model_ids()[0]
    sbc_results: dict[str, dict] = {}

    # Same containment as the execute phase, and for the same reason: SBC costs
    # one LLM call per (relation, model), so scoring every corpus variant would
    # multiply this phase's budget by the variant count. Both phases sample from
    # the same seed and task label, so they score the same solutions.
    selected = select_divergence_relations(cfg, label, list(completions_data))
    scored_data = {r: completions_data[r] for r in selected if r in completions_data}

    for relation, model_completions in scored_data.items():
        for mid, completions in model_completions.items():
            if not completions:
                continue
            # Score the SAME solution the execute phase scored. This used to
            # take completions[0] unconditionally, while analyze_results.py
            # joins each SBC score to the `passes_benchmark` label of the
            # solution _pick_best_completion chose -- the first *passing* one.
            # When those differ, the score describes one program and the label
            # another, which is why SBC's ROC-AUC came out at 0.464: chance.
            flags = None
            if pass_rates:
                flags = pass_rates.get(relation, {}).get(mid, {}).get("per_completion")
            best, _passes = _pick_best_completion(
                completions, task, cfg.execution.timeout_s, pass_flags=flags,
            )
            code = build_solution_code(best, task.prompt, task.entry_point)
            key = f"{relation}/{mid}"
            try:
                sbc_results[key] = await compute_sbc_score(task, code, model_id, client)
            except Exception as exc:
                logger.warning("SBC failed for %s/%s: %s", label, key, exc)

    write_json(out, "sbc_scores.json", sbc_results)
    mark_done(out)
    logger.info("SBC scored %s: %d solutions", label, len(sbc_results))


async def run_score(cfg: Config, tasks, force: bool = False) -> None:
    cache = ResponseCache(cfg.llm.cache_dir)
    client = InnkubeClient(cfg.llm, cache, mock=cfg.project.mock)
    coros = [_score_one(t, cfg, client, force=force) for t in tasks]
    await asyncio.gather(*coros)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="RQ3: metamorphic validation")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--phase", choices=["execute", "score"], required=True)
    add_task_selection_args(parser)
    add_force_arg(parser)
    args = parser.parse_args(argv)

    cfg = Config.from_yaml(args.config)
    setup_logging("rq3", args.phase, log_dir=Path("logs"))

    tasks = load_humaneval(tasks=resolve_task_filter(args, cfg))
    logger.info("RQ3 phase=%s, %d task(s)%s", args.phase, len(tasks), " (forced)" if args.force else "")

    if args.phase == "execute":
        for task in tasks:
            try:
                run_execute_one(task, cfg, force=args.force)
            except Exception:
                logger.exception("Execute failed for %s — leaving unmarked, retry later",
                                  task_label(task))
    else:
        asyncio.run(run_score(cfg, tasks, force=args.force))

    logger.info("RQ3 phase=%s complete.", args.phase)


if __name__ == "__main__":
    main()
