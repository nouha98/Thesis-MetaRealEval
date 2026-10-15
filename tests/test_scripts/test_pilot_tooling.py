"""Focused tests for the vLLM pilot tooling (scripts/, not the library).

Covers: the host / container preflight split, the pilot config's isolation
guarantees, the report's funnel semantics, and the exact Apptainer / `vllm serve`
argument arrays the Slurm job builds. Nothing here needs a GPU, vLLM, Apptainer
or the cluster.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


feas = _load("vllm_feasibility")
mkcfg = _load("make_pilot_config")
report = _load("pilot_report")


# ---------------------------------------------------------------------------
# Preflight: host mode
# ---------------------------------------------------------------------------

def _model_dir(tmp_path, *, heads=64, kv=8, experts=None, shard_bytes=1 << 20, quant=None):
    d = tmp_path / "model"
    d.mkdir()
    cfg = {"architectures": ["Qwen3MoeForCausalLM"], "model_type": "qwen3_moe", "torch_dtype": "bfloat16",
           "num_hidden_layers": 4, "num_attention_heads": heads, "num_key_value_heads": kv,
           "head_dim": 128, "hidden_size": 4096}
    if experts:
        cfg["num_experts"] = experts
    if quant:
        cfg["quantization_config"] = {"quant_method": quant}
    (d / "config.json").write_text(json.dumps(cfg))
    (d / "model-00001.safetensors").write_bytes(b"\0" * shard_bytes)
    return d


def _run_feas(model_dir, tmp_path, *args):
    out = tmp_path / "feas.json"
    with pytest.raises(SystemExit) as exc:
        feas.main([str(model_dir), "--no-hash", "--out", str(out), *args])
    return exc.value.code, json.loads(out.read_text())


def test_host_mode_does_not_need_vllm_and_marks_support_checks_not_checked(tmp_path):
    code, rep = _run_feas(_model_dir(tmp_path), tmp_path, "--gpus", "2", "--tp", "2")
    assert (code, rep["status"], rep["mode"]) == (0, "PREFLIGHT_PASSED", "host")
    sup = rep["support_checks"]
    for key in ("architecture_supported", "quantization", "reasoning_parsers_available"):
        assert sup[key].startswith("NOT CHECKED on the host")
    assert rep["runtime_verdict"].startswith("NOT_RUN")


def test_host_mode_blocks_tp_greater_than_gpus(tmp_path):
    code, rep = _run_feas(_model_dir(tmp_path), tmp_path, "--gpus", "1", "--tp", "2")
    assert code == 2 and any("tensor_parallel_size=2 > gpus=1" in b for b in rep["blockers"])


def test_host_mode_blocks_tp_that_does_not_divide_heads(tmp_path):
    code, rep = _run_feas(_model_dir(tmp_path, heads=64, kv=8), tmp_path, "--gpus", "3", "--tp", "3")
    assert code == 2 and any("not divisible by tp=3" in b for b in rep["blockers"])


def test_host_mode_blocks_when_weights_exceed_estimated_capacity(tmp_path):
    code, rep = _run_feas(_model_dir(tmp_path, shard_bytes=2 << 20), tmp_path,
                          "--gpus", "1", "--tp", "1", "--gpu-gib", "0.001")
    assert code == 2 and any(b.startswith("ESTIMATE:") for b in rep["blockers"])


def test_host_mode_blocks_when_no_weights_found(tmp_path):
    d = _model_dir(tmp_path)
    (d / "model-00001.safetensors").unlink()
    code, rep = _run_feas(d, tmp_path)
    assert code == 2 and any("no weight shards" in b for b in rep["blockers"])


# ---------------------------------------------------------------------------
# Preflight: container mode (verdict logic on constructed facts)
# ---------------------------------------------------------------------------

def _facts(*, detected=2, free=70.0, weights=40.0, arch=None, quant="none", parser="none", cuda=True, vllm="0.17.0"):
    art = {"n_shards": 1}
    env = {"vllm": vllm, "cuda_available": cuda, "gpu_count_detected": detected,
           "gpus_detected": [{"index": i, "name": "A100", "total_gib": 80.0, "free_gib": free} for i in range(detected)]}
    est = {"tensor_parallel_size": 2, "gpus": 2, "headroom_gib": 100.0, "weights_gib": weights,
           "usable_gib": 144.0, "gpu_memory_utilization": 0.9}
    sup = {"tp_necessary_conditions": "ok", "architecture_supported": arch if arch is not None else {"Qwen3MoeForCausalLM": True},
           "quantization": quant, "requested_reasoning_parser": parser}
    return art, env, est, sup


def _verdict(**kw):
    art, env, est, sup = _facts(**kw)
    return feas.verdict(art, env, est, sup, "container", 2)


def test_container_mode_passes_when_everything_checks_out():
    assert _verdict() == ("PREFLIGHT_PASSED", [])


def test_container_mode_blocks_when_vllm_not_importable():
    status, blockers = _verdict(vllm="NOT AVAILABLE (ModuleNotFoundError)")
    assert status == "PREFLIGHT_BLOCKED" and any("not importable inside the container" in b for b in blockers)


def test_container_mode_blocks_unregistered_architecture_quant_and_parser():
    _, b1 = _verdict(arch={"Qwen3NextForCausalLM": False})
    _, b2 = _verdict(quant={"fp8": False})
    _, b3 = _verdict(parser={"qwen3": False})
    assert any("architecture not registered" in b for b in b1)
    assert any("quantisation method not supported" in b for b in b2)
    assert any("reasoning parser not available" in b for b in b3)


def test_container_mode_unknown_support_is_not_a_blocker():
    """A listing API that does not exist is 'unknown', decided later by the smoke test."""
    status, _ = _verdict(arch="UNKNOWN: AttributeError", parser="qwen3 (availability UNKNOWN)")
    assert status == "PREFLIGHT_PASSED"


def test_container_mode_blocks_without_visible_gpu_or_on_count_mismatch():
    _, b_nogpu = _verdict(detected=0, cuda=False)
    _, b_count = _verdict(detected=1)
    assert any("no CUDA GPU visible inside the container" in b for b in b_nogpu)
    assert any("GPUs visible inside the container (1) != requested --gpus (2)" in b for b in b_count)


def test_container_mode_blocks_on_measured_free_memory():
    status, blockers = _verdict(free=10.0, weights=40.0)
    assert status == "PREFLIGHT_BLOCKED" and any("MEASURED free memory" in b for b in blockers)


def _fake_vllm(monkeypatch, *, archs, parsers, quant_methods):
    def mod(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, m)
    mod("vllm")
    mod("vllm.model_executor")
    mod("vllm.model_executor.models", ModelRegistry=SimpleNamespace(get_supported_archs=lambda: archs))
    mod("vllm.model_executor.layers")
    mod("vllm.model_executor.layers.quantization", QUANTIZATION_METHODS=quant_methods)
    mod("vllm.reasoning", ReasoningParserManager=SimpleNamespace(reasoning_parsers={p: object() for p in parsers}))


def test_container_support_checks_read_the_registry(monkeypatch):
    _fake_vllm(monkeypatch, archs=["Qwen3MoeForCausalLM"], parsers=["qwen3"], quant_methods=["fp8"])
    art = {"architectures": ["Qwen3MoeForCausalLM"], "quantization_config": {"quant_method": "fp8"},
           "_text_cfg": {"num_attention_heads": 64, "num_key_value_heads": 8}}
    sup = feas.support_checks(art, 2, "container", "qwen3")
    assert sup["architecture_supported"] == {"Qwen3MoeForCausalLM": True}
    assert sup["quantization"] == {"fp8": True}
    assert sup["reasoning_parsers_available"] == ["qwen3"]
    assert sup["requested_reasoning_parser"] == {"qwen3": True}

    sup = feas.support_checks(art, 2, "container", "deepseek_r1")
    assert sup["requested_reasoning_parser"] == {"deepseek_r1": False}


def test_container_support_checks_report_an_unregistered_architecture(monkeypatch):
    _fake_vllm(monkeypatch, archs=["LlamaForCausalLM"], parsers=[], quant_methods=[])
    art = {"architectures": ["Qwen3NextForCausalLM"], "_text_cfg": {}}
    assert feas.support_checks(art, 1, "container", None)["architecture_supported"] == {"Qwen3NextForCausalLM": False}


# ---------------------------------------------------------------------------
# Pilot config: isolation
# ---------------------------------------------------------------------------

BASE_YAML = """\
project:
  output_dir: ./results
  seed: 42
