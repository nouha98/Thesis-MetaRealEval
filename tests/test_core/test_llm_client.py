"""Tests for InnkubeClient in mock mode (no real API calls)."""

import asyncio
import pytest
from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.config import LLMConfig, LLMModelConfig
from meta_real_eval.core.llm_client import InnkubeClient


@pytest.fixture
def mock_client(tmp_path):
    cfg = LLMConfig(models=[LLMModelConfig(id="test-model")])
    cache = ResponseCache(tmp_path / "cache")
    return InnkubeClient(cfg, cache, mock=True)


async def test_mock_returns_stubs(mock_client):
    results = await mock_client.complete(
        model="test-model",
        messages=[{"role": "user", "content": "hi"}],
        n=3,
    )
    assert len(results) == 3
    assert all("mock" in r for r in results)


async def test_mock_is_not_cached(mock_client, tmp_path):
    """Mock responses bypass the cache entirely."""
    cache = ResponseCache(tmp_path / "cache")
    key = cache.key("test-model", [{"role": "user", "content": "hi"}], n=1)
    # Nothing should be in cache after a mock call
    await mock_client.complete("test-model", [{"role": "user", "content": "hi"}], n=1)
    assert cache.get(key) is None
