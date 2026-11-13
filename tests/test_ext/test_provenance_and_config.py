"""core/provenance.py and the extension config overlay."""

import json
from pathlib import Path

import pytest
import yaml

from meta_real_eval.core import provenance
from meta_real_eval.core.conditions import protocol_settings
from meta_real_eval.core.config import Config, load_yaml_with_base

REPO = Path(__file__).resolve().parents[2]


def test_digest_is_order_independent_and_lists_missing(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("1"), b.write_text("2")
    d1 = provenance.digest_files([a, b, tmp_path / "nope"])
    d2 = provenance.digest_files([b, a])
    assert d1["digest"] == d2["digest"] and d1["n_files"] == 2 and len(d1["missing"]) == 1


def test_verify_pins(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    sha = provenance.file_sha256(f)
    assert provenance.verify_pins({str(f): sha}) == {str(f): "ok"}
    assert provenance.verify_pins({str(tmp_path / "gone"): sha}) == {str(tmp_path / "gone"): "missing"}
    with pytest.raises(provenance.PinMismatch):
        provenance.verify_pins({str(tmp_path / "gone"): sha}, require_all=True)
    with pytest.raises(provenance.PinMismatch):
        provenance.verify_pins({str(f): "0" * 64})


def test_run_manifest_records_inputs_and_the_base_config(tmp_path):
    base = tmp_path / "base.yaml"
    base.write_text("project:\n  seed: 1\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("base_config: base.yaml\nproject:\n  seed: 2\n")
    inp = tmp_path / "in.json"
    inp.write_text("{}")
    path = provenance.write_run_manifest(tmp_path / "out", stage="test", config_path=overlay,
                                         inputs={"x": inp}, seeds={"s": 3}, argv=["prog"])
    m = json.loads(path.read_text())
    assert m["stage"] == "test" and m["seeds"] == {"s": 3} and m["inputs"]["x"]["n_files"] == 1
    assert m["config"]["base"]["sha256"] == provenance.file_sha256(base)
    assert "commit" in m["git"] and "untracked_code_files" in m["git"]
    hashes = json.loads((tmp_path / "out" / provenance.INPUT_HASHES_NAME).read_text())
    assert list(hashes["x"].values()) == [provenance.file_sha256(inp)]


def test_overlay_merges_mappings_and_replaces_lists(tmp_path):
    (tmp_path / "base.yaml").write_text("rq4:\n  degradation_levels: [0.0, 0.5]\nproject:\n  seed: 1\n  mock: true\n")
    (tmp_path / "o.yaml").write_text("base_config: base.yaml\nrq4:\n  degradation_levels: [0.0]\nproject:\n  seed: 7\n")
    data = load_yaml_with_base(tmp_path / "o.yaml")
    assert data == {"rq4": {"degradation_levels": [0.0]}, "project": {"seed": 7, "mock": True}}
    (tmp_path / "self.yaml").write_text("base_config: self.yaml\n")
    with pytest.raises(ValueError):
        load_yaml_with_base(tmp_path / "self.yaml")


@pytest.mark.parametrize("name", ["default.yaml", "tier2_realclasseval.yaml"])
def test_historical_configs_load_exactly_as_before(name):
    path = REPO / "config" / name
    before = Config.model_validate(yaml.safe_load(path.read_text()) or {})
    after = Config.from_yaml(path)
    assert after == before and after.extensions is None
    assert "extensions" not in protocol_settings(after)


def test_extension_config_overlays_tier2_without_changing_its_protocol():
    base = Config.from_yaml(REPO / "config" / "tier2_realclasseval.yaml")
    ext = Config.from_yaml(REPO / "config" / "tier2_extensions.yaml")
    assert ext.extensions is not None
    assert ext.llm == base.llm and ext.rq2 == base.rq2 and ext.rq3 == base.rq3 and ext.benchmark == base.benchmark
    assert ext.project.output_dir != base.project.output_dir
    assert len(ext.extensions.development_tasks) == 24 == len(set(ext.extensions.development_tasks))
    s_base, s_ext = protocol_settings(base), protocol_settings(ext)
    assert {k: v for k, v in s_ext.items() if k != "extensions"} == s_base
    assert s_ext["extensions"]["protocol_version"] == "rev8"


def test_extension_pins_hold():
    ext = Config.from_yaml(REPO / "config" / "tier2_extensions.yaml")
    status = provenance.verify_pins(ext.extensions.pins)
    assert status["config/tier2_realclasseval.yaml"] == "ok"