benchmark:
  name: humaneval
  tasks: null
llm:
  models:
    - id: gemma4-31b-it
    # - id: qwen36-35b
  cache_dir: ./cache/llm_responses
rq2:
  n_completions: 10
  temperature: 0.8
  max_tokens: 8192
"""


@pytest.fixture
def pilot_env(tmp_path, monkeypatch):
    monkeypatch.setattr(mkcfg, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(mkcfg, "PILOT_RESULTS_ROOT", tmp_path / "results_test")
    monkeypatch.setattr(mkcfg, "PILOT_CACHE_ROOT", tmp_path / "cache" / "llm_responses_pilot")
    base = tmp_path / "base.yaml"
    base.write_text(BASE_YAML)
    return tmp_path, base


def test_model_lookup_distinguishes_active_commented_and_missing(pilot_env):
    _, base = pilot_env
    text = base.read_text()
    import yaml
    raw = yaml.safe_load(text)
    assert mkcfg.model_in_base(text, raw, "gemma4-31b-it") == "active"
    assert mkcfg.model_in_base(text, raw, "qwen36-35b") == "commented-out"
    with pytest.raises(SystemExit):
        mkcfg.model_in_base(text, raw, "invented-model")


def test_task_range_is_inclusive_and_validated():
    assert mkcfg.parse_task_range("0-2") == [0, 1, 2]
    assert mkcfg.parse_task_range("5") == [5]
    for bad in ("3-1", "a-b", "-1-2"):
        with pytest.raises(SystemExit):
            mkcfg.parse_task_range(bad)


def test_pilot_config_changes_only_the_intended_keys_and_is_isolated(pilot_env):
    tmp, base = pilot_env
    import yaml
    raw = yaml.safe_load(base.read_text())
    pilot, out_dir, cache_dir = mkcfg.build_pilot(raw, "tier1", "qwen36-35b", [0, 1, 2])
    cfg_path = out_dir / "config.yaml"
    out_dir.mkdir(parents=True)
    cfg_path.write_text(yaml.safe_dump(pilot))

    mkcfg.assert_pilot(cfg_path, base, "qwen36-35b", [0, 1, 2], out_dir, cache_dir, check_bounds=False)

    assert Path(pilot["project"]["output_dir"]).is_absolute() and Path(pilot["llm"]["cache_dir"]).is_absolute()
    assert out_dir == (tmp / "results_test" / "tier1" / "qwen36-35b").resolve()
    assert cache_dir == (tmp / "cache" / "llm_responses_pilot" / "tier1" / "qwen36-35b").resolve()
    # Sampling and budget are untouched.
    assert pilot["rq2"] == raw["rq2"]
    assert pilot["llm"]["models"] == [{"id": "qwen36-35b"}]


def test_assert_pilot_rejects_a_pilot_that_points_at_production(pilot_env):
    tmp, base = pilot_env
    import yaml
    raw = yaml.safe_load(base.read_text())
    pilot, out_dir, cache_dir = mkcfg.build_pilot(raw, "tier1", "qwen36-35b", [0])
    pilot["llm"]["cache_dir"] = str((tmp / "cache" / "llm_responses").resolve())   # production cache
    out_dir.mkdir(parents=True)
    cfg_path = out_dir / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(pilot))
    with pytest.raises(AssertionError):
        mkcfg.assert_pilot(cfg_path, base, "qwen36-35b", [0], out_dir, cache_dir, check_bounds=False)


# ---------------------------------------------------------------------------
# Report: the funnel never reads "nothing usable" as a model score
# ---------------------------------------------------------------------------

def _row(dispositions, per_completion=None, finish=None):
    from meta_real_eval.core.config import Config
    cfg = Config()
    n = len(dispositions)
    records = [{"raw_source": "content", "finish_reason": (finish or ["stop"] * n)[i],
                "delimiter_found": False, "disposition": d} for i, d in enumerate(dispositions)]
    entry = {"choices": ["x"] * n, "records": records}
    task = SimpleNamespace(label="HumanEval_0")
    return report.cell_row(cfg, None, task, "original", "m", ["x"] * n, entry, per_completion, False)


def test_cell_with_no_usable_answers_is_not_interpretable_even_with_a_zero_score():
    row = _row(["unusable_ambiguous"] * 10, per_completion=[False] * 10)
    assert row["pass_rate"] == 0.0 and row["usable_answers"] == 0 and row["unusable"] == 10
    assert row["interpretation"].startswith("NOT INTERPRETABLE")


def test_cell_reports_pass_rate_over_usable_answers_separately():
    disp = ["answer"] * 4 + ["unusable_truncated"] * 6
    row = _row(disp, per_completion=[True, True, False, False] + [False] * 6)
    assert row["pass_rate"] == 0.2
    assert row["pass_rate_over_usable"] == 0.5
    assert row["interpretation"] == "ok"


def test_truncated_kept_text_is_counted_apart_from_clean_answers():
    row = _row(["answer", "truncated"], per_completion=[True, False], finish=["stop", "length"])
    assert (row["usable_answers"], row["truncated_kept"], row["finish_length"]) == (1, 1, 1)


def test_cell_without_provenance_reads_unknown_not_reconstructed():
    from meta_real_eval.core.config import Config
    task = SimpleNamespace(label="HumanEval_0")
    row = report.cell_row(Config(), None, task, "original", "m", ["x", "y"], {"choices": ["x", "y"]}, [True, False], False)
    assert row["unknown_provenance"] == 2 and row["interpretation"].startswith("provenance unknown")


# ---------------------------------------------------------------------------
# Slurm helpers: the exact container and server commands
# ---------------------------------------------------------------------------

def _bash():
    exe = shutil.which("bash")
    if not exe:
        return None
    probe = subprocess.run([exe, "-c", "echo $BASH_VERSION"], capture_output=True, text=True)
    return exe if probe.returncode == 0 and probe.stdout.strip() else None


requires_bash = pytest.mark.skipif(_bash() is None, reason="no usable bash")


def _bash_lines(script: str, env=None) -> list[str]:
    helper = (SCRIPTS / "slurm" / "_vllm_container.sh").as_posix()
    res = subprocess.run([_bash(), "-c", f'source "{helper}"\n{script}'], capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stderr
    return res.stdout.splitlines()


@requires_bash
def test_apptainer_args_use_nv_bind_model_readonly_and_pass_cache_env():
    lines = _bash_lines(
        'export TRITON_CACHE_DIR=/r/.cache/triton XDG_CACHE_HOME=/r/.cache/xdg HF_HOME=/r/.cache/huggingface\n'
        'mre_apptainer_args /img/vllm.sif /models/M /r /r/results_test/t/m\n'
        'printf "%s\\n" "${APPTAINER_ARGS[@]}"')
    assert lines[:2] == ["exec", "--nv"]
    assert lines[-1] == "/img/vllm.sif"                       # image last, ready for a command
    joined = "\n".join(lines)
    for expected in ("/models/M:/model:ro", "/r/scripts:/opt/mre_scripts:ro", "/r/.cache:/r/.cache",
                     "/r/results_test/t/m:/r/results_test/t/m",
                     "TRITON_CACHE_DIR=/r/.cache/triton", "XDG_CACHE_HOME=/r/.cache/xdg",
                     "HF_HOME=/r/.cache/huggingface", "HF_HUB_OFFLINE=1",
                     "/r/.cache/container_home:/r/.cache/container_home"):
        assert expected in joined, expected
    assert "--home" in lines
    # The scripts dir is the only code mounted, and read-only; the model is never writable.
    assert not any(l.endswith(":/model") for l in lines)


@requires_bash
def test_apptainer_extra_flags_are_recorded_before_the_image_and_default_to_none():
    lines = _bash_lines('MRE_APPTAINER_EXTRA="--cleanenv --no-mount tmp"\n'
                        'mre_apptainer_args img /m /r\nprintf "%s\\n" "${APPTAINER_ARGS[@]}"')
    assert lines[-1] == "img" and "--cleanenv" in lines
    assert "--cleanenv" not in _bash_lines('mre_apptainer_args img /m /r\nprintf "%s\\n" "${APPTAINER_ARGS[@]}"')


@requires_bash
def test_server_args_default_to_no_parser_no_tool_flags_and_the_requested_tp():
    lines = _bash_lines('mre_server_args qwen36-35b 8123 2 16384 "" ""\nprintf "%s\\n" "${SERVER_ARGS[@]}"')
    assert lines[:3] == ["vllm", "serve", "/model"]
    pairs = dict(zip(lines[3::2], lines[4::2]))
    assert pairs == {"--host": "127.0.0.1", "--port": "8123", "--served-model-name": "qwen36-35b",
                     "--tensor-parallel-size": "2", "--max-model-len": "16384"}
    joined = " ".join(lines)
    # Nothing is inherited from the reference script unless asked for.
    for flag in ("--reasoning-parser", "--enable-auto-tool-choice", "--tool-call-parser",
                 "--enable-chunked-prefill", "--max-num-batched-tokens"):
        assert flag not in joined


@requires_bash
def test_server_args_add_parser_and_extra_flags_only_when_given():
    lines = _bash_lines('mre_server_args m 1 1 1024 qwen3 "--dtype auto --enable-chunked-prefill"\n'
                        'printf "%s\\n" "${SERVER_ARGS[@]}"')
    assert lines[lines.index("--reasoning-parser") + 1] == "qwen3"
    assert lines[-3:] == ["--dtype", "auto", "--enable-chunked-prefill"]    # extras appended last, split into words


@requires_bash
def test_gpu_count_helper_counts_listed_gpus_and_reports_zero(tmp_path):
    fake = tmp_path / "fake-smi"
    fake.write_text('#!/bin/bash\nprintf "GPU 0: A100 (UUID: a)\\nGPU 1: A100 (UUID: b)\\n"\n')
    fake.chmod(0o755)
    empty = tmp_path / "empty-smi"
    empty.write_text("#!/bin/bash\nexit 0\n")
    empty.chmod(0o755)
    assert _bash_lines(f'mre_count_gpus "{fake.as_posix()}"') == ["2"]
    assert _bash_lines(f'mre_count_gpus "{empty.as_posix()}"') == ["0"]


def test_job_script_gates_are_ordered_and_use_the_container_not_srun():
    job = (SCRIPTS / "slurm" / "submit_vllm_pilot.sh").read_text()
    # Anchored on the executable lines (the header comment also names these steps).
    order = ['HOST_GPUS="$(mre_count_gpus)"', 'CPF_ARGS=("${MRE_CONTAINER_MODEL_PATH}" --mode container',
             'mre_server_args "${MODEL}"', '"${PY}" "${REPO_DIR}/scripts/vllm_probe.py"']
    assert all(token in job for token in order), [t for t in order if t not in job]
    positions = [job.index(token) for token in order]
    assert positions == sorted(positions), "gates must run: GPU count, container preflight, server, probe"
    assert "srun" not in job.replace("srun-free", "")
    assert 'apptainer "${APPTAINER_ARGS[@]}" "${SERVER_ARGS[@]}"' in job
    assert "cd \"${PILOT_DIR}\"" in job                          # pilot logs/ stay in the pilot dir


def test_launcher_runs_host_preflight_only_and_blocks_without_override():
    launcher = (SCRIPTS / "slurm" / "launch_vllm_pilot.sh").read_text()
    assert "--mode host" in launcher and "--mode container" not in launcher
    assert "force" not in launcher.lower().replace("--force-", "")      # no override flag for a blocker


# ---------------------------------------------------------------------------
# Report verdicts: a pre-server gate failure is not a server-smoke failure
# ---------------------------------------------------------------------------

def test_pre_server_gate_failure_is_job_gate_not_server_smoke():
    v = report.probe_verdicts({"gpu_count": "FAIL: allocated GPUs (1) != requested --gpus (2)"})
    assert v == {"JOB_GATE": "FAIL: gpu_count", "SERVER_SMOKE": "NOT_RUN", "RESPONSE_FORMAT": "NOT_RUN"}


def test_server_start_failure_is_a_server_smoke_failure():
    v = report.probe_verdicts({"server_start": "FAIL: vLLM not ready"})
    assert v["SERVER_SMOKE"] == "FAIL: server_start" and v["JOB_GATE"] == "PASS"


def test_a_completed_probe_passes_gate_and_smoke_and_reports_format_separately():
    checks = {"served_model_name": "PASS", "n10_returns_10_choices": "PASS", "response_format_captured": "FAIL: boom"}
    v = report.probe_verdicts(checks)
    assert (v["JOB_GATE"], v["SERVER_SMOKE"], v["RESPONSE_FORMAT"]) == ("PASS", "PASS", "FAIL: boom")


def test_no_probe_means_everything_not_run():
    assert report.probe_verdicts({}) == {"JOB_GATE": "NOT_RUN", "SERVER_SMOKE": "NOT_RUN", "RESPONSE_FORMAT": "NOT_RUN"}


def test_every_fail_gate_name_in_the_job_script_is_a_known_job_gate_or_server_start():
    import re
    job = (SCRIPTS / "slurm" / "submit_vllm_pilot.sh").read_text()
    names = set(re.findall(r"fail_gate (\w+) ", job))
    assert names, "expected fail_gate calls"
    assert names - {"server_start"} <= report.JOB_GATE_CHECKS, names - report.JOB_GATE_CHECKS
