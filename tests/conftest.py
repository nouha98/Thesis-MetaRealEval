"""Shared pytest fixtures."""

import pytest
from meta_real_eval.core.data_loader import HumanEvalTask


@pytest.fixture
def simple_task() -> HumanEvalTask:
    """A minimal HumanEval-like task for testing without network access."""
    return HumanEvalTask(
        task_id="HumanEval/0",
        task_index=0,
        prompt='def add(a: int, b: int) -> int:\n    """Return a + b."""\n',
        canonical_solution="    return a + b\n",
        test='def check(candidate):\n    assert candidate(1, 2) == 3\n    assert candidate(-1, 1) == 0\n',
        entry_point="add",
    )


@pytest.fixture
def config(tmp_path):
    """Minimal config with output_dir pointing to a temp directory."""
    from meta_real_eval.core.config import Config, ProjectConfig, LLMConfig, LLMModelConfig
    cfg = Config()
    cfg.project.output_dir = tmp_path / "results"
    cfg.project.mock = True
    cfg.llm.cache_dir = tmp_path / "cache"
    return cfg
