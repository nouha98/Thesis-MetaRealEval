"""RQ4 interaction analysis: does prompt sensitivity compound with oracle weakness?

For each task, we re-run the RQ2 tau_b analysis at each degradation level
and regress tau_b against degradation percentage.  Page's L trend test checks
whether tau_b decreases monotonically as degradation increases.

H1b: Ranking instability (tau_b) increases monotonically with degradation degree.
"""

from __future__ import annotations

import logging

import numpy as np

from ..core.config import Config
from ..core.data_loader import HumanEvalTask
from ..rq2.evaluator import _run_completion, pass_at_k
from ..rq2.ranking import _rank_vector, _tau_b, collapse_tau_by_arm

logger = logging.getLogger(__name__)


def compute_tau_at_degradation_level(
    task: HumanEvalTask,
    completions_data: dict,
    degraded_test: str,
    cfg: Config,
) -> dict:
    """Re-run RQ2's ranking-stability protocol using a degraded test suite.

    Returns the (task, relation)-level summary that rq2.ranking produces, so
    every degradation level is directly comparable to the intact baseline:

        {"mean_tau_b": float | None, "tau_b_per_relation": {...},
         "degenerate_relations": [...], "pass_at_1": {relation: {model: float}}}

    tau_b describes the ordering of the whole model set, so there is one value
    per relation — not one per model (see rq2/ranking.py).

    ``pass_at_1`` is returned as well because two downstream analyses need the
    raw scores, not just their rank correlation: RQ4's rank-recovery statistic
    (H1a) compares each suite's model ranking against the intact-suite ranking,
    and the augment-vs-degrade verification check needs to see that the two
    suites actually score candidates differently.
    """
    model_ids = cfg.model_ids()
    relations = [r for r in cfg.rq2.relations if r != "original"]

    # pass@1 for each (relation, model) under the degraded test. A cell with no
    # completions is left out entirely rather than scored 0.0 — see
    # rq2/ranking.py::_model_pass_at1 for why an empty sample is not a zero.
    pass_at1: dict[str, dict[str, float]] = {}
    for relation, model_completions in completions_data.items():
        pass_at1[relation] = {}
        for model_id, completions in model_completions.items():
            n = len(completions)
            if n == 0:
                continue
            correct = 0
            for comp in completions:
                try:
                    if _run_completion(comp, task.prompt, degraded_test,
                                       task.entry_point, cfg.execution.timeout_s):
                        correct += 1
                except Exception:
                    pass
            pass_at1[relation][model_id] = pass_at_k(n, correct, 1)

    def _complete(relation: str) -> bool:
        scores = pass_at1.get(relation, {})
        return all(mid in scores for mid in model_ids)

    baseline_ok = _complete("original")
    baseline_vec = _rank_vector(pass_at1.get("original", {}), model_ids)
    complete_relations: list[str] = []
    tau_per_relation: dict[str, float | None] = {}
    for relation in relations:
        if not baseline_ok or not _complete(relation):
            tau_per_relation[relation] = None
            continue
        complete_relations.append(relation)
        variant_vec = _rank_vector(pass_at1.get(relation, {}), model_ids)
        tau_per_relation[relation] = _tau_b(baseline_vec, variant_vec)

    defined = [t for t in tau_per_relation.values() if t is not None]
    by_arm = collapse_tau_by_arm(tau_per_relation)
    return {
        # Same definition as rq2/ranking.py: the primary arm, collapsed
        # variant -> family -> arm. Page's L compares this value across
        # degradation levels, so it has to mean the same thing at every level.
        "mean_tau_b": by_arm["primary"],
        "tau_b_by_arm": by_arm,
        "mean_tau_b_all_relations": float(np.mean(defined)) if defined else None,
        "tau_b_per_relation": tau_per_relation,
        # Two different facts about a None, split the way rq2/ranking.py splits
        # them: `degenerate` had a complete cell under the degraded suite but
        # every model tied under it (no ordering to preserve); `incomplete` had
        # no cell at all (a model came back empty here, or the baseline itself
        # was incomplete). Collapsing them under one "degenerate_relations" key
        # is the same mistake RQ2's coverage gate made — a relation could look
        # like a gap in the data when it was actually a tied, fully-observed
        # ranking (see rq2/corpus.py::MIN_FAMILIES_COVERED).
        "degenerate_relations": [r for r in complete_relations if tau_per_relation[r] is None],
        "incomplete_relations": [r for r in relations if r not in complete_relations],
        "pass_at_1": pass_at1,
    }


# H1b's Page's L trend test lives in analysis/statistics.py and is run once over
# all tasks by scripts/analyze_results.py, not per task here.
#
# It used to be computed per task, which cannot work: Page's L is a
# randomized-block statistic, and one task is a single block (n=1) whose k=4
# arrangements have no usable asymptotics. That version also fed *raw* tau
# values into L while comparing the result against the null moments of a
# rank-sum statistic, so L (range -10..-2 across the corpus) was tested against
# mean_L=25 -- the z-score was hugely negative by construction and the test
# returned p=1.0 on all 162 tasks, verdict False on 162/162. It could never
# fire, whatever the data did. Tasks are the blocks; the trend is a property of
# the corpus, so the test belongs where the per-task values are pooled.
