"""RQ3 execute phase: pairwise output divergence across paraphrase-derived solutions.

For each task, we take the best (most-correct) completion per relation per model,
execute all k solutions on M shared random inputs, and compute the pairwise
disagreement rate.  High disagreement signals that solutions may be incorrect
even when benchmark tests pass (false positives).
"""

from __future__ import annotations

import ast
import logging
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations

from ..core.checkpoint import task_dir, read_json
from ..core.data_loader import HumanEvalTask, task_label
from ..core.sandbox import execute
from ..stage0.equivalence import _generate_inputs  # reuse input generator

logger = logging.getLogger(__name__)


# Distinct from any real output. A crash or timeout means "we do not know what
# this solution would have produced" — it must never be counted as agreeing with
# another crash, and it can never serve as a consensus (expected) value.
ERROR_OUTPUT = "__error__"

# Cap on how many consensus (input, expected-output) pairs get persisted for the
# RQ4 assertion builder. The disagreement *rates* below are computed over every
# qualifying input; only the embedded corpus is truncated, to keep both
# divergence.json and the generated test block small.
MAX_CONSENSUS_ENTRIES = 50


def _pick_best_completion(
    completions: list[str],
    task: HumanEvalTask,
    timeout_s: float,
    pass_flags: list[bool] | None = None,
) -> tuple[str, bool]:
    """Return (completion, passes_benchmark) for the best available completion.

    The first completion that passes the task's own test suite is preferred; if
    none pass, the first one is returned with passes_benchmark=False.  The flag
    is the label RQ3 needs: divergence is scored as a *classifier* of "this
    solution passes the benchmark", so every solution must carry its outcome.

    ``pass_flags`` is RQ2's per-completion outcome vector for this cell.  When
    supplied, no code is executed here at all: RQ2's evaluate phase already ran
    exactly these completions against exactly this suite, so re-running them
    would burn up to n_completions subprocesses per (relation, model) — the
    serial cost this module's docstring blames for whole-task SLURM timeouts —
    and would risk RQ2 and RQ3 disagreeing about which solutions pass.
    """
    if not completions:
        return "", False

    if pass_flags is not None and len(pass_flags) == len(completions):
        for comp, passed in zip(completions, pass_flags):
            if passed:
                return comp, True
        return completions[0], False

    from ..rq2.evaluator import _run_completion
    for comp in completions:
        if _run_completion(comp, task.prompt, task.test, task.entry_point, timeout_s):
            return comp, True
    return completions[0], False


def _execute_on_input(code: str, entry_point: str, args: tuple, timeout_s: float) -> str:
    """Run code on args and return the string representation of the output."""
    call = f"\n__r__ = {entry_point}(*{repr(args)})\nprint(repr(__r__))"
    result = execute(code, call, timeout_s=timeout_s)
    if result.timed_out or not result.passed:
        return ERROR_OUTPUT
    return result.stdout.strip()


def compute_divergence(
    task: HumanEvalTask,
    completions_data: dict,
    n_shared_inputs: int = 200,
    timeout_s: float = 5.0,
    seed: int = 42,
    cpu_workers: int = 1,
    pass_rates: dict | None = None,
) -> dict:
    """Compute pairwise divergence across all (relation, model) solutions.

    Returns
    -------
    {
      "n_solutions": int,
      "n_inputs": int,
      "pairwise_disagreement_rate": float,  # fraction of (pair, input) combos with different output
      "consensus": {                        # majority-vote pseudo-oracle (RQ4 uses this)
         "n_inputs_with_consensus": int,
         "entries": [{"args_repr": str, "expected_repr": str,
                      "votes": int, "n_voters": int}, ...],
      },
      "solutions": [{"relation": str, "model": str,
                     "passes_benchmark": bool,          # RQ3 ROC label
                     "consensus_disagreement_rate": float}, ...]  # RQ3 ROC score
    }

    ``pass_rates`` is RQ2's pass_rates.json for this task.  Passing it lets the
    representative-solution pick reuse RQ2's per-completion outcomes instead of
    re-executing the whole suite, which is both faster and guarantees the two
    RQs agree on which completions pass.
    

    Execution across (solution, input) pairs is spread over ``cpu_workers``
    subprocess-launching worker processes (mirrors stage0's equivalence check
    and rq2's evaluator) — this is O(n_solutions * n_inputs) subprocess
    spawns, so running it serially against a shared SLURM time limit is what
    causes whole-task timeouts once a single candidate solution genuinely
    hangs (each of its n_inputs calls then pays the full timeout_s).

    A single malformed/crashing completion is isolated with try/except and
    logged rather than allowed to take down the entire task.
    """
    from ..rq2.evaluator import build_solution_code

    solutions: list[dict] = []
    for relation, model_completions in completions_data.items():
        for model_id, completions in model_completions.items():
            if not completions:
                continue
            flags = None
            if pass_rates:
                cell = pass_rates.get(relation, {}).get(model_id, {})
                flags = cell.get("per_completion")
            try:
                best, passes = _pick_best_completion(
                    completions, task, timeout_s, pass_flags=flags
                )
                # Same assembly rule as RQ2's evaluator: a body-only completion
                # gets the prompt prepended, a complete module keeps its own
                # imports. Deciding it differently here would score the same
                # solution as correct in one RQ and broken in another.
                code = build_solution_code(best, task.prompt, task.entry_point)
            except Exception as exc:
                logger.warning(
                    "Skipping %s/%s for %s — completion extraction failed: %s",
                    relation, model_id, task_label(task), exc,
                )
                continue
            solutions.append({"relation": relation, "model": model_id,
                              "code": code, "passes_benchmark": passes})

    if len(solutions) < 2:
        return {"n_solutions": len(solutions), "n_inputs": 0,
                "pairwise_disagreement_rate": 0.0,
                "consensus": {"n_inputs_with_consensus": 0, "entries": []},
                "solutions": [{k: v for k, v in s.items() if k != "code"}
                              for s in solutions]}

    inputs = _generate_inputs(task, n_shared_inputs, seed)
    n_inputs = len(inputs)

    # Collect outputs per solution. Flatten (solution, input) into parallel
    # lists so the subprocess spawns are spread across cpu_workers processes
    # instead of running the full n_solutions * n_inputs sequentially.
    if cpu_workers <= 1:
        flat_outputs = [
            _execute_on_input(sol["code"], task.entry_point, inp, timeout_s)
            for sol in solutions for inp in inputs
        ]
    else:
        codes, entry_points, args_list, timeouts = [], [], [], []
        for sol in solutions:
            for inp in inputs:
                codes.append(sol["code"])
                entry_points.append(task.entry_point)
                args_list.append(inp)
                timeouts.append(timeout_s)
        with ProcessPoolExecutor(max_workers=cpu_workers) as pool:
            flat_outputs = list(pool.map(
                _execute_on_input, codes, entry_points, args_list, timeouts,
            ))

    all_outputs: list[list[str]] = [
        flat_outputs[i * n_inputs:(i + 1) * n_inputs] for i in range(len(solutions))
    ]

    # Compute pairwise disagreement
    total_comparisons = 0
    disagreements = 0
    for i, j in combinations(range(len(solutions)), 2):
        for o_i, o_j in zip(all_outputs[i], all_outputs[j]):
            total_comparisons += 1
            if o_i != o_j:
                disagreements += 1

    rate = disagreements / total_comparisons if total_comparisons else 0.0

    consensus, per_solution = _build_consensus(solutions, inputs, all_outputs)

    return {
        "n_solutions": len(solutions),
        "n_inputs": len(inputs),
        "pairwise_disagreement_rate": rate,
        "disagreements": disagreements,
        "total_comparisons": total_comparisons,
        "consensus": consensus,
        "solutions": per_solution,
    }


