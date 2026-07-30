"""Tests for the disk response cache."""

import json
import pytest
from meta_real_eval.core.cache import ResponseCache


def test_miss_returns_none(tmp_path):
    cache = ResponseCache(tmp_path / "cache")
    key = cache.key("model-a", [{"role": "user", "content": "hi"}])
    assert cache.get(key) is None


def test_put_then_get(tmp_path):
    cache = ResponseCache(tmp_path / "cache")
    key = cache.key("model-a", [{"role": "user", "content": "hello"}])
    data = {"choices": ["response text"]}
    cache.put(key, data)
    assert cache.get(key) == data


def test_key_is_deterministic(tmp_path):
    cache = ResponseCache(tmp_path / "cache")
    msgs = [{"role": "user", "content": "hello"}]
    k1 = cache.key("m", msgs, temperature=0.8, n=10)
    k2 = cache.key("m", msgs, temperature=0.8, n=10)
    assert k1 == k2


def test_different_params_give_different_keys(tmp_path):
    cache = ResponseCache(tmp_path / "cache")
    msgs = [{"role": "user", "content": "hello"}]
    k1 = cache.key("m", msgs, temperature=0.8)
    k2 = cache.key("m", msgs, temperature=0.5)
    assert k1 != k2


def test_corrupt_file_is_cleaned(tmp_path):
    cache = ResponseCache(tmp_path / "cache")
    key = cache.key("m", [{"role": "user", "content": "x"}])
    path = cache._path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid json")
    assert cache.get(key) is None
    assert not path.exists()
