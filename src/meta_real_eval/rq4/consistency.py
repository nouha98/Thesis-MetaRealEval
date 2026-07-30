"""Build Consistency Assertions from RQ3 divergence signals.

A Consistency Assertion is an oracle-free cross-variant check: if a task
shows high pairwise divergence (solutions from different paraphrases disagree
on shared inputs), we generate an assertion that all solutions must agree
on a fresh set of random inputs.

The generated assertion code is injected as additional tests into the
MT-augmented test suite used in RQ4.
"""

from __future__ import annotations

import logging

from ..core.data_loader import HumanEvalTask
from ..stage0.equivalence import _generate_inputs

logger = logging.getLogger(__name__)


def build_consistency_assertions(
    task: HumanEvalTask,
    divergence_data: dict,
    threshold: float | None,
    n_inputs: int = 50,
    seed: int = 42,
) -> str:
    """Return Python code that asserts cross-solution output consistency.

    If divergence is below threshold (or threshold is None), returns an empty
    string (no augmentation needed).

    The generated code assumes that all solution functions are named with a
    suffix (_sol0, _sol1, ...) and are defined in the same namespace.
    """
    rate = divergence_data.get("pairwise_disagreement_rate", 0.0)
    effective_threshold = threshold if threshold is not None else 0.1

    if rate < effective_threshold:
        return ""  # solutions agree sufficiently; no assertions needed

    n_solutions = divergence_data.get("n_solutions", 0)
    if n_solutions < 2:
        return ""

    inputs = _generate_inputs(task, n_inputs, seed)

    lines = [
        f"# Consistency Assertions for {task.task_id}",
        f"# Divergence rate: {rate:.3f} (threshold: {effective_threshold})",
        "def _check_consistency(*fns):",
        "    import itertools",
    ]

    input_reprs = [repr(inp) for inp in inputs[:20]]  # embed up to 20 inputs
    lines.append(f"    _inputs = {input_reprs}")
    lines += [
        "    for args in _inputs:",
        "        outputs = [f(*args) for f in fns]",
        "        for a, b in itertools.combinations(outputs, 2):",
        "            assert a == b, f'Consistency violation: {a!r} != {b!r} on {args!r}'",
    ]
    lines.append("")
    return "\n".join(lines)
