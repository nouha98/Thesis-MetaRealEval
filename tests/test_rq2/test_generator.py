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
# Truncation is an infrastructure failure, not a wrong answer. A completion cut
# off at the token cap is non-empty, so the blankness check waves it through and
# the model is scored 0 for a budget shortfall. Measured on the recorded corpus:
# qwen36-35b routes its answer through a reasoning field and every stored
# completion sat at the 1024-token cap.
# ---------------------------------------------------------------------------

def test_every_completion_truncated_is_not_real():
    assert _has_real_completion(["partial", "partial"], ["length", "length"]) is False


def test_a_partially_truncated_cell_still_counts():
    """Some completions finished; those are real answers and must be kept."""
    assert _has_real_completion(["done", "partial"], ["stop", "length"]) is True


def test_missing_finish_reasons_falls_back_to_the_blankness_check():
    """An old cache entry has no finish reasons; it must stay usable."""
    assert _has_real_completion(["def f(): return 1"], None) is True
    assert _has_real_completion(["def f(): return 1"], []) is True


async def test_a_fully_truncated_attempt_is_retried(tmp_path):
    client, remaining = _client_with_fake_backend(tmp_path, [
        (["cut off mid-thou"], ["length"]),
        (["def f(): return 1"], ["stop"]),
    ])
    cfg = Config()
    task = SimpleNamespace(task_id="HumanEval/0")

    completions, error = await _complete_with_retries(
        task, "original", "m", [{"role": "user", "content": "hi"}], cfg, client,
    )

    assert completions == ["def f(): return 1"]
    assert error is None
    assert remaining == [], "the truncated attempt should have triggered a real retry"


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

    Each entry is either a plain list of completion strings (finish reasons
    default to "stop") or an explicit ``(completions, finish_reasons)`` pair,
    matching what ``_call_with_retry`` returns.
    """
    cfg = LLMConfig(models=[LLMModelConfig(id="m")], cache_dir=tmp_path / "cache")
    client = InnkubeClient(cfg, ResponseCache(tmp_path / "cache"), mock=False)
    remaining = list(responses)

    async def fake_call_with_retry(model, messages, temperature, max_tokens, n):
        entry = remaining.pop(0)
        if isinstance(entry, tuple):
            return entry
        return entry, ["stop"] * len(entry)

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


# ---------------------------------------------------------------------------
# --only-model must MERGE. generate_task builds `results` from scratch and
# writes completions.json wholesale, so regenerating one model by narrowing
# llm.models would silently delete every other model's completions -- an
# irreversible loss of data that costs hours of API budget to reproduce.
# ---------------------------------------------------------------------------

async def _run_generate_task(tmp_path, cfg, task, responses, only_model):
    from meta_real_eval.rq2.generator import generate_task

    client, _ = _client_with_fake_backend(tmp_path, responses)
    await generate_task(task, cfg, client, only_model=only_model)


def _two_model_cfg(tmp_path):
    cfg = Config()
    cfg.project.output_dir = tmp_path / "results"
    cfg.llm.models = [LLMModelConfig(id="keep-me"), LLMModelConfig(id="redo-me")]
    cfg.llm.cache_dir = tmp_path / "cache"
    cfg.rq2.template_relations = []
    cfg.rq2.include_control_resample = False
    cfg.rq2.n_completions = 1
    return cfg


async def test_only_model_preserves_the_other_models_completions(tmp_path):
    import json as _json

    from meta_real_eval.core.checkpoint import task_dir

    cfg = _two_model_cfg(tmp_path)
    task = SimpleNamespace(task_id="HumanEval/0", prompt="def f():\n", entry_point="f")
    out = task_dir(cfg, "rq2", "HumanEval_0", phase="generate")
    out.mkdir(parents=True, exist_ok=True)
    (out / "completions.json").write_text(_json.dumps({
        "original": {"keep-me": ["ORIGINAL KEEP"], "redo-me": ["STALE"]},
    }))

    await _run_generate_task(tmp_path, cfg, task, [["FRESH"]], only_model="redo-me")

    merged = _json.loads((out / "completions.json").read_text())
    assert merged["original"]["keep-me"] == ["ORIGINAL KEEP"], "untouched model was clobbered"
    assert merged["original"]["redo-me"] == ["FRESH"], "target model was not regenerated"


async def test_only_model_rejects_a_model_outside_the_config(tmp_path):
    import pytest

    cfg = _two_model_cfg(tmp_path)
    task = SimpleNamespace(task_id="HumanEval/0", prompt="def f():\n", entry_point="f")

    with pytest.raises(SystemExit):
        await _run_generate_task(tmp_path, cfg, task, [], only_model="not-a-model")


async def test_a_plain_run_still_writes_every_configured_model(tmp_path):
    """No --only-model: behaviour is unchanged, both models are generated."""
    import json as _json

    from meta_real_eval.core.checkpoint import task_dir

    cfg = _two_model_cfg(tmp_path)
    task = SimpleNamespace(task_id="HumanEval/0", prompt="def f():\n", entry_point="f")

    await _run_generate_task(tmp_path, cfg, task, [["A"], ["B"]], only_model=None)

    out = task_dir(cfg, "rq2", "HumanEval_0", phase="generate")
    written = _json.loads((out / "completions.json").read_text())
    assert set(written["original"]) == {"keep-me", "redo-me"}


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
