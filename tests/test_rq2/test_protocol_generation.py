"""RQ2 with recommended configs: retry policy, control arm, meta, evaluation.

  * transport_only never re-draws a model output (blank / truncated stays);
  * a transport failure leaves a documented empty cell, never a silent one;
  * the control arm keeps the neutral marker; the logical prompt is recorded;
  * a cell with 0 < len < n is never scored.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
from openai import APIStatusError

from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.checkpoint import is_done, task_dir
from meta_real_eval.core.config import Config, LLMModelConfig, SamplingConfig
from meta_real_eval.core.llm_client import InnkubeClient, TransportFailure
from meta_real_eval.rq2.generator import _complete_with_retries, generate_task

TASK = SimpleNamespace(task_id="HumanEval/0", label="HumanEval_0", prompt="def f():\n",
                       entry_point="f")


def _model(mid="m") -> LLMModelConfig:
    return LLMModelConfig(id=mid, sampling=SamplingConfig(temperature=0.7))


def _cfg(tmp_path, *models, n=2, control=True) -> Config:
    cfg = Config.model_validate({
        "project": {"output_dir": str(tmp_path / "results"), "mock": False},
        "llm": {"models": [m.model_dump() for m in models], "cache_dir": str(tmp_path / "cache"),
                "requests_per_minute": 1_000_000},
        "rq2": {"template_relations": [], "include_control_resample": control,
                "n_completions": n, "retry_policy": "transport_only"},
    })
    return cfg


def _client(cfg, responder):
    """``responder(model, messages, n, kw) -> tuple | Exception``; records every call."""
    client = InnkubeClient(cfg.llm, ResponseCache(cfg.llm.cache_dir), mock=False)
    calls: list[dict] = []

    async def fake(model, messages, temperature, max_tokens, n, **kw):
        calls.append({"model": model, "messages": messages, "temperature": temperature, **kw})
        out = responder(model, messages, n, kw)
        if isinstance(out, BaseException):
            raise out
        return out
    client._call_with_retry = fake
    return client, calls


async def test_transport_only_keeps_a_fully_truncated_cell_and_never_redraws(tmp_path):
    cfg = _cfg(tmp_path, _model())
    client, calls = _client(cfg, lambda m, msgs, n, kw: (["cut"] * n, ["length"] * n))
    meta: dict = {}
    completions, error = await _complete_with_retries(
        TASK, "original", "m", [{"role": "user", "content": "q"}], cfg, client, meta_out=meta)
    assert completions == ["cut", "cut"] and error is None
    assert len(calls) == 1, "a truncated model output must not be re-drawn"
    assert meta["status"] == "ok" and meta["finish_reasons"] == ["length", "length"]


async def test_transport_only_keeps_blank_outputs_as_model_outcomes(tmp_path):
    cfg = _cfg(tmp_path, _model())
    client, calls = _client(cfg, lambda m, msgs, n, kw: ([""] * n, ["stop"] * n))
    completions, error = await _complete_with_retries(
        TASK, "original", "m", [{"role": "user", "content": "q"}], cfg, client)
    assert completions == ["", ""] and error is None and len(calls) == 1


async def test_a_transport_failure_leaves_a_documented_empty_cell(tmp_path):
    cfg = _cfg(tmp_path, _model(), control=False)
    attempts = [{"attempt": 1, "status": "timeout", "latency_s": 1.0}]
    client, _ = _client(cfg, lambda *a: TransportFailure("down", attempts))
    await generate_task(TASK, cfg, client)
    out = task_dir(cfg, "rq2", TASK.label, phase="generate")
    assert json.loads((out / "completions.json").read_text())["original"]["m"] == []
    meta = json.loads((out / "generation_meta.json").read_text())["original"]["m"]
    assert meta["status"] == "transport_failure" and meta["transport_attempts"] == attempts
    failed = json.loads((out / "generation_failed.json").read_text())
    assert failed["empty_cells"][0]["status"] == "transport_failure"
    assert not is_done(out), "a task with a missing cell must be picked up again"


async def test_a_context_overflow_is_classified_apart_from_transport(tmp_path):
    cfg = _cfg(tmp_path, _model())
    req = httpx.Request("POST", "http://x/v1/chat/completions")
    err = APIStatusError("This model's maximum context length is 40960 tokens",
                         response=httpx.Response(400, request=req), body=None)
    client, _ = _client(cfg, lambda *a: err)
    meta: dict = {}
    completions, _ = await _complete_with_retries(
        TASK, "original", "m", [{"role": "user", "content": "q"}], cfg, client, meta_out=meta)
    assert completions == [] and meta["status"] == "context_overflow"


async def test_control_keeps_the_marker_and_the_base_prompt_is_shared(tmp_path):
    cfg = _cfg(tmp_path, _model())
    client, calls = _client(cfg, lambda m, msgs, n, kw: (["a"] * n, ["stop"] * n))
    await generate_task(TASK, cfg, client)
    meta = json.loads((task_dir(cfg, "rq2", TASK.label, phase="generate")
                       / "generation_meta.json").read_text())
    ctrl = meta["control_resample"]["m"]
    assert ctrl["control_marker"] is True
    assert ctrl["sent_prompt_sha256"] != ctrl["base_prompt_sha256"]
    assert ctrl["base_prompt_sha256"] == meta["original"]["m"]["base_prompt_sha256"]


async def test_the_profile_temperature_is_what_the_backend_sees(tmp_path):
    cfg = _cfg(tmp_path, _model())
    client = InnkubeClient(cfg.llm, ResponseCache(cfg.llm.cache_dir), mock=False)
    seen = []

    class _Fake:
        def with_options(self, **kw):
            return self
        chat = SimpleNamespace(completions=SimpleNamespace(create=None))

    async def create(**kw):
        seen.append(kw)
        msg = SimpleNamespace(content="x", reasoning_content=None, reasoning=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")] * kw["n"],
                               usage=None, model=kw["model"])
    fake = _Fake()
    fake.chat.completions.create = create
    client._client = fake
    await _complete_with_retries(TASK, "original", "m", [{"role": "user", "content": "q"}],
                                 cfg, client)
    assert seen[0]["temperature"] == 0.7 and cfg.rq2.temperature == 0.8


def test_an_incomplete_cell_is_never_scored(tmp_path):
    from meta_real_eval.benchmarks import get_benchmark
    from meta_real_eval.rq2.evaluator import evaluate_task
    from meta_real_eval.rq2.ranking import _model_pass_at1

    cfg = _cfg(tmp_path, _model("a"), _model("b"), n=3, control=False)
    cfg.execution.cpu_workers = 1
    task = get_benchmark(cfg).load_tasks([0])[0]
    body = task.raw.canonical_solution        # the HumanEval reference body
    gen = task_dir(cfg, "rq2", task.label, phase="generate")
    gen.mkdir(parents=True)
    (gen / "completions.json").write_text(json.dumps(
        {"original": {"a": [body, body, body], "b": [body, body]}}))
    evaluate_task(task, cfg)
    rates = json.loads((task_dir(cfg, "rq2", task.label, phase="evaluate")
                        / "pass_rates.json").read_text())["original"]
    assert rates["a"]["pass@1"] == 1.0 and not rates["a"].get("incomplete")
    assert rates["b"]["incomplete"] is True and rates["b"]["pass@1"] is None
    assert _model_pass_at1({"original": rates}, "original") == {"a": 1.0}
