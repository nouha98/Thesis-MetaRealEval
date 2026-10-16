"""Per-model ``request_params``: the thinking switch, its cache identity, its record.

The invariants that matter:
  * a model with no request_params sends the same request and uses the same
    cache key as before the field existed (every legacy cache entry stays valid);
  * a model WITH request_params gets distinct keys, independent of dict order,
    so a thinking-off run can never be served a thinking-on (or legacy) answer;
  * the params actually reach the request body, as top-level fields;
  * the condition is recorded next to the results and cannot be silently mixed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.conditions import (
    MANIFEST_NAME, ConditionMismatch, record_llm_conditions,
)
from meta_real_eval.core.config import Config, LLMConfig, LLMModelConfig
from meta_real_eval.core.llm_client import InnkubeClient

MSGS = [{"role": "user", "content": "hi"}]
KW = dict(temperature=0.8, max_tokens=1024, n=1)


def _client(tmp_path, *models: LLMModelConfig) -> tuple[InnkubeClient, ResponseCache]:
    cache = ResponseCache(tmp_path / "cache")
    return InnkubeClient(LLMConfig(models=list(models)), cache, mock=False), cache


def _stub_call(client: InnkubeClient) -> None:
    async def fake_call(model, messages, temperature, max_tokens, n):
        return ["answer"], ["stop"], [{"raw_source": "content", "finish_reason": "stop",
                                       "delimiter_found": False, "disposition": "answer"}]
    client._call_with_retry = fake_call


# --- cache identity -------------------------------------------------------

async def test_no_request_params_uses_the_exact_legacy_key(tmp_path):
    client, cache = _client(tmp_path, LLMModelConfig(id="m"))
    _stub_call(client)
    await client.complete_with_meta("m", MSGS, **KW)
    assert cache.get(cache.key("m", MSGS, **KW)) is not None


async def test_a_model_absent_from_llm_models_keeps_the_legacy_key(tmp_path):
    """The paraphrase generator / judge sit outside llm.models."""
    client, cache = _client(tmp_path, LLMModelConfig(id="other", request_params={"x": 1}))
    _stub_call(client)
    await client.complete_with_meta("m", MSGS, **KW)
    assert cache.get(cache.key("m", MSGS, **KW)) is not None


async def test_request_params_never_reuse_the_legacy_entry(tmp_path):
    client, cache = _client(
        tmp_path, LLMModelConfig(id="m", request_params={"reasoning_effort": "none"}))
    _stub_call(client)
    await client.complete_with_meta("m", MSGS, **KW)
    assert cache.get(cache.key("m", MSGS, **KW)) is None, "wrote under the legacy key"
    assert cache.get(cache.key("m", MSGS, **KW,
                               request_params={"reasoning_effort": "none"})) is not None


async def test_a_legacy_cache_entry_is_not_served_to_a_request_params_model(tmp_path):
    client, cache = _client(
        tmp_path, LLMModelConfig(id="m", request_params={"reasoning_effort": "none"}))
    cache.put(cache.key("m", MSGS, **KW), {"choices": ["THINKING-ON ANSWER"]})  # legacy
    _stub_call(client)
    out = await client.complete("m", MSGS, **KW)
    assert out == ["answer"], "served a legacy (server-default) completion as 'thinking off'"


async def test_different_settings_get_different_keys(tmp_path):
    keys = set()
    for params in ({"reasoning_effort": "none"}, {"reasoning_effort": "medium"}, {}):
        client, cache = _client(tmp_path / str(len(keys)),
                                LLMModelConfig(id="m", request_params=params))
        _stub_call(client)
        await client.complete_with_meta("m", MSGS, **KW)
        files = [p.stem for p in (tmp_path / str(len(keys)) / "cache").rglob("*.json")]
        assert len(files) == 1
        keys.add(files[0])
    assert len(keys) == 3


async def test_dict_ordering_does_not_change_the_key(tmp_path):
    a = {"chat_template_kwargs": {"enable_thinking": False, "x": 1}, "reasoning_effort": "none"}
    b = {"reasoning_effort": "none", "chat_template_kwargs": {"x": 1, "enable_thinking": False}}
    keys = []
    for i, params in enumerate((a, b)):
        client, _cache = _client(tmp_path / str(i), LLMModelConfig(id="m", request_params=params))
        _stub_call(client)
        await client.complete_with_meta("m", MSGS, **KW)
        keys.append([p.stem for p in (tmp_path / str(i) / "cache").rglob("*.json")])
    assert keys[0] == keys[1]


# --- the request body -----------------------------------------------------

class _FakeOpenAI:
    def __init__(self):
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(content="ok", reasoning_content=None, reasoning=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")])


async def test_request_params_reach_the_request_as_extra_body(tmp_path):
    client, _ = _client(
        tmp_path, LLMModelConfig(id="m", request_params={"reasoning_effort": "none"}))
    fake = _FakeOpenAI()
    client._client = fake
    await client.complete("m", MSGS, **KW)
    assert fake.calls[0]["extra_body"] == {"reasoning_effort": "none"}
    assert fake.calls[0]["model"] == "m"


async def test_no_request_params_leaves_the_request_exactly_as_before(tmp_path):
    client, _ = _client(tmp_path, LLMModelConfig(id="m"))
    fake = _FakeOpenAI()
    client._client = fake
    await client.complete("m", MSGS, **KW)
    assert "extra_body" not in fake.calls[0]


# --- the recorded condition -----------------------------------------------

def _cfg(tmp_path: Path, *models: LLMModelConfig, mock: bool = False) -> Config:
    return Config.model_validate({
        "project": {"output_dir": str(tmp_path / "out"), "mock": mock},
        "llm": {"models": [m.model_dump() for m in models]},
    })


def test_the_condition_is_recorded_next_to_the_results(tmp_path, monkeypatch):
    monkeypatch.setenv("INNKUBE_BASE_URL", "https://gw.example/")
    monkeypatch.setenv("INNKUBE_API_KEY", "sk-SECRET-VALUE")
    cfg = _cfg(tmp_path, LLMModelConfig(
        id="m", condition="think-off", request_params={"reasoning_effort": "none"}))
    path = record_llm_conditions(cfg)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["models"]["m"] == {"condition": "think-off",
                                   "request_params": {"reasoning_effort": "none"}}
    assert data["endpoint"] == "https://gw.example"
    assert "SECRET" not in text, "the API key must never reach the manifest"


def test_a_conflicting_condition_in_the_same_results_dir_aborts(tmp_path):
    record_llm_conditions(_cfg(tmp_path, LLMModelConfig(
        id="m", request_params={"reasoning_effort": "none"})))
    with pytest.raises(ConditionMismatch, match="one condition per model"):
        record_llm_conditions(_cfg(tmp_path, LLMModelConfig(
            id="m", request_params={"reasoning_effort": "medium"})))


def test_the_same_condition_resumes_and_a_new_model_is_merged(tmp_path):
    a = LLMModelConfig(id="a", request_params={"reasoning_effort": "none"})
    record_llm_conditions(_cfg(tmp_path, a))
    path = record_llm_conditions(_cfg(tmp_path, a, LLMModelConfig(id="b")))
    assert set(json.loads(path.read_text())["models"]) == {"a", "b"}


def test_mock_mode_writes_nothing(tmp_path):
    assert record_llm_conditions(_cfg(tmp_path, LLMModelConfig(id="m"), mock=True)) is None
    assert not (tmp_path / "out" / MANIFEST_NAME).exists()


# --- pilot configs must not drop the switch -------------------------------

def _load_script(name: str):
    root = Path(__file__).resolve().parents[2] / "scripts"
    spec = importlib.util.spec_from_file_location(name, root / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_pilot_config_keeps_the_base_models_request_params():
    mkcfg = _load_script("make_pilot_config")
    base = {"llm": {"models": [
        {"id": "other"},
        {"id": "m", "condition": "think-off", "request_params": {"reasoning_effort": "none"}},
    ]}}
    pilot, _out, _cache = mkcfg.build_pilot(base, "tier1", "m", [0])
    assert pilot["llm"]["models"] == [
        {"id": "m", "condition": "think-off", "request_params": {"reasoning_effort": "none"}}]


def test_pilot_config_for_a_commented_out_model_is_still_just_the_id():
    mkcfg = _load_script("make_pilot_config")
    pilot, _out, _cache = mkcfg.build_pilot({"llm": {"models": [{"id": "x"}]}},
                                            "tier1", "not-listed", [0])
    assert pilot["llm"]["models"] == [{"id": "not-listed"}]
