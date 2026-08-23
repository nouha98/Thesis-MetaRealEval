"""Ranking stability and per-model sensitivity under prompt paraphrase.

Three questions, at three different granularities:

1. Ranking stability — "does a paraphrase change the *ordering* of models?"
   Kendall's tau_b correlates the model-score vector under a variant against
   the vector under 'original'.  Both vectors are indexed by model, so tau_b
   describes the whole leaderboard for one (task, relation) pair; it cannot be
   attributed to a single model.  (This file used to loop over model_ids and
   write the same number under each key — the correlated vectors span all
   models regardless of the loop variable, so every entry was an identical
   duplicate.  Verified: 0/164 tasks differed across models.)

2. Per-model sensitivity — "does a paraphrase move *this* model's score?"
   That one is genuinely per-model:  delta = pass@1(variant) - pass@1(original).

3. Per-model rank movement — "does a paraphrase change *this* model's
   position in the leaderboard, and by how many places?"  Ties are handled by
   fractional (average) ranking, so this is always defined — unlike tau_b, a
   fully-tied vector still has a well-defined rank_change of exactly 0 (no
   position moved), it never needs to be excluded as degenerate.

Undefined tau_b: when every model scores the same under a relation there is no
ordering to preserve and tau_b is 0/0.  We record null and exclude it from the
mean rather than substituting 1.0 ("stable") or 0.0 ("random").

No confidence interval is computed here: per task there are only 4 non-baseline
relations, far too few to bootstrap.  The CI is computed once across all tasks
in scripts/analyze_results.py.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from scipy.stats import kendalltau, rankdata

from ..core.checkpoint import task_dir, write_json, read_json
from ..core.config import Config
from ..core.data_loader import HumanEvalTask, task_label

logger = logging.getLogger(__name__)

BASELINE_RELATION = "original"


def _model_pass_at1(pass_rates: dict, relation: str) -> dict[str, float]:
    """Return {model_id: pass@1} for a given relation, skipping empty cells.

    A (relation, model) cell with no completions is missing data, not a score of
    zero: pass@1 over an empty sample is 0.0, which would enter the leaderboard
    as "this model got everything wrong". Callers check for a complete set of
    models before computing a ranking statistic.
    """
    return {
        model_id: rates["pass@1"]
        for model_id, rates in pass_rates.get(relation, {}).items()
        if rates.get("n", 0) > 0
    }


def _rank_vector(scores: dict[str, float], model_ids: list[str]) -> list[float]:
    """Convert {model_id: score} to a list of scores in fixed model order."""
    return [scores.get(mid, 0.0) for mid in model_ids]


def _tau_b(vec_a: list[float], vec_b: list[float]) -> Optional[float]:
    """Kendall tau_b between two model-score vectors, or None if undefined.

    A constant vector has no ordering, so tau_b is 0/0.  Returning None forces
    callers to exclude it rather than coerce it into a fabricated observation.
    """
    if len(set(vec_a)) <= 1 or len(set(vec_b)) <= 1:
        return None
    result = kendalltau(vec_a, vec_b)
    return None if np.isnan(result.statistic) else float(result.statistic)


def _rank_positions(scores: dict[str, float], model_ids: list[str]) -> dict[str, float]:
    """Rank models by score, best = rank 1.  Ties share the average rank
    (fractional ranking), so a tie never arbitrarily favours one model.
    """
    vec = _rank_vector(scores, model_ids)
    ranks = rankdata([-v for v in vec], method="average")  # negate: higher score -> lower (better) rank
    return dict(zip(model_ids, ranks))


def compute_ranking_stability(task: HumanEvalTask, cfg: Config) -> None:
    """Read pass_rates.json and write rankings.json for one task.

    Always recomputed — this is pure post-processing of pass_rates.json (no LLM
    calls, no sandbox execution), so there is nothing to checkpoint around.
    """
    label = task_label(task)
    out = task_dir(cfg, "rq2", label, phase="evaluate")

    try:
        pass_rates: dict = read_json(out, "pass_rates.json")
    except FileNotFoundError:
        logger.error("pass_rates.json missing for %s", label)
        return

    model_ids = cfg.model_ids()
    relations = [r for r in cfg.rq2.relations if r != BASELINE_RELATION]

    baseline_scores = _model_pass_at1(pass_rates, BASELINE_RELATION)
    baseline_vec = _rank_vector(baseline_scores, model_ids)

    # 1. Ranking stability: one tau_b per relation, not per model.
    # A relation missing any model has no leaderboard to compare, so it is
    # recorded as undefined alongside the all-tied case rather than ranked with
    # a fabricated 0.0 standing in for the absent model.
    incomplete_relations: list[str] = []
    baseline_complete = len(baseline_scores) == len(model_ids)
    tau_per_relation: dict[str, Optional[float]] = {}
    for relation in relations:
        variant_scores = _model_pass_at1(pass_rates, relation)
        if not baseline_complete or len(variant_scores) != len(model_ids):
            incomplete_relations.append(relation)
            tau_per_relation[relation] = None
            continue
        variant_vec = _rank_vector(variant_scores, model_ids)
        tau_per_relation[relation] = _tau_b(baseline_vec, variant_vec)

    if incomplete_relations:
        logger.warning(
            "%s: %d relation(s) missing a model's completions (%s) — excluded "
            "from tau_b rather than scored 0.0",
            label, len(incomplete_relations), ", ".join(incomplete_relations),
        )

    defined = [t for t in tau_per_relation.values() if t is not None]

    # 2. Per-model sensitivity: delta pass@1 against the baseline relation.
    delta_pass_at_1 = {
        model_id: {
            relation: round(
                _model_pass_at1(pass_rates, relation).get(model_id, 0.0)
                - baseline_scores.get(model_id, 0.0),
                6,
            )
            for relation in relations
        }
        for model_id in model_ids
    }

    # 3. Per-model rank movement: positive = moved to a better (lower-numbered)
    # rank; negative = moved to a worse one.  Always defined (see module docstring).
    baseline_ranks = _rank_positions(baseline_scores, model_ids)
    rank_change = {
        model_id: {
            relation: round(
                baseline_ranks[model_id]
                - _rank_positions(_model_pass_at1(pass_rates, relation), model_ids)[model_id],
                4,
            )
            for relation in relations
        }
        for model_id in model_ids
    }

    write_json(out, "rankings.json", {
        "model_ids": model_ids,
        "baseline_pass_at_1": baseline_scores,
        "tau_b_per_relation": tau_per_relation,
        "mean_tau_b": float(np.mean(defined)) if defined else None,
        "n_relations_defined": len(defined),
        "n_relations_total": len(tau_per_relation),
        "degenerate_relations": [r for r, t in tau_per_relation.items() if t is None],
        "incomplete_relations": incomplete_relations,
        "baseline_complete": baseline_complete,
        "delta_pass_at_1": delta_pass_at_1,
        "mean_abs_delta_pass_at_1": {
            model_id: float(np.mean([abs(d) for d in deltas.values()])) if deltas else 0.0
            for model_id, deltas in delta_pass_at_1.items()
        },
        "rank_change": rank_change,
        "mean_abs_rank_change": {
            model_id: float(np.mean([abs(c) for c in changes.values()])) if changes else 0.0
            for model_id, changes in rank_change.items()
        },
    })

    mean_tau = float(np.mean(defined)) if defined else None
    logger.info(
        "Rankings %s: mean_tau_b=%s over %d/%d relations",
        label,
        f"{mean_tau:.3f}" if mean_tau is not None else "undefined",
        len(defined), len(tau_per_relation),
    )
