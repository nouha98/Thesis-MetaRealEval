"""Tests for RQ2's per-cell completion generation."""

from types import SimpleNamespace

from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.config import Config, LLMConfig, LLMModelConfig
from meta_real_eval.core.llm_client import InnkubeClient
from meta_real_eval.rq2.generator import _complete_with_retries, _has_real_completion


# ---------------------------------------------------------------------------
# Regression: `if completions:` only checked that the list was non-empty, so
# a model returning n blank strings (see test_llm_client.py's _message_text
# tests for how that happens) was accepted as n genuine samples instead of
# triggering the retry-then-generation_failed.json path the module's own
# docstring describes.
# ---------------------------------------------------------------------------

def test_all_blank_completions_are_not_real():
    assert _has_real_completion(["", "", ""]) is False


def test_all_whitespace_completions_are_not_real():
    assert _has_real_completion(["   ", "\n\t", ""]) is False


def test_empty_list_is_not_real():
    assert _has_real_completion([]) is False


def test_at_least_one_real_completion_counts():
    assert _has_real_completion(["", "def f(): return 1", ""]) is True


def test_all_real_completions_count():
    assert _has_real_completion(["a", "b", "c"]) is True


# ---------------------------------------------------------------------------
# Regression: a retry that reuses the caller's cache_salt unchanged is not a
# retry at all. InnkubeClient.complete() caches unconditionally, including a
# blank result, so attempt 2 with the same (model, messages, temperature,
# max_tokens, n, cache_salt) tuple as attempt 1 hits that cached blank result
# and never reaches the network -- confirmed empirically: with a fixed salt,
# 3 configured attempts made exactly 1 real API call.
# ---------------------------------------------------------------------------

def _client_with_fake_backend(tmp_path, responses):
    """An InnkubeClient whose network call is replaced by a canned sequence.

    ``responses`` is popped from the front on each real call (never on a
    cache hit), so the length actually consumed is the count of genuine API
    calls -- exactly what this regression needs to measure.
    """
    cfg = LLMConfig(models=[LLMModelConfig(id="m")], cache_dir=tmp_path / "cache")
    client = InnkubeClient(cfg, ResponseCache(tmp_path / "cache"), mock=False)
    remaining = list(responses)

    async def fake_call_with_retry(model, messages, temperature, max_tokens, n):
        return remaining.pop(0)

    client._call_with_retry = fake_call_with_retry
    return client, remaining


async def test_retry_after_a_blank_attempt_makes_a_real_second_call(tmp_path):
    client, remaining = _client_with_fake_backend(
        tmp_path, [["", "", ""], ["def f(): return 1"]],
    )
    cfg = Config()
    task = SimpleNamespace(task_id="HumanEval/0")
    messages = [{"role": "user", "content": "hi"}]

    completions, error = await _complete_with_retries(
        task, "original", "m", messages, cfg, client, cache_salt=None,
    )

    assert completions == ["def f(): return 1"]
    assert error is None
    assert remaining == [], "both canned responses were consumed by real calls"


async def test_all_attempts_blank_makes_max_attempts_real_calls(tmp_path):
    from meta_real_eval.rq2.generator import MAX_GENERATE_ATTEMPTS
    client, remaining = _client_with_fake_backend(
        tmp_path, [["", "", ""]] * MAX_GENERATE_ATTEMPTS,
    )
    cfg = Config()
    task = SimpleNamespace(task_id="HumanEval/0")
    messages = [{"role": "user", "content": "hi"}]

    completions, error = await _complete_with_retries(
        task, "original", "m", messages, cfg, client, cache_salt=None,
    )

    assert completions == []
    assert error is not None
    assert remaining == [], f"expected all {MAX_GENERATE_ATTEMPTS} attempts to make a real call"


async def test_a_successful_first_attempt_keeps_the_caller_supplied_salt(tmp_path):
    """The fix must not touch caching for the common case (no retry needed) --
    only a genuine retry should get a modified salt."""
    client, remaining = _client_with_fake_backend(
        tmp_path, [["def f(): return 1"]],
    )
    cfg = Config()
    task = SimpleNamespace(task_id="HumanEval/0")
    messages = [{"role": "user", "content": "hi"}]

    completions, _ = await _complete_with_retries(
        task, "control_resample", "m", messages, cfg, client,
        cache_salt="control_resample",
    )
    assert completions == ["def f(): return 1"]

    # A second, independent call with the exact same inputs must be a cache
    # hit (same salt as attempt 1 above), not a second real call.
    client2, remaining2 = _client_with_fake_backend(tmp_path, [])
    completions2, _ = await _complete_with_retries(
        task, "control_resample", "m", messages, cfg, client2,
        cache_salt="control_resample",
    )
    assert completions2 == ["def f(): return 1"]
