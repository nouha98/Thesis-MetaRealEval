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


# ---------------------------------------------------------------------------
# Choice classification: provenance + the conservative reasoning-field rule.
#
# `finish_reason == "stop"` does not make reasoning-field text an answer (a
# finished reasoning trace may contain none), so that text is accepted only when
# a closing </think> is followed by non-empty text. Everything else is blanked
# and recorded as unusable. Raw-response facts (raw_source, finish_reason,
# delimiter_found) are kept apart from the decision (disposition).
# ---------------------------------------------------------------------------

from meta_real_eval.core.llm_client import _classify_choice  # noqa: E402


def _msg(content=None, reasoning_content=None, reasoning=None):
    return SimpleNamespace(content=content, reasoning_content=reasoning_content, reasoning=reasoning)


def _assert_record(record, source, finish, delimiter, disposition):
    assert record == {
        "raw_source": source,
        "finish_reason": finish,
        "delimiter_found": delimiter,
        "disposition": disposition,
    }


def test_classify_plain_content_is_an_answer():
    text, rec = _classify_choice(_msg(content="return a + b"), "stop")
    assert text == "return a + b"
    _assert_record(rec, "content", "stop", False, "answer")


def test_classify_content_with_closed_think_strips_up_to_last_tag():
    text, rec = _classify_choice(_msg(content="a</think>b</think>final"), "stop")
    assert text == "final"
    _assert_record(rec, "content", "stop", True, "answer")


def test_classify_content_cut_at_the_token_cap_keeps_text_but_is_flagged():
    """Existing scoring is unchanged (text kept); the record says truncated."""
    text, rec = _classify_choice(_msg(content="def f():\n    ret"), "length")
    assert text == "def f():\n    ret"
    _assert_record(rec, "content", "length", False, "truncated")


def test_classify_content_with_unclosed_think_is_left_alone():
    text, rec = _classify_choice(_msg(content="<think>still going"), "stop")
    assert text == "<think>still going"
    _assert_record(rec, "content", "stop", False, "answer")


def test_classify_reasoning_only_with_stop_and_no_boundary_is_unusable():
    """A reasoning trace that ended normally is NOT thereby an answer."""
    text, rec = _classify_choice(_msg(content="", reasoning_content="Let me think. So the answer is..."), "stop")
    assert text == ""
    _assert_record(rec, "reasoning_field", "stop", False, "unusable_ambiguous")


def test_classify_reasoning_only_with_length_is_unusable_truncated():
    text, rec = _classify_choice(_msg(content="", reasoning_content="Let me think about"), "length")
    assert text == ""
    _assert_record(rec, "reasoning_field", "length", False, "unusable_truncated")


def test_classify_reasoning_field_with_closing_tag_and_answer_is_accepted():
    text, rec = _classify_choice(
        _msg(content="", reasoning_content="thinking...</think>\ndef f(): return 1"), "stop")
    assert text == "\ndef f(): return 1"
    _assert_record(rec, "reasoning_field", "stop", True, "answer")


def test_classify_reasoning_field_with_closing_tag_but_no_text_after_is_unusable():
    text, rec = _classify_choice(_msg(content="", reasoning_content="thinking...</think>  \n"), "stop")
    assert text == ""
    _assert_record(rec, "reasoning_field", "stop", True, "unusable_ambiguous")


def test_classify_reasoning_field_answer_cut_by_length_is_flagged_truncated():
    text, rec = _classify_choice(_msg(content="", reasoning_content="x</think>def f():\n  re"), "length")
    assert text == "def f():\n  re"
    _assert_record(rec, "reasoning_field", "length", True, "truncated")


def test_classify_reads_the_newer_reasoning_field_name_too():
    text, rec = _classify_choice(_msg(content="", reasoning="why</think>ans"), "stop")
    assert text == "ans"
    assert rec["raw_source"] == "reasoning_field"


def test_classify_nothing_returned_is_empty():
    text, rec = _classify_choice(_msg(content=None), "stop")
    assert text == ""
    _assert_record(rec, "none", "stop", False, "empty")


def test_classify_missing_finish_reason_reads_unknown_not_stop():
    _text, rec = _classify_choice(_msg(content="x"), None)
    assert rec["finish_reason"] == "unknown"


async def test_records_survive_the_cache_round_trip(tmp_path):
    client = InnkubeClient(LLMConfig(), ResponseCache(tmp_path), mock=False)
    rec = {"raw_source": "content", "finish_reason": "stop",
           "delimiter_found": False, "disposition": "answer"}

    async def fake_call(model, messages, temperature, max_tokens, n):
        return ["ok"], ["stop"], [rec]

    client._call_with_retry = fake_call
    messages = [{"role": "user", "content": "hi"}]
    first = await client.complete_with_records("m", messages)
    assert first == (["ok"], [rec])

    client._call_with_retry = None          # any real call would now raise
    assert await client.complete_with_records("m", messages) == (["ok"], [rec])
    # The two-value API is unchanged.
    assert await client.complete_with_meta("m", messages) == (["ok"], ["stop"])


async def test_a_pre_records_cache_entry_reports_unknown_not_reconstructed(tmp_path):
    cache = ResponseCache(tmp_path)
    client = InnkubeClient(LLMConfig(), cache, mock=False)
    messages = [{"role": "user", "content": "hi"}]
    key = cache.key("m", messages, temperature=0.8, max_tokens=1024, n=1)
    cache.put(key, {"choices": ["x"], "finish_reasons": ["stop"]})   # pre-records shape

    completions, records = await client.complete_with_records(
        "m", messages, temperature=0.8, max_tokens=1024, n=1)
    assert completions == ["x"]
    _assert_record(records[0], "unknown", "stop", None, "unknown")


async def test_a_two_tuple_call_double_still_works_and_has_unknown_records(tmp_path):
    """Existing test doubles return (choices, finish_reasons) only."""
    client = InnkubeClient(LLMConfig(), ResponseCache(tmp_path), mock=False)

    async def fake_call(model, messages, temperature, max_tokens, n):
        return ["a"], ["stop"]

    client._call_with_retry = fake_call
    _c, records = await client.complete_with_records("m", [{"role": "user", "content": "q"}])
    assert records[0]["disposition"] == "unknown"
