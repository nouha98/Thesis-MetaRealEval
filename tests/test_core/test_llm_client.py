"""Tests for InnkubeClient in mock mode (no real API calls)."""

import asyncio
import pytest
from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.config import LLMConfig, LLMModelConfig
from types import SimpleNamespace

from meta_real_eval.core.llm_client import InnkubeClient, _message_text, _strip_reasoning


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


# ---------------------------------------------------------------------------
# Reasoning-model hygiene
# ---------------------------------------------------------------------------
#
# Some models on the Innkube endpoint write their chain-of-thought inline in
# `message.content`, closed by a literal </think> tag, instead of the separate
# `reasoning_content` field (confirmed live: soofi-s-isar-preview does this).
# Left unstripped, every caller — pass@1 execution, paraphrase validation,
# mutant extraction — would silently treat 10-30KB of deliberation as the
# answer. This is applied inside InnkubeClient._call_with_retry, upstream of
# every caller, rather than patched into each one separately.

def test_strip_reasoning_removes_a_closed_think_block():
    assert _strip_reasoning("blah blah</think>\nfinal answer") == "\nfinal answer"


def test_strip_reasoning_keeps_only_text_after_the_last_tag():
    assert _strip_reasoning("a</think>b</think>c") == "c"


def test_strip_reasoning_is_a_no_op_without_a_closing_tag():
    # An unclosed <think> (truncated by max_tokens) is left alone rather than
    # guessed at — there is no reliable place to cut it.
    assert _strip_reasoning("<think>still reasoning, never closed") == (
        "<think>still reasoning, never closed"
    )


def test_strip_reasoning_is_a_no_op_for_plain_content():
    assert _strip_reasoning("return a + b") == "return a + b"


# ---------------------------------------------------------------------------
# _message_text
# ---------------------------------------------------------------------------
#
# Regression: qwen36-35b puts its entire answer in `reasoning_content`
# instead of `content`, per the comment above _THINK_BLOCK_RE. Reading only
# `message.content` (the old behaviour) silently returned "" for every one
# of its completions -- confirmed live via results/model_check, where the
# API call reports status "OK" but every extracted mutant has code: "".

def test_message_text_prefers_content_when_present():
    message = SimpleNamespace(content="return a + b", reasoning_content="ignored")
    assert _message_text(message) == "return a + b"


def test_message_text_falls_back_to_reasoning_content_when_content_is_blank():
    message = SimpleNamespace(content="", reasoning_content="def f():\n    return 1\n")
    assert _message_text(message) == "def f():\n    return 1\n"


def test_message_text_falls_back_when_content_is_whitespace_only():
    message = SimpleNamespace(content="   \n", reasoning_content="the real answer")
    assert _message_text(message) == "the real answer"


def test_message_text_handles_missing_reasoning_content_attribute():
    """A model with neither field populated (pydantic's model_extra omits an
    attribute the API never sent) must not raise -- just report no text."""
    message = SimpleNamespace(content=None)
    assert _message_text(message) == ""


def test_message_text_handles_reasoning_content_being_none():
    message = SimpleNamespace(content="", reasoning_content=None)
    assert _message_text(message) == ""


# ---------------------------------------------------------------------------
# finish_reason plumbing. A completion truncated at the token cap is non-empty,
# so callers cannot tell it from a wrong answer unless the reason survives the
# cache round-trip. Entries written before finish reasons were recorded must
# stay readable -- an old cache is worth keeping, but it must not be mistaken
# for a run of clean stops.
# ---------------------------------------------------------------------------

async def test_finish_reasons_survive_the_cache_round_trip(tmp_path):
    from meta_real_eval.core.cache import ResponseCache
    from meta_real_eval.core.config import LLMConfig
    from meta_real_eval.core.llm_client import InnkubeClient

    cache = ResponseCache(tmp_path)
    client = InnkubeClient(LLMConfig(), cache, mock=False)

    async def fake_call(model, messages, temperature, max_tokens, n):
        return ["cut off"], ["length"]

    client._call_with_retry = fake_call
    messages = [{"role": "user", "content": "hi"}]

    first, reasons = await client.complete_with_meta("m", messages)
    assert (first, reasons) == (["cut off"], ["length"])

    # Second call is served from cache; the reason must come back with it.
    client._call_with_retry = None          # any real call would now raise
    cached, cached_reasons = await client.complete_with_meta("m", messages)
    assert (cached, cached_reasons) == (["cut off"], ["length"])


async def test_a_pre_finish_reason_cache_entry_reports_unknown(tmp_path):
    from meta_real_eval.core.cache import ResponseCache
    from meta_real_eval.core.config import LLMConfig
    from meta_real_eval.core.llm_client import InnkubeClient

    cache = ResponseCache(tmp_path)
    client = InnkubeClient(LLMConfig(), cache, mock=False)
    messages = [{"role": "user", "content": "hi"}]

    # Exactly what the old code wrote: choices, no finish_reasons.
    key = cache.key("m", messages, temperature=0.8, max_tokens=1024, n=1)
    cache.put(key, {"choices": ["def f(): return 1"]})

    completions, reasons = await client.complete_with_meta(
        "m", messages, temperature=0.8, max_tokens=1024, n=1,
    )
    assert completions == ["def f(): return 1"]
    assert reasons == ["unknown"], "an unrecorded reason must not read as 'stop'"


async def test_complete_still_returns_plain_strings(tmp_path):
    """The narrow wrapper keeps every existing call site working unchanged."""
    from meta_real_eval.core.cache import ResponseCache
    from meta_real_eval.core.config import LLMConfig
    from meta_real_eval.core.llm_client import InnkubeClient

    client = InnkubeClient(LLMConfig(), ResponseCache(tmp_path), mock=False)

    async def fake_call(model, messages, temperature, max_tokens, n):
        return ["answer"], ["stop"]

    client._call_with_retry = fake_call
    out = await client.complete("m", [{"role": "user", "content": "hi"}])
    assert out == ["answer"]
