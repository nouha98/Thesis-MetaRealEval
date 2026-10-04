"""RQ3 execute phase: pairwise output divergence across paraphrase-derived solutions.

For each task, we take the best (most-correct) completion per relation per model,
execute all k solutions on M shared random inputs, and compute the pairwise
disagreement rate.  High disagreement signals that solutions may be incorrect
even when benchmark tests pass (false positives).
"""

from __future__ import annotations

import ast
import json
import logging
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations

from ..benchmarks import get_benchmark
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


# ---------------------------------------------------------------------------
# Benchmark-agnostic version (see the Tier 2 plan, RQ3). Added alongside the
# Tier 1-only functions above, which rq3/runner.py no longer calls but which
# stay exactly as they are.
#
# Two things the Tier 1 code gets "for free" from its shape, carried over
# deliberately rather than lost in the generalisation:
#
#   excluded != disagree   ERROR_OUTPUT is one sentinel standing in for BOTH
#                          a timeout and a crash. The generic observations
#                          (Benchmark.observe) distinguish them
#                          (is_timeout / is_error), so _unusable below checks
#                          both -- comparing only against one sentinel would
#                          silently let a real timeout slip through as a
#                          "comparable" value.
#   semantic comparison    for a plain string (Tier 1) `==` and
#                          observations_agree agree trivially. For a Tier 2
#                          trace dict, only observations_agree compares
#                          correctly (sorted keys, nondeterminism masking);
#                          `==` on two dicts would not.
#
# Consensus-building (RQ4's input) IS ported below (_build_consensus_generic),
# now that RQ4's consistency_suite exists to consume it. Tier 2's analogue of
# Tier 1's "embed a Python literal" is "majority-vote token per scenario step,
# replayed at runtime via forkserver._run_scenario and compared" (see
# RealClassEvalBenchmark.consistency_suite) -- a different shape, so the
# consensus entries below carry a benchmark-opaque ``expected_obs`` (the
# representative observation itself) plus Tier 1's own ``args_repr``/
# ``expected_repr`` fields where the observation is a plain string, rather
# than forcing one shape on both. RQ3's own headline metric -- the pairwise
# disagreement rate ROC-labelled by passes_benchmark, which τ_div is
# calibrated against -- was already fully generic above; this section is
# purely RQ4's input.
# ---------------------------------------------------------------------------

def _pick_best_completion_generic(
    bench,
    completions: list[str],
    task,
    timeout_s: float,
    pass_flags: list[bool] | None = None,
) -> tuple[str, bool]:
    """Generic _pick_best_completion. See its docstring; same contract."""
    if not completions:
        return "", False
    if pass_flags is not None and len(pass_flags) == len(completions):
        for comp, passed in zip(completions, pass_flags):
            if passed:
                return comp, True
        return completions[0], False
    for comp in completions:
        code = bench.build_solution(task, comp)
        if bench.run_suite(task, code, timeout_s).passed_all:
            return comp, True
    return completions[0], False


def _observe_one_generic(cfg, task, code: str, pool, index: int, timeout_s: float):
    """Module-level, picklable worker: reconstructs the benchmark per call
    (cheap -- no I/O; see rq2.evaluator._score_completion's docstring for why)
    rather than pickling a benchmark instance into every submitted item."""
    bench = get_benchmark(cfg)
    return bench.observe_one(task, code, pool, index, timeout_s)


def _unusable(bench, obs) -> bool:
    """True if ``obs`` carries no information about this solution's output --
    a timeout or a crash -- and so must be excluded from comparison rather
    than compared as if it were a value."""
    return bench.is_timeout(obs) or bench.is_error(obs)


def _vote_key(obs) -> str:
    """A hashable canonical form for majority-vote grouping.

    Tier 1 observations are already strings (hashable as-is). Tier 2
    observations are trace dicts; ``json.dumps(sort_keys=True)`` gives the
    same canonical-and-hashable property without this module (or
    _build_consensus_generic) needing to know which benchmark produced the
    observation -- it dispatches on the *shape* of ``obs``, not a benchmark
    name.
    """
    return obs if isinstance(obs, str) else json.dumps(obs, sort_keys=True, default=str)


