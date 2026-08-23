"""Build Consistency Assertions from RQ3 divergence signals.

A Consistency Assertion is an oracle-free cross-variant check.  When a task
shows high pairwise divergence (solutions derived from different paraphrases
disagree on shared inputs), the majority output across those solutions is used
as a *pseudo-oracle*: a candidate must reproduce the consensus output on every
input where a majority exists.

This is deliberately **not** ground truth.  H1a therefore measures ranking
recovery *relative to a cross-variant consensus*, not relative to the correct
answer — the pseudo-oracle is built from paraphrase-derived solutions, so a
systematic error shared by a majority of them is invisible to it.  State that
limitation whenever these numbers are reported.

The generated code is appended to the (degraded) test block, so it runs at
module level with the candidate's ``entry_point`` already defined above it and
before ``check(entry_point)`` is called.  A violated assertion therefore fails
the candidate exactly like a benchmark assert would.
"""

from __future__ import annotations

import logging

from ..core.data_loader import HumanEvalTask

logger = logging.getLogger(__name__)

# Used only when rq3.divergence_threshold has not been calibrated yet.  Callers
# record threshold_calibrated=False alongside their results so an uncalibrated
# run is never mistaken for a calibrated one.
DEFAULT_DIVERGENCE_THRESHOLD = 0.1

# Minimum number of reference solutions for a majority to be meaningful.
MIN_REFERENCE_SOLUTIONS = 3


def build_consistency_assertions(
    task: HumanEvalTask,
    divergence_data: dict,
    threshold: float | None,
    max_assertions: int = 20,
) -> tuple[str, int]:
    """Return (code, n_cases): Python asserting the candidate matches the consensus.

    Returns ("", 0) — no augmentation — when any of the following holds:
      * divergence is below the threshold — the solutions already agree, so
        cross-variant checking adds no information;
      * fewer than MIN_REFERENCE_SOLUTIONS reference solutions exist — a
        majority vote is undefined;
      * RQ3 found no input carrying a leave-one-out safe majority.
    """
    rate = divergence_data.get("pairwise_disagreement_rate", 0.0)
    effective_threshold = (
        threshold if threshold is not None else DEFAULT_DIVERGENCE_THRESHOLD
    )

    if rate < effective_threshold:
        return "", 0

    if divergence_data.get("n_solutions", 0) < MIN_REFERENCE_SOLUTIONS:
        return "", 0

    entries = divergence_data.get("consensus", {}).get("entries", [])[:max_assertions]
    if not entries:
        logger.debug("No consensus inputs for %s — no assertions built", task.task_id)
        return "", 0

    ep = task.entry_point
    lines = [
        f"# Consistency assertions for {task.task_id} (majority-vote pseudo-oracle)",
        f"# Divergence rate {rate:.3f} >= threshold {effective_threshold}; "
        f"{len(entries)} consensus input(s)",
        "_ca_cases = [",
    ]
    lines += [
        f"    ({e['args_repr']}, {e['expected_repr']}),  "
        f"# {e['votes']}/{e['n_voters']} votes"
        for e in entries
    ]
    lines += [
        "]",
        "for _ca_args, _ca_expected in _ca_cases:",
        f"    _ca_actual = {ep}(*_ca_args)",
        "    assert _ca_actual == _ca_expected, (",
        "        'Consistency violation on %r: got %r, consensus %r'",
        "        % (_ca_args, _ca_actual, _ca_expected)",
        "    )",
        "",
    ]
    code = "\n".join(lines)

    # Last-resort safety net. This block is prepended to every candidate's test
    # run, so a syntax error here would fail all of them and be indistinguishable
    # from a real augmentation effect. Emitting nothing is the honest fallback.
    try:
        compile(code, "<consistency_assertions>", "exec")
    except SyntaxError:
        logger.warning("Generated assertions for %s do not compile - skipping",
                       task.task_id)
        return "", 0
    return code, len(entries)