def _is_literal(text: str) -> bool:
    """True if text can be embedded in generated code as a Python literal."""
    try:
        ast.literal_eval(text)
        return True
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return False


def _build_consensus(
    solutions: list[dict],
    inputs: list[tuple],
    all_outputs: list[list[str]],
) -> tuple[dict, list[dict]]:
    """Derive a majority-vote pseudo-oracle and score each solution against it.

    For every shared input we take the modal output across the k solutions and
    keep it only if it is a *leave-one-out safe* strict majority: after dropping
    one vote (the candidate under test may itself be one of the reference
    solutions) it must still be a strict majority.  That is a static, per-task
    approximation of proper leave-one-out — it costs no per-candidate code
    generation and can only make the oracle more conservative.

    Crucially the majority is counted against **all** reference solutions, not
    just the ones that produced an output.  Error/timeout outputs never vote and
    never become an expected value, but they still count in the denominator.
    Without that, an input on which most solutions legitimately raise (an empty
    list to a function that divides by len(xs)) would let the handful of
    degenerate solutions that silently return None define the "expected" value —
    and every correct candidate would then fail the assertion.

    A solution that errors where a consensus does exist is counted as disagreeing
    with it (behavioural divergence, not missing data).

    Returns (consensus_block, per_solution_rows).
    """
    n_solutions = len(solutions)
    kept: list[tuple[int, str, int, int]] = []   # (input_index, expected, votes, n_voters)

    for idx in range(len(inputs)):
        column = [all_outputs[s][idx] for s in range(n_solutions)]
        voters = [o for o in column if o != ERROR_OUTPUT]
        if len(voters) < 3:
            continue                      # majority is undefined below 3 voters
        expected, votes = Counter(voters).most_common(1)[0]
        if (votes - 1) <= (n_solutions - 1) / 2:
            continue                      # not a leave-one-out safe majority
        if not _is_literal(expected):
            # RQ4 embeds this value verbatim in generated assertion code. An
            # output whose repr is not a Python literal (a custom object's
            # "<X at 0x...>") would make that code a SyntaxError, failing every
            # candidate and faking an augmentation effect.
            continue
        kept.append((idx, expected, votes, len(voters)))

    per_solution: list[dict] = []
    for s_i, sol in enumerate(solutions):
        n_disagree = sum(
            1 for idx, expected, _, _ in kept if all_outputs[s_i][idx] != expected
        )
        per_solution.append({
            "relation": sol["relation"],
            "model": sol["model"],
            "passes_benchmark": sol["passes_benchmark"],
            "n_consensus_inputs": len(kept),
            "n_consensus_disagreements": n_disagree,
            "consensus_disagreement_rate": n_disagree / len(kept) if kept else 0.0,
        })

    consensus = {
        "n_reference_solutions": n_solutions,
        "n_inputs_with_consensus": len(kept),
        "n_entries_persisted": min(len(kept), MAX_CONSENSUS_ENTRIES),
        "entries": [
            {"args_repr": repr(inputs[idx]), "expected_repr": expected,
             "votes": votes, "n_voters": n_voters, "n_solutions": n_solutions}
            for idx, expected, votes, n_voters in kept[:MAX_CONSENSUS_ENTRIES]
        ],
    }
    return consensus, per_solution
