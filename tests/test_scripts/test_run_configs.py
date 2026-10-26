"""scripts/make_run_configs.py: one config per serving group + the combined target."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from meta_real_eval.core.config import Config

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("make_run_configs", REPO / "scripts" / "make_run_configs.py")
mrc = importlib.util.module_from_spec(spec)
sys.modules["make_run_configs"] = mrc
spec.loader.exec_module(mrc)

BASE = yaml.safe_load((REPO / "config" / "tier2_realclasseval.yaml").read_text(encoding="utf-8"))


def _write(tmp_path, *args) -> dict[str, Config]:
    mrc.main(["--out-dir", str(tmp_path), *args])
    return {p.stem: Config.from_yaml(p) for p in tmp_path.glob("*.yaml")}


def test_groups_partition_the_models_and_combined_has_them_all(tmp_path):
    cfgs = _write(tmp_path)
    assert cfgs["full_innkube"].model_ids() == ["gemma4-31b-it"]
    assert cfgs["full_vllm-qwen38"].model_ids() == ["qwen38-27b"]
    assert cfgs["full_vllm-qwen3-next"].model_ids() == ["qwen3-next-80b-a3b-instruct"]
    assert cfgs["full_vllm-qwen36"].model_ids() == ["qwen36-35b"]
    assert cfgs["full_combined"].model_ids() == [m["id"] for m in BASE["llm"]["models"]]


def test_model_entries_and_protocol_are_the_base_verbatim(tmp_path):
    cfgs = _write(tmp_path)
    base = Config.model_validate(BASE)
    for cfg in cfgs.values():
        for m in cfg.llm.models:
            assert m == base.llm.model(m.id)
        assert cfg.rq2 == base.rq2 and cfg.rq1 == base.rq1 and cfg.benchmark == base.benchmark


def test_every_group_has_its_own_dirs_and_vllm_gets_server_client_limits(tmp_path):
    cfgs = _write(tmp_path)
    outs = {c.project.output_dir.as_posix() for c in cfgs.values()}
    caches = {c.llm.cache_dir.as_posix() for c in cfgs.values()}
    assert len(outs) == len(caches) == 5
    assert cfgs["full_vllm-qwen36"].llm.max_concurrent_requests == 16
    assert cfgs["full_innkube"].llm.max_concurrent_requests == BASE["llm"]["max_concurrent_requests"]


def test_a_pilot_needs_its_own_label(tmp_path):
    with pytest.raises(SystemExit, match="label"):
        _write(tmp_path, "--tasks", "1,2")
    cfgs = _write(tmp_path, "--tasks", "1,2,8", "--label", "pilot")
    assert cfgs["pilot_combined"].benchmark.tasks == [1, 2, 8]
    assert "pilot" in cfgs["pilot_combined"].project.output_dir.parts
