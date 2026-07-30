"""RQ2 evaluate phase: execute completions against the test suite and compute Pass@k.

Pass@k uses the unbiased estimator from Chen et al. 2021 (HumanEval paper):

    pass@k = 1 - C(n-c, k) / C(n, k)

where n = total samples, c = correct samples.
"""

from __future__ import annotations

import logging
import math
import re
from concurrent.futures import ProcessPoolExecutor, as_completed

from ..core.checkpoint import is_done, mark_done, task_dir, write_json, read_json
from ..core.config import Config
from ..core.data_loader import HumanEvalTask, task_label
from ..core.sandbox import execute

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pass@k estimator
# ---------------------------------------------------------------------------

def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator.  Returns 1.0 if n - c < k."""
    if n == 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - math.prod((n - c - i) / (n - i) for i in range(k))


# ---------------------------------------------------------------------------
# Code extraction
# ---------------------------------------------------------------------------

def _extract_function_body(raw: str, entry_point: str) -> str:
    """Extract the function body from a model completion.

    Models may return:
    - just the body (indented lines)
    - a full function definition
    - markdown-fenced code
    """
    # Strip markdown
    fenced = re.search(r"```(?:python)?\s*(.*?)```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1)

    # If it contains `def entry_point(`, return from that line onward
    match = re.search(rf"def\s+{re.escape(entry_point)}\s*\(", raw)
    if match:
        # Find the function body indented block
        func_block = raw[match.start():]
        return func_block

    # Otherwise assume it's already just the body
    return raw


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _run_completion(
    completion: str,
    task_prompt: str,
    test_code: str,
    entry_point: str,
    timeout_s: float,
) -> bool:
    """Return True if the completion passes the test."""
    body = _extract_function_body(completion, entry_point)

    # If model returned only a body (no def line), prepend the prompt
    if not re.match(r"\s*def\s+", body):
        solution_code = task_prompt + body
    else:
        solution_code = body

    test = test_code + f"\ncheck({entry_point})\n"
    result = execute(solution_code, test, timeout_s=timeout_s)
    return result.passed


def evaluate_task(task: HumanEvalTask, cfg: Config) -> None:
    """Evaluate cached completions for one task and write pass rates."""
    label = task_label(task)
    out = task_dir(cfg, "rq2", label, phase="evaluate")

    if is_done(out):
        logger.info("SKIP evaluate %s", label)
        return

    gen_out = task_dir(cfg, "rq2", label, phase="generate")
    try:
        completions_data: dict = read_json(gen_out, "completions.json")
    except FileNotFoundError:
        logger.error("Missing generate output for %s — run rq2 generate first", label)
        return

    pass_rates: dict[str, dict[str, dict]] = {}

    for relation, model_completions in completions_data.items():
        pass_rates[relation] = {}
        for model_id, completions in model_completions.items():
            correct = 0
            n = len(completions)
            with ProcessPoolExecutor(max_workers=cfg.execution.cpu_workers) as pool:
                futures = [
                    pool.submit(
                        _run_completion,
                        comp,
                        task.prompt,
                        task.test,
                        task.entry_point,
                        cfg.execution.timeout_s,
                    )
                    for comp in completions
                ]
                for f in as_completed(futures):
                    try:
                        if f.result():
                            correct += 1
                    except Exception:
                        pass

            pass_rates[relation][model_id] = {
                "n": n,
                "correct": correct,
                "pass@1":  pass_at_k(n, correct, 1),
                "pass@5":  pass_at_k(n, correct, 5),
                "pass@10": pass_at_k(n, correct, 10),
            }
            logger.debug("  %s / %s / %s: pass@1=%.3f",
                         label, relation, model_id,
                         pass_rates[relation][model_id]["pass@1"])

    write_json(out, "pass_rates.json", pass_rates)
    mark_done(out)
    logger.info("Evaluated %s", label)