def _build_consensus_generic(
    bench,
    pool,
    solutions: list[dict],
    all_outputs: list[list],
    max_entries: int = MAX_CONSENSUS_ENTRIES,
) -> tuple[dict, list[dict]]:
    """Generic _build_consensus: same unanimous-vote rule (MIN_VOTERS,
    MIN_VOTER_SHARE, unanimity -- see _build_consensus's docstring for why),
    grouping by :func:`_vote_key` instead of raw string equality so it works
    for Tier 2's structured traces too.

    Each entry carries ``scenario_index`` (Tier 2's consistency_suite
    recomputes the same input pool from (task, n_shared_inputs, seed) -- see
    compute_divergence_generic -- and looks the scenario back up by this
    index rather than the entry serialising the scenario's steps itself) and
    ``expected_obs`` (the representative observation, opaque to this
    function's caller). Tier 1's own ``args_repr``/``expected_repr`` fields
    are filled in only when the observation is a plain string, so
    rq4.consistency.build_consistency_assertions (which reads exactly those
    two keys) keeps working unchanged against this function's output.
    """
    n_solutions = len(solutions)
    kept: list[tuple[int, str, object, int, int]] = []  # (idx, key, representative, votes, n_voters)

    for idx in range(len(pool.items)):
        column = [all_outputs[s][idx] for s in range(n_solutions)]
        voter_idx = [i for i, o in enumerate(column) if not _unusable(bench, o)]
        if len(voter_idx) < MIN_VOTERS:
            continue
        if len(voter_idx) < MIN_VOTER_SHARE * n_solutions:
            continue
        keys = [_vote_key(column[i]) for i in voter_idx]
        distinct = Counter(keys)
        if len(distinct) > 1:
            continue
        key, votes = distinct.most_common(1)[0]
        representative = column[voter_idx[keys.index(key)]]
        kept.append((idx, key, representative, votes, len(voter_idx)))

    per_solution: list[dict] = []
    for s_i, sol in enumerate(solutions):
        n_disagree = sum(
            1 for idx, key, _, _, _ in kept if _vote_key(all_outputs[s_i][idx]) != key
        )
        per_solution.append({
            "relation": sol["relation"],
            "model": sol["model"],
            "passes_benchmark": sol["passes_benchmark"],
            "n_consensus_inputs": len(kept),
            "n_consensus_disagreements": n_disagree,
            "consensus_disagreement_rate": n_disagree / len(kept) if kept else 0.0,
        })

    entries = []
    for idx, key, representative, votes, n_voters in kept[:max_entries]:
        entry = {
            "scenario_index": idx,
            "expected_obs": representative,
            "votes": votes, "n_voters": n_voters, "n_solutions": n_solutions,
        }
        if isinstance(representative, str) and _is_literal(representative):
            # Tier 1 shape: build_consistency_assertions reads these two keys
            # and embeds expected_repr verbatim as a Python literal.
            entry["args_repr"] = repr(pool.items[idx])
            entry["expected_repr"] = representative
        entries.append(entry)

    consensus = {
        "n_reference_solutions": n_solutions,
        "n_inputs_with_consensus": len(kept),
        "n_entries_persisted": min(len(kept), max_entries),
        "entries": entries,
    }
    return consensus, per_solution


def compute_divergence_generic(
    cfg,
    task,
    completions_data: dict,
    n_shared_inputs: int = 200,
    timeout_s: float = 5.0,
    seed: int = 42,
    cpu_workers: int = 1,
    pass_rates: dict | None = None,
) -> dict:
    """Generic compute_divergence: same algorithm, same output shape (minus
    the Tier-1-only consensus entries -- see this section's docstring),
    driven through the Benchmark protocol. For HumanEvalBenchmark this
    reproduces compute_divergence's pairwise_disagreement_rate and per-solution
    labels exactly -- see tests/test_rq3/test_divergence_adapter.py.
    """
    bench = get_benchmark(cfg)

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
                best, passes = _pick_best_completion_generic(
                    bench, completions, task, timeout_s, pass_flags=flags
                )
                code = bench.build_solution(task, best)
            except Exception as exc:
                logger.warning(
                    "Skipping %s/%s for %s — completion extraction failed: %s",
                    relation, model_id, task.label, exc,
                )
                continue
            solutions.append({"relation": relation, "model": model_id,
                              "code": code, "passes_benchmark": passes})

    def _empty_result() -> dict:
        return {"n_solutions": len(solutions), "n_inputs": 0,
                "pairwise_disagreement_rate": None,
                "n_comparable_pairs": 0,
                "n_pairs_excluded_error": 0,
                "consensus": {"n_inputs_with_consensus": 0, "entries": []},
                "solutions": [{k: v for k, v in s.items() if k != "code"}
                              for s in solutions],
                "n_shared_inputs_requested": n_shared_inputs,
                "seed": seed}

    if len(solutions) < 2:
        return _empty_result()

    pool = bench.input_pool(task, n_shared_inputs, seed)
    n_inputs = len(pool.items)

    if n_inputs == 0:
        return _empty_result()

    # Flattened (solution, input) submissions in ONE pool, matching
    # compute_divergence's own structure -- the parallelism unit is a single
    # (solution, input) observation, not a whole solution's batch, which is
    # what keeps a single hanging candidate from costing n_inputs timeouts
    # serially (see the module docstring).
    if cpu_workers <= 1:
        flat = [_observe_one_generic(cfg, task, sol["code"], pool, idx, timeout_s)
               for sol in solutions for idx in range(n_inputs)]
    else:
        jobs = [(sol["code"], idx) for sol in solutions for idx in range(n_inputs)]
        with ProcessPoolExecutor(max_workers=cpu_workers) as ex:
            flat = list(ex.map(
                _observe_one_generic,
                [cfg] * len(jobs), [task] * len(jobs), [c for c, _ in jobs],
                [pool] * len(jobs), [i for _, i in jobs], [timeout_s] * len(jobs),
            ))

    all_outputs = [flat[i * n_inputs:(i + 1) * n_inputs] for i in range(len(solutions))]

    comparable = 0
    excluded_error = 0
    disagreements = 0
    for i, j in combinations(range(len(solutions)), 2):
        for o_i, o_j in zip(all_outputs[i], all_outputs[j]):
            if _unusable(bench, o_i) or _unusable(bench, o_j):
                excluded_error += 1
                continue
            comparable += 1
            if not bench.observations_agree(o_i, o_j):
                disagreements += 1

    rate = disagreements / comparable if comparable else None

    consensus, per_solution = _build_consensus_generic(bench, pool, solutions, all_outputs)

    return {
        "n_solutions": len(solutions),
        "n_inputs": n_inputs,
        "pairwise_disagreement_rate": rate,
        "disagreements": disagreements,
        "n_comparable_pairs": comparable,
        "n_pairs_excluded_error": excluded_error,
        "total_comparisons": comparable + excluded_error,
        "consensus": consensus,
        "solutions": per_solution,
        # consistency_suite recomputes this exact pool from (task, n_shared_inputs,
        # seed) to look a consensus entry's scenario_index back up -- see
        # _build_consensus_generic's docstring. Recorded here, not re-derived
        # from cfg at that call site, so a later config change can't silently
        # desync the two.
        "n_shared_inputs_requested": n_shared_inputs,
        "seed": seed,
    }
