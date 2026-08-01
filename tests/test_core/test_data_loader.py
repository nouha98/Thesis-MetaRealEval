"""The HumanEval corpus must load without network access.

Compute nodes have no route to huggingface.co, so a job that fell back to
``datasets.load_dataset`` died within a second of starting. These tests pin the
offline path: the loader must read a pre-staged file and must never silently
reach the Hub.
"""

import gzip
import json

import pytest

from meta_real_eval.core import data_loader
from meta_real_eval.core.data_loader import (
    CorpusNotFound,
    load_humaneval,
    task_label,
)

ROWS = [
    {
        "task_id": f"HumanEval/{i}",
        "prompt": f"def f{i}():\n",
        "canonical_solution": f"    return {i}\n",
        "test": f"def check(f):\n    assert f() == {i}\n",
        "entry_point": f"f{i}",
    }
    for i in range(5)
]


@pytest.fixture(autouse=True)
def no_hub_fallback(monkeypatch):
    """Any fallback to the network is a test failure, not a silent success."""
    def boom():
        raise AssertionError("load_humaneval reached the network fallback")

    monkeypatch.setattr(data_loader, "_load_rows_from_hub", boom)


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """A small pre-staged corpus, wired up the way SLURM jobs find it."""
    path = tmp_path / "HumanEval.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in ROWS))
    monkeypatch.setenv("MRE_HUMANEVAL_PATH", str(path))
    return path


def test_loads_every_task_from_disk(corpus):
    tasks = load_humaneval()
    assert [t.task_index for t in tasks] == [0, 1, 2, 3, 4]


def test_task_fields_are_populated(corpus):
    task = load_humaneval(tasks=[3])[0]
    assert task.task_id == "HumanEval/3"
    assert task.entry_point == "f3"
    assert task.prompt == "def f3():\n"
    assert task.canonical_solution == "    return 3\n"
    assert "def check" in task.test


def test_subset_filter_sorts_by_index(corpus):
    tasks = load_humaneval(tasks=[4, 1, 0])
    assert [t.task_index for t in tasks] == [0, 1, 4]


def test_unknown_index_raises_actionable_error(corpus):
    with pytest.raises(ValueError, match=r"do not exist"):
        load_humaneval(tasks=[99])


def test_gzipped_corpus_is_read(tmp_path, monkeypatch):
    path = tmp_path / "HumanEval.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for row in ROWS:
            f.write(json.dumps(row) + "\n")
    monkeypatch.setenv("MRE_HUMANEVAL_PATH", str(path))
    assert len(load_humaneval()) == len(ROWS)


def test_task_label_is_filesystem_safe(corpus):
    assert task_label(load_humaneval(tasks=[2])[0]) == "HumanEval_2"


def test_missing_corpus_error_names_the_fix(tmp_path, monkeypatch):
    """The message is what turns a bare SLURM ExitCode 1 into a fixable error."""
    monkeypatch.setenv("MRE_HUMANEVAL_PATH", str(tmp_path / "absent.jsonl"))
    monkeypatch.setattr(data_loader, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(data_loader, "_PACKAGE_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        data_loader, "_load_rows_from_hub",
        lambda: (_ for _ in ()).throw(CorpusNotFound("no internet here")),
    )

    with pytest.raises(CorpusNotFound, match="no internet here"):
        load_humaneval()


def test_real_corpus_is_complete_when_staged():
    """If the corpus has actually been fetched, it must be all 164 tasks."""
    if not any(p.is_file() for p in data_loader.candidate_paths()):
        pytest.skip("corpus not staged; run scripts/fetch_data.py")
    tasks = load_humaneval()
    assert len(tasks) == data_loader.N_HUMANEVAL_TASKS
    assert [t.task_index for t in tasks] == list(range(data_loader.N_HUMANEVAL_TASKS))
