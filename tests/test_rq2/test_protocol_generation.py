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


def _seeded_cfg(tmp_path, seeds=True, markers=None, n=2):
    cfg = _cfg(tmp_path, _model(), n=n)
    cfg.rq2.request_seeds = seeds
    cfg.rq2.control_marker_models = markers
    return cfg


async def test_seeded_control_sends_the_identical_prompt_with_its_own_seed(tmp_path):
    cfg = _seeded_cfg(tmp_path, markers=[])
    client, calls = _client(cfg, lambda m, msgs, n, kw: (["a"] * n, ["stop"] * n))
    await generate_task(TASK, cfg, client)
    orig, ctrl = calls
    assert orig["messages"] == ctrl["messages"], "no marker: byte-identical prompts"
    assert orig["seed"] != ctrl["seed"]
    meta = json.loads((task_dir(cfg, "rq2", TASK.label, phase="generate")
                       / "generation_meta.json").read_text())
    assert meta["control_resample"]["m"]["control_marker"] is False
    assert meta["control_resample"]["m"]["seed"] == ctrl["seed"]
    assert meta["original"]["m"]["sent_prompt_sha256"] == meta["control_resample"]["m"]["sent_prompt_sha256"]


async def test_turning_seeds_off_never_turns_the_marker_back_on(tmp_path):
    cfg = _cfg(tmp_path, _model())
    cfg.rq2.control_marker_models = []
    client, calls = _client(cfg, lambda m, msgs, n, kw: (["a"] * n, ["stop"] * n))
    await generate_task(TASK, cfg, client)
    assert calls[0]["messages"] == calls[1]["messages"]
    assert "seed" not in calls[0] and "seed" not in calls[1]


async def test_the_marker_can_be_kept_for_one_model_only(tmp_path):
    cfg = _cfg(tmp_path, _model("a"), _model("b"))
    cfg.rq2.request_seeds, cfg.rq2.control_marker_models = True, ["a"]
    client, calls = _client(cfg, lambda m, msgs, n, kw: (["x"] * n, ["stop"] * n))
    await generate_task(TASK, cfg, client)
    sent = {(c["model"], i): c["messages"] for i, c in enumerate(calls)}
    by_model = {}
    for (model, _), msgs in sent.items():
        by_model.setdefault(model, []).append(msgs)
    assert by_model["a"][0] != by_model["a"][1], "a keeps the marker on its control arm"
    assert by_model["b"][0] == by_model["b"][1], "b sends the identical prompt"


def test_seed_ranges_of_a_cells_relations_are_disjoint(tmp_path):
    from meta_real_eval.rq2.generator import request_seed
    cfg = _seeded_cfg(tmp_path, n=10)
    cfg.rq2.template_relations = ["persona", "formal", "reorder", "terse"]
    for task_id in ("RealClassEval/csn/snippet_3", "HumanEval/0", "x"):
        for model in ("gemma4-31b-it", "qwen38-27b"):
            ranges = [range(s, s + 10) for s in
                      (request_seed(cfg, task_id, model, r) for r in cfg.rq2.relations)]
            used = [v for rg in ranges for v in rg]
            assert len(used) == len(set(used)), "two relations would share a child seed"
            assert max(used) < 2 ** 31


def test_the_seed_is_stable_across_processes(tmp_path):
    import subprocess
    import sys
    from meta_real_eval.rq2.generator import request_seed
    cfg = _seeded_cfg(tmp_path, n=10)
    here = request_seed(cfg, "HumanEval/0", "m", "control_resample")
    code = ("from meta_real_eval.core.config import Config\n"
            "from meta_real_eval.rq2.generator import request_seed\n"
            "import sys, json\n"
            "cfg = Config.model_validate(json.loads(sys.argv[1]))\n"
            "print(request_seed(cfg, 'HumanEval/0', 'm', 'control_resample'))\n")
    out = subprocess.run([sys.executable, "-c", code, cfg.model_dump_json()],
                         capture_output=True, text=True, check=True,
                         env={**__import__("os").environ, "PYTHONHASHSEED": "123"})
    assert int(out.stdout.strip()) == here


def test_request_seeds_need_the_transport_only_policy():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="request_seeds"):
        Config.model_validate({"llm": {"models": [{"id": "m"}]},
                               "rq2": {"request_seeds": True}})


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


def _evaluate(tmp_path, monkeypatch, cells: dict, crash_on: str | None = None, meta: dict | None = None):
    """Evaluate one HumanEval task in-process (threads, so a patched scorer applies)."""
    import concurrent.futures
    from meta_real_eval.benchmarks import get_benchmark
    from meta_real_eval.rq2 import evaluator

    cfg = _cfg(tmp_path, _model("a"), _model("b"), n=3, control=False)
    task = get_benchmark(cfg).load_tasks([0])[0]
    monkeypatch.setattr(evaluator, "ProcessPoolExecutor", concurrent.futures.ThreadPoolExecutor)
    if crash_on is not None:
        real = evaluator._score_completion

        def scorer(task, completion, cfg, timeout_s):
            if completion == crash_on:
                raise RuntimeError("worker died")
            return real(task, completion, cfg, timeout_s)
        monkeypatch.setattr(evaluator, "_score_completion", scorer)
    body = task.raw.canonical_solution
    gen = task_dir(cfg, "rq2", task.label, phase="generate")
    gen.mkdir(parents=True)
    (gen / "completions.json").write_text(json.dumps(
        {"original": {m: [body if c == "BODY" else c for c in comps] for m, comps in cells.items()}}))
    if meta is not None:
        (gen / "generation_meta.json").write_text(json.dumps(meta))
    evaluator.evaluate_task(task, cfg)
    out = task_dir(cfg, "rq2", task.label, phase="evaluate")
    return json.loads((out / "pass_rates.json").read_text())["original"], is_done(out)


def test_an_evaluation_crash_is_not_a_score_and_leaves_the_task_open(tmp_path, monkeypatch):
    from meta_real_eval.rq2.ranking import _model_pass_at1
    rates, done = _evaluate(tmp_path, monkeypatch, {"a": ["BODY"] * 3, "b": ["BODY", "CRASH", "BODY"]},
                            crash_on="CRASH")
    assert rates["b"]["evaluation_error"] == [1]
    assert rates["b"]["pass@1"] is None and rates["b"]["mean_primary"] is None
    assert rates["b"]["per_completion"] is None, "RQ3 must re-execute, not read crash-as-fail"
    assert not done, "re-running evaluate scores the same completions"
    assert _model_pass_at1({"original": rates}, "original", "mean_primary") == {"a": 1.0}


def test_unusable_output_is_a_counted_zero_and_length_alone_is_never_a_zero(tmp_path, monkeypatch):
    # b's first completion is blank (a cut-off generation): it runs, fails, and
    # stays in the denominator. b's second hit the token cap but still holds a
    # complete answer: it is scored by its tests like any other.
    meta = {"original": {"b": {"records": [{"finish_reason": "length"}, {"finish_reason": "length"},
                                           {"finish_reason": "stop"}]}}}
    rates, done = _evaluate(tmp_path, monkeypatch, {"a": ["BODY"] * 3, "b": ["", "BODY", "BODY"]},
                            meta=meta)
    assert done
    assert rates["b"]["n"] == 3 and rates["b"]["correct"] == 2
    assert rates["b"]["per_completion"] == [False, True, True]
    assert rates["b"]["mean_primary"] == 2 / 3, "the blank one is a 0 in the graded mean too"
