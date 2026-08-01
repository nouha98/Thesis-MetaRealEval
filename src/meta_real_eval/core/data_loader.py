"""HumanEval dataset loader.

Compute nodes on this cluster have no outbound internet, so a HuggingFace
``load_dataset`` call fails within a second of a job starting. The corpus is
therefore pre-staged on the login node (``scripts/fetch_data.py``) and read
off /shared at job time.

Resolution order:

1. ``$MRE_HUMANEVAL_PATH`` — explicit override (.jsonl or .jsonl.gz)
2. ``<repo>/data/HumanEval.jsonl[.gz]`` — what ``scripts/fetch_data.py`` writes
3. ``<package>/data/HumanEval.jsonl[.gz]`` — if vendored into the package
4. HuggingFace ``datasets`` — last-resort fallback, requires network
"""

from __future__ import annotations

import gzip
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]

N_HUMANEVAL_TASKS = 164
DEFAULT_CORPUS_PATH = _REPO_ROOT / "data" / "HumanEval.jsonl.gz"

_FETCH_HINT = (
    "Pre-stage it on the login node (which has internet) with:\n"
    "         .venv/bin/python scripts/fetch_data.py\n"
    "       or point MRE_HUMANEVAL_PATH at an existing HumanEval.jsonl."
)


@dataclass
class HumanEvalTask:
    task_id: str           # "HumanEval/42"
    task_index: int        # 42
    prompt: str            # function signature + docstring
    canonical_solution: str
    test: str              # check() function block
    entry_point: str       # function name


class CorpusNotFound(RuntimeError):
    """The HumanEval corpus is available neither on disk nor from the Hub."""


def candidate_paths() -> list[Path]:
    """Local corpus locations, in priority order."""
    candidates: list[Path] = []

    override = os.environ.get("MRE_HUMANEVAL_PATH")
    if override:
        candidates.append(Path(override))

    for root in (_REPO_ROOT / "data", Path.cwd() / "data", _PACKAGE_ROOT / "data"):
        candidates.append(root / "HumanEval.jsonl")
        candidates.append(root / "HumanEval.jsonl.gz")

    return candidates


def _read_jsonl(path: Path) -> Iterator[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _load_rows_from_disk() -> Optional[list[dict]]:
    for path in candidate_paths():
        if path.is_file():
            logger.debug("Loading HumanEval from %s", path)
            return list(_read_jsonl(path))
    return None


def _load_rows_from_hub() -> list[dict]:
    """Download the corpus. Only works where there is outbound internet."""
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise CorpusNotFound(
            "HumanEval is not on disk and the 'datasets' package is not "
            "installed, so it cannot be downloaded.\n       " + _FETCH_HINT
        ) from e

    try:
        ds = load_dataset("openai/openai_humaneval", split="test")
    except Exception as e:
        raise CorpusNotFound(
            f"HumanEval is not on disk and the download failed "
            f"({type(e).__name__}: {e}).\n"
            "       Compute nodes have no internet access. " + _FETCH_HINT
        ) from e

    return [dict(item) for item in ds]


def load_humaneval(tasks: Optional[list[int]] = None) -> list[HumanEvalTask]:
    """Load HumanEval tasks.

    Parameters
    ----------
    tasks:
        If None, all 164 tasks are loaded. Otherwise only the task indices
        in the list are returned.  Example: tasks=[0, 1, 10] for a pilot.

    Raises
    ------
    ValueError
        If an explicitly requested task index does not exist.
    CorpusNotFound
        If the corpus can be found neither on disk nor on the Hub.
    """
    rows = _load_rows_from_disk()
    if rows is None:
        rows = _load_rows_from_hub()

    wanted = set(tasks) if tasks is not None else None

    result: list[HumanEvalTask] = []
    for item in rows:
        idx = int(item["task_id"].split("/")[1])
        if wanted is not None and idx not in wanted:
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

    if wanted is not None:
        missing = sorted(wanted - {t.task_index for t in result})
        if missing:
            raise ValueError(
                f"HumanEval task index/indices {missing} do not exist "
                f"(valid range 0..{len(rows) - 1}). Check --task-index and the "
                "SLURM --array range."
            )

    result.sort(key=lambda t: t.task_index)
    return result


def task_label(task: HumanEvalTask) -> str:
    """Filesystem-safe label, e.g. 'HumanEval_42'."""
    return task.task_id.replace("/", "_")


def fetch_corpus(dest: Path = DEFAULT_CORPUS_PATH) -> int:
    """Download the corpus and write it as gzipped JSONL. Returns the row count.

    Run on a node with internet access; see ``scripts/fetch_data.py``.
    """
    rows = _load_rows_from_hub()
    dest.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if dest.suffix == ".gz" else open
    with opener(dest, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return len(rows)
