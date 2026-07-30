"""HumanEval dataset loader."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class HumanEvalTask:
    task_id: str           # "HumanEval/42"
    task_index: int        # 42
    prompt: str            # function signature + docstring
    canonical_solution: str
    test: str              # check() function block
    entry_point: str       # function name


def load_humaneval(tasks: Optional[list[int]] = None) -> list[HumanEvalTask]:
    """Load HumanEval tasks from HuggingFace datasets.

    Parameters
    ----------
    tasks:
        If None, all 164 tasks are loaded. Otherwise only the task indices
        in the list are returned.  Example: tasks=[0, 1, 10] for a pilot.
    """
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError("Install the 'datasets' package: pip install datasets") from e

    ds = load_dataset("openai_humaneval", split="test", trust_remote_code=True)

    result: list[HumanEvalTask] = []
    for item in ds:
        idx = int(item["task_id"].split("/")[1])
        if tasks is not None and idx not in tasks:
            continue
        result.append(
            HumanEvalTask(
                task_id=item["task_id"],
                task_index=idx,
                prompt=item["prompt"],
                canonical_solution=item["canonical_solution"],
                test=item["test"],
                entry_point=item["entry_point"],
            )
        )

    result.sort(key=lambda t: t.task_index)
    return result


def task_label(task: HumanEvalTask) -> str:
    """Filesystem-safe label, e.g. 'HumanEval_42'."""
    return task.task_id.replace("/", "_")
