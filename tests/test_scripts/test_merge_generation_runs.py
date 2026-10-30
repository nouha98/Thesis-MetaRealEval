"""scripts/merge_generation_runs.py: a scientific-integrity gate, not a file copy.

Two serving groups generate separately (here: real ``generate_task`` runs with
a fake backend); the merge must refuse every way the union could be wrong and
must leave the sources untouched.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.checkpoint import is_done, task_dir
from meta_real_eval.core.conditions import record_llm_conditions
from meta_real_eval.core.config import Config, LLMModelConfig, SamplingConfig
from meta_real_eval.core.llm_client import InnkubeClient
from meta_real_eval.rq2.generator import generate_task

REPO = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("merge_generation_runs",
                                                  REPO / "scripts" / "merge_generation_runs.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["merge_generation_runs"] = mod
    spec.loader.exec_module(mod)
    return mod


mgr = _load()
TASKS = [SimpleNamespace(task_id=f"HumanEval/{i}", label=f"HumanEval_{i}",
                         prompt=f"def f{i}():\n", entry_point=f"f{i}") for i in (0, 1)]


def _model(mid, temperature=0.7) -> LLMModelConfig:
    return LLMModelConfig(id=mid, sampling=SamplingConfig(temperature=temperature))


A, B = _model("a"), _model("b")


def _cfg(root: Path, name: str, *models, n=2, **rq2) -> Config:
    return Config.model_validate({
        "project": {"output_dir": str(root / name), "mock": False},
        "llm": {"models": [m.model_dump() for m in models], "cache_dir": str(root / f"cache_{name}"),
                "requests_per_minute": 1_000_000},
        "rq2": {"template_relations": [], "n_completions": n, "retry_policy": "transport_only", **rq2},
    })


async def _generate(cfg: Config, responder=None):
    record_llm_conditions(cfg, phase="rq2-generate")
    client = InnkubeClient(cfg.llm, ResponseCache(cfg.llm.cache_dir), mock=False)

    async def fake(model, messages, temperature, max_tokens, n, **kw):
        if responder is not None:
            out = responder(model, messages, n)
            if isinstance(out, BaseException):
                raise out
            return out
        return [f"{model}-{i}" for i in range(n)], ["stop"] * n
    client._call_with_retry = fake
    for t in TASKS:
        await generate_task(t, cfg, client)


async def _two_groups(tmp_path, responder_b=None, cfg_b=None):
    g1 = _cfg(tmp_path, "g1", A)
    g2 = cfg_b or _cfg(tmp_path, "g2", B)
    await _generate(g1)
    await _generate(g2, responder_b)
    comb = _cfg(tmp_path, "comb", A, B)
    return g1, g2, comb


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + p.read_bytes())
    return h.hexdigest()


def _merge(g1, g2, comb, **kw):
    return mgr.merge([Path(g1.project.output_dir), Path(g2.project.output_dir)], comb, ["rq2"],
                     tasks=TASKS, **kw)


async def test_happy_path_unions_models_and_leaves_sources_untouched(tmp_path):
    g1, g2, comb = await _two_groups(tmp_path)
    before = (_tree_hash(Path(g1.project.output_dir)), _tree_hash(Path(g2.project.output_dir)))
    prov = _merge(g1, g2, comb)
    after = (_tree_hash(Path(g1.project.output_dir)), _tree_hash(Path(g2.project.output_dir)))
    assert before == after, "a merge must never modify its sources"

    out = task_dir(comb, "rq2", "HumanEval_0", phase="generate")
    comps = json.loads((out / "completions.json").read_text())
    assert list(comps["original"]) == ["a", "b"], "combined-config model order"
    assert comps["control_resample"]["b"] == ["b-0", "b-1"]
    assert is_done(out)
    manifest = json.loads((Path(comb.project.output_dir) / "llm_conditions.json").read_text())
    assert set(manifest["models"]) == {"a", "b"}
    assert manifest["sessions"][-1]["phase"] == "merge"
    assert len(prov["sources"]) == 2 and all(s["files"] for s in prov["sources"])
    assert (Path(comb.project.output_dir) / "merge_provenance.json").is_file()


async def test_rerunning_the_merge_is_idempotent_but_a_changed_target_is_refused(tmp_path):
    g1, g2, comb = await _two_groups(tmp_path)
    _merge(g1, g2, comb)
    _merge(g1, g2, comb)                      # same content: fine
    out = task_dir(comb, "rq2", "HumanEval_0", phase="generate") / "completions.json"
    data = json.loads(out.read_text())
    data["original"]["a"] = ["tampered", "x"]
    out.write_text(json.dumps(data))
    with pytest.raises(SystemExit, match="exists with different content"):
        _merge(g1, g2, comb)


async def test_the_combined_config_makes_zero_llm_calls_after_a_merge(tmp_path):
    g1, g2, comb = await _two_groups(tmp_path)
    _merge(g1, g2, comb)
    client = InnkubeClient(comb.llm, ResponseCache(comb.llm.cache_dir), mock=False)

    async def boom(*a, **kw):
        raise AssertionError("the combined config called an endpoint")
    client._call_with_retry = boom
    for t in TASKS:
        await generate_task(t, comb, client)

    from meta_real_eval.rq1.runner import _generate_one
    for t in TASKS:
        (task_dir(comb, "rq1", t.label, phase="generate")).mkdir(parents=True, exist_ok=True)
        (task_dir(comb, "rq1", t.label, phase="generate") / "_done.marker").touch()
        await _generate_one(t, comb, client, bench=None)


async def test_different_protocol_settings_are_refused(tmp_path):
    g2 = _cfg(tmp_path, "g2", B, max_tokens=999)
    g1, g2, comb = await _two_groups(tmp_path, cfg_b=g2)
    with pytest.raises(SystemExit, match="protocol settings"):
        _merge(g1, g2, comb)


async def test_a_model_that_ran_other_sampling_than_the_combined_config_is_refused(tmp_path):
    g2 = _cfg(tmp_path, "g2", _model("b", temperature=1.0))
    g1, g2, comb = await _two_groups(tmp_path, cfg_b=g2)
    with pytest.raises(SystemExit, match="the combined config says"):
        _merge(g1, g2, comb)


async def test_overlapping_model_sets_are_refused(tmp_path):
    g2 = _cfg(tmp_path, "g2", A, B)
    g1, g2, comb = await _two_groups(tmp_path, cfg_b=g2)
    with pytest.raises(SystemExit, match="two sources"):
        _merge(g1, g2, comb)


async def test_a_missing_task_is_refused(tmp_path):
    g1, g2, comb = await _two_groups(tmp_path)
    import shutil
    shutil.rmtree(task_dir(g2, "rq2", "HumanEval_1", phase="generate"))
    with pytest.raises(SystemExit, match="HumanEval_1"):
        _merge(g1, g2, comb)


async def test_a_transport_failure_needs_allow_failures_and_is_then_explicit(tmp_path):
    from meta_real_eval.core.llm_client import TransportFailure

    def flaky(model, messages, n):
        if "f1" in json.dumps(messages):
            return TransportFailure("down", [{"attempt": 1, "status": "timeout"}])
        return [f"{model}-{i}" for i in range(n)], ["stop"] * n
    g1, g2, comb = await _two_groups(tmp_path, responder_b=flaky)
    with pytest.raises(SystemExit, match="transport_failure"):
        _merge(g1, g2, comb)
    prov = _merge(g1, g2, comb, allow_failures=True)
    assert prov["failures"]["rq2"]["HumanEval_1"], "the failure must be listed, not dropped"
    out = task_dir(comb, "rq2", "HumanEval_1", phase="generate")
    assert json.loads((out / "completions.json").read_text())["original"]["b"] == []
    assert (out / "generation_failed.json").is_file()


async def test_a_short_cell_is_refused(tmp_path):
    g1, g2, comb = await _two_groups(tmp_path)
    path = task_dir(g2, "rq2", "HumanEval_0", phase="generate") / "completions.json"
    data = json.loads(path.read_text())
    data["original"]["b"] = data["original"]["b"][:1]
    path.write_text(json.dumps(data))
    with pytest.raises(SystemExit, match="1 completions"):
        _merge(g1, g2, comb)


async def test_a_different_logical_prompt_is_refused(tmp_path):
    g1, g2, comb = await _two_groups(tmp_path)
    path = task_dir(g2, "rq2", "HumanEval_0", phase="generate") / "generation_meta.json"
    meta = json.loads(path.read_text())
    meta["original"]["b"]["base_prompt_sha256"] = "0" * 64
    path.write_text(json.dumps(meta))
    with pytest.raises(SystemExit, match="logical prompt differs"):
        _merge(g1, g2, comb)


def _rq1_source(root: Path, cfg: Config, mid: str, failed: bool):
    record_llm_conditions(cfg, phase="rq1-generate")
    for t in TASKS:
        d = task_dir(cfg, "rq1", t.label, phase="generate")
        d.mkdir(parents=True, exist_ok=True)
        mutants = [] if failed else [{"mutant_id": f"LLM-{mid}-0", "operator": "LLM",
                                      "description": "", "code": "x", "source_model": mid}]
        (d / "llm_mutants.json").write_text(json.dumps(mutants))
        (d / "generation_meta.json").write_text(json.dumps({mid: {
            "status": "failed" if failed else "ok",
            "attempts": [{"attempt": 1, "prompt_sha256": f"p-{t.label}"}]}}))
        if failed:
            (d / "generation_failed.json").write_text(json.dumps(
                {"failed_models": [{"model_id": mid, "last_error": "nothing usable"}]}))
        (d / "_done.marker").touch()


def test_rq1_partial_failure_is_refused_unless_allowed_and_lineage_is_kept(tmp_path):
    g1, g2 = _cfg(tmp_path, "g1", A), _cfg(tmp_path, "g2", B)
    _rq1_source(tmp_path, g1, "a", failed=False)
    _rq1_source(tmp_path, g2, "b", failed=True)
    comb = _cfg(tmp_path, "comb", A, B)
    srcs = [Path(g1.project.output_dir), Path(g2.project.output_dir)]
    with pytest.raises(SystemExit, match="no mutants"):
        mgr.merge(srcs, comb, ["rq1"], tasks=TASKS)
    prov = mgr.merge(srcs, comb, ["rq1"], tasks=TASKS, allow_failures=True)
    assert prov["failures"]["rq1"]
    merged = json.loads((task_dir(comb, "rq1", "HumanEval_0", phase="generate")
                         / "llm_mutants.json").read_text())
    assert [m["source_model"] for m in merged] == ["a"]


async def test_a_corpus_variant_a_task_lacks_is_not_a_missing_cell(tmp_path):
    """Gate C removed HumanEval/1's variant: no model generates that cell, and
    the merge expects exactly the relations the generator issued per task."""
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps({
        "manifest": {"families": ["lexical"], "n_per_family": 1},
        "tasks": {"HumanEval/0": {"original": TASKS[0].prompt, "variants": [
                      {"variant_id": "llm_lexical_01", "family": "lexical",
                       "text": "def f0():\n    'reworded'\n"}]},
                  "HumanEval/1": {"original": TASKS[1].prompt, "variants": []}},
    }), encoding="utf-8")
    g1 = _cfg(tmp_path, "g1", A, paraphrase_corpus=str(corpus))
    g2 = _cfg(tmp_path, "g2", B, paraphrase_corpus=str(corpus))
    await _generate(g1)
    await _generate(g2)
    comb = _cfg(tmp_path, "comb", A, B, paraphrase_corpus=str(corpus))
    _merge(g1, g2, comb)
    merged = json.loads((Path(comb.project.output_dir) / "rq2" / "generate" / "HumanEval_1"
                         / "completions.json").read_text(encoding="utf-8"))
    assert "llm_lexical_01" not in merged and set(merged["original"]) == {"a", "b"}
    merged0 = json.loads((Path(comb.project.output_dir) / "rq2" / "generate" / "HumanEval_0"
                          / "completions.json").read_text(encoding="utf-8"))
    assert set(merged0["llm_lexical_01"]) == {"a", "b"}
