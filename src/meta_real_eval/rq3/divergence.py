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

# A consensus needs enough working references to mean anything. Below this many
# solutions produced a value, "they all agree" is an accident of a small sample.
MIN_VOTERS = 3

# ...and those voters must be most of the solution set. An input where only a
# handful of references ran is one the others crashed on, which usually means it
# sits outside the task's domain -- exactly where a confident-looking consensus
# is most likely to be wrong. See _build_consensus for the measured cases.
MIN_VOTER_SHARE = 0.8


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
                "pairwise_disagreement_rate": None,
                "n_comparable_pairs": 0,
                "n_pairs_excluded_error": 0,
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

    # Pairwise disagreement, over comparable outputs only.
    #
    # A crash or timeout means "we do not know what this solution would have
    # produced", so a pair where either side errored carries no information
    # about whether the two behave alike. Comparing the ERROR_OUTPUT sentinels
    # as if they were values made two crashed solutions *agree* with each other
    # and disagree with everything that ran -- so the rate measured how many
    # solutions were broken, not how far the working ones diverged. On the
    # pre-repair corpus that was not a subtle effect: on 72 of 164 tasks the
    # rate came out exactly g(n-g)/C(n,2), the algebraic signature of g crashing
    # solutions standing against the rest, and the resulting ROC-AUC of 0.957
    # was detecting broken extraction rather than wrong answers.
    comparable = 0
    excluded_error = 0
    disagreements = 0
    for i, j in combinations(range(len(solutions)), 2):
        for o_i, o_j in zip(all_outputs[i], all_outputs[j]):
            if o_i == ERROR_OUTPUT or o_j == ERROR_OUTPUT:
                excluded_error += 1
                continue
            comparable += 1
            if o_i != o_j:
                disagreements += 1

    # None, not 0.0: with nothing comparable there is no evidence either way,
    # and 0.0 would read as "these solutions agree perfectly" -- which would
    # then gate a task out of RQ4 augmentation for the wrong reason.
    rate = disagreements / comparable if comparable else None

    consensus, per_solution = _build_consensus(solutions, inputs, all_outputs)

    return {
        "n_solutions": len(solutions),
        "n_inputs": len(inputs),
        "pairwise_disagreement_rate": rate,
        "disagreements": disagreements,
        "n_comparable_pairs": comparable,
        "n_pairs_excluded_error": excluded_error,
        "total_comparisons": comparable + excluded_error,
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
    """Derive a unanimous-vote pseudo-oracle and score each solution against it.

    For every shared input we keep the output only when **every** reference
    solution that produced a value produced the *same* value, and enough of them
    ran to make that meaningful (``MIN_VOTER_SHARE`` of the solution set).

    Why unanimity rather than a majority.  RQ4 turns each kept entry into an
    assertion that candidates must satisfy, so a wrong entry does not merely add
    noise -- it *fails correct solutions*, which is the one outcome the
    experiment cannot absorb. A majority rule admits exactly that on inputs
    outside the task's intended domain, where the fuzzer supplies values the
    specification never contemplated and the references disagree about what
    should happen. Measured on the recorded corpus:

        HumanEval/55   fib(-72) == 0         14 of 17 voters (18 solutions)
        HumanEval/100  make_a_pile(-72) == []  9 of 12 voters (12 solutions)
        HumanEval/119  match_parens(...) == 'Yes'  16 of 18 voters

    Each of those was a majority, each became an assertion, and each failed a
    solution that passes the full benchmark -- dropping qwen3-next from 1.0 to
    0.0 on two of the three tasks. All three are non-unanimous; all three are
    excluded here, while the entries that carry real signal (``fib(10) == 55``
    at 17/17, ``make_a_pile(3) == [3, 5, 7]`` at 12/12) survive. A task whose
    references cannot agree unanimously ends up with no assertions, which is
    the honest answer: there was no oracle to extract.

    This does **not** close the domain problem. If every reference agrees on a
    wrong out-of-domain value the entry is still kept, and a correct solution
    that raises there still fails. The real fix is generating in-domain inputs;
    until then, state the residual risk when reporting RQ4.

    Error/timeout outputs never vote and never become an expected value, but
    they still count in the denominator via ``MIN_VOTER_SHARE``: an input on
    which most solutions legitimately raise must not let the few that silently
    return None define the expected value.

    A solution that errors where a consensus does exist is counted as disagreeing
    with it (behavioural divergence, not missing data).

    Returns (consensus_block, per_solution_rows).
    """
    n_solutions = len(solutions)
    kept: list[tuple[int, str, int, int]] = []   # (input_index, expected, votes, n_voters)

    for idx in range(len(inputs)):
        column = [all_outputs[s][idx] for s in range(n_solutions)]
        voters = [o for o in column if o != ERROR_OUTPUT]
        if len(voters) < MIN_VOTERS:
            continue                      # too few working references to agree
        if len(voters) < MIN_VOTER_SHARE * n_solutions:
            continue                      # too many failed to produce a value
        distinct = Counter(voters)
        if len(distinct) > 1:
            continue                      # not unanimous -- see the docstring
        expected, votes = distinct.most_common(1)[0]
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
