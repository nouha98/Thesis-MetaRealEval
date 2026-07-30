"""RQ3 execute phase: pairwise output divergence across paraphrase-derived solutions.

For each task, we take the best (most-correct) completion per relation per model,
execute all k solutions on M shared random inputs, and compute the pairwise
disagreement rate.  High disagreement signals that solutions may be incorrect
even when benchmark tests pass (false positives).
"""

from __future__ import annotations

import logging
import random
from itertools import combinations

from ..core.checkpoint import task_dir, read_json
from ..core.data_loader import HumanEvalTask, task_label
from ..core.sandbox import execute
from ..stage0.equivalence import _generate_inputs  # reuse input generator

logger = logging.getLogger(__name__)


def _pick_best_completion(completions: list[str], task: HumanEvalTask, timeout_s: float) -> str:
    """Return the first passing completion, or the first one if none pass."""
    from ..rq2.evaluator import _run_completion
    for comp in completions:
        if _run_completion(comp, task.prompt, task.test, task.entry_point, timeout_s):
            return comp
    return completions[0] if completions else ""


def _execute_on_input(code: str, entry_point: str, args: tuple, timeout_s: float) -> str:
    """Run code on args and return the string representation of the output."""
    call = f"\n__r__ = {entry_point}(*{repr(args)})\nprint(repr(__r__))"
    result = execute(code, call, timeout_s=timeout_s)
    if result.timed_out or not result.passed:
        return f"__error__"
    return result.stdout.strip()


def compute_divergence(
    task: HumanEvalTask,
    completions_data: dict,
    n_shared_inputs: int = 200,
    timeout_s: float = 5.0,
    seed: int = 42,
) -> dict:
    """Compute pairwise divergence across all (relation, model) solutions.

    Returns
    -------
    {
      "n_solutions": int,
      "n_inputs": int,
      "pairwise_disagreement_rate": float,  # fraction of (pair, input) combos with different output
      "solutions": [{"relation": str, "model": str, "code": str}, ...]
    }
    """
    from ..rq2.evaluator import _extract_function_body

    solutions: list[dict] = []
    for relation, model_completions in completions_data.items():
        for model_id, completions in model_completions.items():
            if not completions:
                continue
            best = _pick_best_completion(completions, task, timeout_s)
            body = _extract_function_body(best, task.entry_point)
            import re
            if not re.match(r"\s*def\s+", body):
                code = task.prompt + body
            else:
                code = body
            solutions.append({"relation": relation, "model": model_id, "code": code})

    if len(solutions) < 2:
        return {"n_solutions": len(solutions), "n_inputs": 0,
                "pairwise_disagreement_rate": 0.0, "solutions": solutions}

    inputs = _generate_inputs(task, n_shared_inputs, seed)

    # Collect outputs per solution
    all_outputs: list[list[str]] = []
    for sol in solutions:
        outputs = [_execute_on_input(sol["code"], task.entry_point, inp, timeout_s)
                   for inp in inputs]
        all_outputs.append(outputs)

    # Compute pairwise disagreement
    total_comparisons = 0
    disagreements = 0
    for i, j in combinations(range(len(solutions)), 2):
        for o_i, o_j in zip(all_outputs[i], all_outputs[j]):
            total_comparisons += 1
            if o_i != o_j:
                disagreements += 1

    rate = disagreements / total_comparisons if total_comparisons else 0.0

    return {
        "n_solutions": len(solutions),
        "n_inputs": len(inputs),
        "pairwise_disagreement_rate": rate,
        "disagreements": disagreements,
        "total_comparisons": total_comparisons,
        "solutions": [{"relation": s["relation"], "model": s["model"]} for s in solutions],
    }
