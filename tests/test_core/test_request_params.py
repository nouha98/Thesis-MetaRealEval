"""Per-model recommended sampling + request_params: request, cache key, transport, record.

The invariants that matter:
  * a model with no profile sends the same request, uses the same cache key and
    keeps the same retry behaviour as before (every legacy cache entry stays
    valid; Tier 1 is unchanged);
  * an instrument call (use_profile=False) is a legacy request whatever the
    model's profile;
  * a profiled model's key carries its sampling/request_params, so a
    recommended-config run is never served an old T=0.8 response;
  * the values reach the request where the backend reads them;
  * profiled requests retry transport failures with the same request and record
    every attempt; missing telemetry is None, never 0;
  * the configuration is recorded next to the results and cannot be mixed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError, APITimeoutError
from pydantic import ValidationError

from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.conditions import MANIFEST_NAME, ConditionMismatch, record_llm_conditions
from meta_real_eval.core.config import Config, LLMConfig, LLMModelConfig, SamplingConfig
from meta_real_eval.core.llm_client import InnkubeClient, TransportFailure, resolve_request

MSGS = [{"role": "user", "content": "hi"}]
KW = dict(temperature=0.8, max_tokens=1024, n=1)
REC = dict(temperature=0.6, top_p=0.95, top_k=20, min_p=0.0,
           presence_penalty=0.0, repetition_penalty=1.0)


def _profiled(mid="m", **over) -> LLMModelConfig:
    fields = dict(id=mid, sampling=SamplingConfig(**REC))
    fields.update(over)
    return LLMModelConfig(**fields)


def _client(tmp_path, *models: LLMModelConfig, **llm) -> tuple[InnkubeClient, ResponseCache]:
    cache = ResponseCache(tmp_path / "cache")
    cfg = LLMConfig(models=list(models), retry_base_delay_s=0.0, **llm)
    return InnkubeClient(cfg, cache, mock=False), cache


def _stub_call(client: InnkubeClient) -> None:
    async def fake_call(model, messages, temperature, max_tokens, n, **_kw):
        return ["answer"], ["stop"], [{"raw_source": "content", "finish_reason": "stop",
                                       "delimiter_found": False, "disposition": "answer"}]
    client._call_with_retry = fake_call


def _cache_files(root: Path) -> list[str]:
    return [p.stem for p in (root / "cache").rglob("*.json")]


# --- cache identity -------------------------------------------------------

async def test_no_profile_uses_the_exact_legacy_key(tmp_path):
    client, cache = _client(tmp_path, LLMModelConfig(id="m"))
    _stub_call(client)
    await client.complete_with_meta("m", MSGS, **KW)
    assert cache.get(cache.key("m", MSGS, **KW)) is not None


async def test_a_model_absent_from_llm_models_keeps_the_legacy_key(tmp_path):
    """The paraphrase generator / judge sit outside llm.models."""
    client, cache = _client(tmp_path, _profiled("other"))
    _stub_call(client)
    await client.complete_with_meta("m", MSGS, **KW)
    assert cache.get(cache.key("m", MSGS, **KW)) is not None


async def test_request_params_only_keeps_the_committed_key_shape(tmp_path):
    client, cache = _client(tmp_path, LLMModelConfig(id="m", request_params={"reasoning_effort": "none"}))
    _stub_call(client)
    await client.complete_with_meta("m", MSGS, **KW)
    assert cache.get(cache.key("m", MSGS, **KW)) is None, "wrote under the legacy key"
    assert cache.get(cache.key("m", MSGS, **KW,
                               request_params={"reasoning_effort": "none"})) is not None


async def test_a_profiled_key_carries_the_sampling_and_its_temperature(tmp_path):
    client, cache = _client(tmp_path, _profiled())
    _stub_call(client)
    await client.complete_with_meta("m", MSGS, **KW)
    want = {**KW, "temperature": 0.6, "sampling": SamplingConfig(**REC).resolved()}
    assert cache.get(cache.key("m", MSGS, **want)) is not None


async def test_a_legacy_cache_entry_is_not_served_to_a_profiled_model(tmp_path):
    client, cache = _client(tmp_path, _profiled())
    cache.put(cache.key("m", MSGS, **KW), {"choices": ["OLD T=0.8 ANSWER"]})  # legacy
    _stub_call(client)
    assert await client.complete("m", MSGS, **KW) == ["answer"]


async def test_different_profiles_get_different_keys(tmp_path):
    variants = [_profiled(), _profiled(sampling=SamplingConfig(**{**REC, "top_k": 21})),
                _profiled(request_params={"reasoning_effort": "none"}), LLMModelConfig(id="m")]
    keys = set()
    for i, m in enumerate(variants):
        client, _ = _client(tmp_path / str(i), m)
        _stub_call(client)
        await client.complete_with_meta("m", MSGS, **KW)
        keys.update(_cache_files(tmp_path / str(i)))
    assert len(keys) == len(variants)


async def test_instrument_call_on_a_profiled_model_is_a_legacy_request(tmp_path):
    client, cache = _client(tmp_path, _profiled())
    _stub_call(client)
    await client.complete("m", MSGS, **KW, use_profile=False)
    assert cache.get(cache.key("m", MSGS, **KW)) is not None


# --- the request body -----------------------------------------------------

class _FakeOpenAI:
    """Records every create() call; replies from a script of outcomes."""

    def __init__(self, outcomes=None, n_choices=None, usage=None):
        self.calls: list[dict] = []
        self.options: list[dict] = []
        self._outcomes = list(outcomes or [])
        self._n_choices = n_choices
        self._usage = usage
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def with_options(self, **kw):
        self.options.append(kw)
        return self

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._outcomes:
            outcome = self._outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
        n = self._n_choices if self._n_choices is not None else kwargs["n"]
        msg = SimpleNamespace(content="ok", reasoning_content=None, reasoning=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")] * n,
                               usage=self._usage, model=kwargs["model"])


def _status_error(code: int) -> APIStatusError:
    req = httpx.Request("POST", "http://gw/v1/chat/completions")
    return APIStatusError(f"HTTP {code}", response=httpx.Response(code, request=req), body=None)


def _timeout() -> APITimeoutError:
    return APITimeoutError(request=httpx.Request("POST", "http://gw/v1/chat/completions"))


async def test_recommended_values_reach_the_request_where_the_backend_reads_them(tmp_path):
    client, _ = _client(tmp_path, _profiled(request_params={"reasoning_effort": "none"}))
    fake = _FakeOpenAI()
    client._client = fake
    await client.complete("m", MSGS, **KW)
    call = fake.calls[0]
    assert call["temperature"] == 0.6, "the model's temperature overrides the caller's"
    assert call["top_p"] == 0.95 and call["presence_penalty"] == 0.0
    assert call["extra_body"] == {"top_k": 20, "min_p": 0.0, "repetition_penalty": 1.0,
                                  "reasoning_effort": "none"}


async def test_no_profile_leaves_the_request_exactly_as_before(tmp_path):
    client, _ = _client(tmp_path, LLMModelConfig(id="m"))
    fake = _FakeOpenAI()
    client._client = fake
    await client.complete("m", MSGS, **KW)
    assert fake.calls[0] == {"model": "m", "messages": MSGS, **KW}
    assert fake.options == [], "legacy requests keep the SDK's own retry settings"


async def test_instrument_call_sends_the_legacy_body(tmp_path):
    client, _ = _client(tmp_path, _profiled())
    fake = _FakeOpenAI()
    client._client = fake
    await client.complete("m", MSGS, temperature=0.3, max_tokens=256, n=1, use_profile=False)
    assert fake.calls[0] == {"model": "m", "messages": MSGS, "temperature": 0.3,
                             "max_tokens": 256, "n": 1}


def test_resolve_request_without_profile_has_no_extra_body():
    cfg = LLMConfig(models=[LLMModelConfig(id="m")])
    req = resolve_request(cfg, "m", temperature=0.8, max_tokens=10, n=2)
    assert not req.profiled and req.extra == {}
    assert req.key_params == {"temperature": 0.8, "max_tokens": 10, "n": 2}


# --- validation -------------------------------------------------------------

@pytest.mark.parametrize("bad", [{"top_p": 0.0}, {"top_p": 1.5}, {"top_k": 0}, {"top_k": -2},
                                 {"min_p": 1.5}, {"temperature": -0.1},
                                 {"presence_penalty": 3.0}, {"repetition_penalty": 0.0}])
def test_out_of_range_sampling_is_rejected(bad):
    with pytest.raises(ValidationError):
        SamplingConfig(**bad)


@pytest.mark.parametrize("params", [{"top_k": 5}, {"temperature": 1.0}, {"max_tokens": 9}])
def test_request_params_may_not_smuggle_client_fields(params):
    with pytest.raises(ValidationError, match="may not set"):
        LLMModelConfig(id="m", request_params=params)


def test_transport_only_policy_needs_a_profile_for_every_model():
    with pytest.raises(ValidationError, match="sampling profile"):
        Config.model_validate({"llm": {"models": [{"id": "m"}]},
                               "rq2": {"retry_policy": "transport_only"}})


# --- transport handling and telemetry ---------------------------------------

async def test_profiled_request_retries_transport_failures_with_the_same_request(tmp_path):
    client, _ = _client(tmp_path, _profiled())
    fake = _FakeOpenAI(outcomes=[_status_error(408), _timeout(), _status_error(503)])
    client._client = fake
    res = await client.complete_detailed("m", MSGS, **KW)
    assert res.choices == ["ok"]
    assert len(fake.calls) == 4 and all(c == fake.calls[0] for c in fake.calls)
    assert [a["status"] for a in res.meta["attempts"]] == ["http_408", "timeout", "http_503", "ok"]
    assert res.meta["total_latency_s"] >= res.meta["success_latency_s"]
    assert fake.options[0]["max_retries"] == 0, "SDK retries off so every attempt is recorded"


async def test_a_wrong_number_of_choices_is_a_transport_failure(tmp_path):
    client, _ = _client(tmp_path, _profiled(), retry_max_attempts=2)
    client._client = _FakeOpenAI(n_choices=3)
    with pytest.raises(TransportFailure) as info:
        await client.complete("m", MSGS, temperature=0.8, max_tokens=10, n=5)
    assert [a["status"] for a in info.value.attempts] == ["choice_count", "choice_count"]


async def test_legacy_request_still_raises_408_and_timeouts_at_once(tmp_path):
    client, _ = _client(tmp_path, LLMModelConfig(id="m"))
    fake = _FakeOpenAI(outcomes=[_status_error(408)])
    client._client = fake
    with pytest.raises(APIStatusError):
        await client.complete("m", MSGS, **KW)
    assert len(fake.calls) == 1
    client2, _ = _client(tmp_path / "b", LLMModelConfig(id="m"))
    client2._client = _FakeOpenAI(outcomes=[_timeout()])
    with pytest.raises(APITimeoutError):
        await client2.complete("m", MSGS, **KW)


async def test_missing_usage_is_none_not_zero(tmp_path):
    client, _ = _client(tmp_path, _profiled())
    client._client = _FakeOpenAI(usage=None)
    res = await client.complete_detailed("m", MSGS, **KW)
    assert res.meta["usage"] is None and res.meta["reasoning_tokens"] is None
    assert res.meta["choices"] == [{"answer_chars": 2, "reasoning_field_chars": None}]


async def test_reported_reasoning_tokens_are_kept_and_meta_survives_the_cache(tmp_path):
    usage = SimpleNamespace(model_dump=lambda: {
        "completion_tokens": 40, "prompt_tokens": 5, "total_tokens": 45,
        "completion_tokens_details": {"reasoning_tokens": 30}})
    client, _ = _client(tmp_path, _profiled())
    fake = _FakeOpenAI(usage=usage)
    client._client = fake
    first = await client.complete_detailed("m", MSGS, **KW)
    assert first.meta["reasoning_tokens"] == 30 and first.meta["cache_hit"] is False
    again = await client.complete_detailed("m", MSGS, **KW)
    assert len(fake.calls) == 1 and again.meta["cache_hit"] is True
    assert again.meta["usage"] == first.meta["usage"]


async def test_request_timeout_is_passed_to_the_sdk(tmp_path):
    client, _ = _client(tmp_path, LLMModelConfig(id="m"), request_timeout_s=1234)
    fake = _FakeOpenAI()
    client._client = fake
    await client.complete("m", MSGS, **KW)
    assert fake.options == [{"timeout": 1234}]


# --- the recorded configuration -----------------------------------------------

def _cfg(tmp_path: Path, *models: LLMModelConfig, mock: bool = False, **rq2) -> Config:
    return Config.model_validate({
        "project": {"output_dir": str(tmp_path / "out"), "mock": mock},
        "llm": {"models": [m.model_dump() for m in models]},
        "rq2": {"template_relations": [], **rq2},
    })


def test_the_configuration_is_recorded_next_to_the_results(tmp_path, monkeypatch):
    monkeypatch.setenv("INNKUBE_BASE_URL", "https://gw.example/")
    monkeypatch.setenv("INNKUBE_API_KEY", "sk-SECRET-VALUE")
    m = _profiled()
    path = record_llm_conditions(_cfg(tmp_path, m), phase="rq2-generate")
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["models"]["m"] == m.effective_condition()
    assert data["sessions"][0]["endpoint"] == "https://gw.example"
    assert data["settings"]["n_completions"] == 10
    assert "SECRET" not in text, "the API key must never reach the manifest"


def test_a_conflicting_profile_in_the_same_results_dir_aborts(tmp_path):
    record_llm_conditions(_cfg(tmp_path, _profiled()))
    with pytest.raises(ConditionMismatch, match="one configuration"):
        record_llm_conditions(_cfg(tmp_path, _profiled(sampling=SamplingConfig(temperature=1.0))))


def test_changed_settings_abort_but_a_resume_appends_a_session(tmp_path, monkeypatch):
    a = _profiled("a")
    record_llm_conditions(_cfg(tmp_path, a))
    monkeypatch.setenv("INNKUBE_BASE_URL", "http://127.0.0.1:9002")      # ports are not compared
    path = record_llm_conditions(_cfg(tmp_path, a, LLMModelConfig(id="b")))
    data = json.loads(path.read_text())
    assert set(data["models"]) == {"a", "b"} and len(data["sessions"]) == 2
    with pytest.raises(ConditionMismatch, match="protocol settings"):
        record_llm_conditions(_cfg(tmp_path, a, n_completions=3))


def test_mock_mode_writes_nothing(tmp_path):
    assert record_llm_conditions(_cfg(tmp_path, LLMModelConfig(id="m"), mock=True)) is None
    assert not (tmp_path / "out" / MANIFEST_NAME).exists()


# --- pilot configs must not drop the profile ------------------------------

def _load_script(name: str):
    root = Path(__file__).resolve().parents[2] / "scripts"
    spec = importlib.util.spec_from_file_location(name, root / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_pilot_config_keeps_the_base_models_profile():
    mkcfg = _load_script("make_pilot_config")
    entry = {"id": "m", "request_params": {"reasoning_effort": "none"},
             "sampling": {"temperature": 0.6, "top_k": 20}}
    base = {"llm": {"models": [{"id": "other"}, entry]}}
    pilot, _out, _cache = mkcfg.build_pilot(base, "tier1", "m", [0])
    assert pilot["llm"]["models"] == [entry]


def test_pilot_config_for_a_commented_out_model_is_still_just_the_id():
    mkcfg = _load_script("make_pilot_config")
    pilot, _out, _cache = mkcfg.build_pilot({"llm": {"models": [{"id": "x"}]}},
                                            "tier1", "not-listed", [0])
    assert pilot["llm"]["models"] == [{"id": "not-listed"}]
