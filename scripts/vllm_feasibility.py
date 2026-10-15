"""Preflight for serving a downloaded model with vLLM, in two separate modes.

  --mode host        (login node; no GPU, no vLLM, no container)
      Reads only the model directory: artifact facts (config.json, shard sizes,
      hashes), arithmetic estimates, and the necessary tensor-parallel
      conditions. It makes NO claim about what vLLM supports, because vLLM is
      not installed on the host: those checks are reported as NOT CHECKED.

  --mode container   (inside the Apptainer image, in the GPU job)
      Imports the vLLM that will actually serve the model and reports what it
      says: version, whether the architecture and quantisation are registered,
      which reasoning parsers exist, plus the GPUs the process really sees
      (count, names, free memory). Run it as
        apptainer exec --nv --bind <model>:/model:ro --bind <scripts>:/opt/mre_scripts:ro \\
            IMAGE python3 /opt/mre_scripts/vllm_feasibility.py /model --mode container ...

Report sections are kept apart on purpose:

  artifact_facts     read from the files (config.json, shard sizes, hashes)
  environment_facts  what is installed / detected right now, in THIS mode
  estimates          arithmetic, labelled as such -- NOT measurements
  support_checks     what the installed vLLM says it supports (container mode)

The status is PREFLIGHT_PASSED or PREFLIGHT_BLOCKED. It never says "feasible":
whether the model really loads and answers on the allocated GPUs is decided only
by the server smoke test. A registered architecture or parser name proves
nothing about runtime behaviour. This script never fetches or loads weights.

Usage (host):
    python scripts/vllm_feasibility.py /shared/.../model --gpus 2 --tp 2 \\
        --max-model-len 16384 --out results_test/tier1/qwen36-35b/feasibility.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

GIB = 1024 ** 3
MOE_KEYS = ("num_experts", "num_local_experts", "n_routed_experts")
DTYPE_BYTES = {"float32": 4, "float16": 2, "bfloat16": 2, "float8": 1}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_facts(model_dir: Path, repo_id: str | None, do_hash: bool) -> dict:
    cfg_path = model_dir / "config.json"
    if not cfg_path.is_file():
        return {"error": f"no config.json in {model_dir}"}
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    text_cfg = cfg.get("text_config") or cfg          # some multimodal configs nest the LM

    shards = sorted(p for p in model_dir.glob("*.safetensors"))
    fmt = "safetensors"
    if not shards:
        shards, fmt = sorted(model_dir.glob("*.bin")), "pytorch_bin"
    shard_info = [{"name": p.name, "gib": round(p.stat().st_size / GIB, 3),
                   **({"sha256": sha256_file(p)} if do_hash else {})} for p in shards]

    # HF cache layout models--org--name/snapshots/<revision> gives repo AND revision.
    revision, inferred_repo = None, None
    m = re.search(r"models--([^/\\]+)--([^/\\]+)[/\\]snapshots[/\\]([0-9a-f]{7,40})", str(model_dir))
    if m:
        inferred_repo, revision = f"{m.group(1)}/{m.group(2)}", m.group(3)
    if (model_dir / ".git").exists():
        try:
            revision = subprocess.check_output(
                ["git", "-C", str(model_dir), "rev-parse", "HEAD"], text=True).strip()
        except Exception:
            pass

    index = model_dir / "model.safetensors.index.json"
    return {
        "model_dir": str(model_dir),
        "repo_id": repo_id or inferred_repo or "UNKNOWN -- pass --repo-id",
        "revision": revision or "UNKNOWN (not a git clone or HF cache snapshot)",
        "architectures": cfg.get("architectures"),
        "model_type": cfg.get("model_type"),
        "moe": any(text_cfg.get(k) for k in MOE_KEYS),
        "moe_experts": next((text_cfg[k] for k in MOE_KEYS if text_cfg.get(k)), None),
        "dtype": (cfg.get("torch_dtype") or cfg.get("dtype")
                  or text_cfg.get("torch_dtype") or text_cfg.get("dtype")),
        "quantization_config": cfg.get("quantization_config"),
        "weight_format": fmt,
        "n_shards": len(shard_info),
        "total_weights_gib": round(sum(s["gib"] for s in shard_info), 3),
        "index_file_present": index.is_file(),
        "shards": shard_info,
        "hashed": do_hash,
        "_text_cfg": {k: text_cfg.get(k) for k in (
            "num_hidden_layers", "num_attention_heads", "num_key_value_heads",
            "head_dim", "hidden_size", "max_position_embeddings", "layer_types")},
    }


def environment_facts(mode: str) -> dict:
    env = {"mode": mode}
    for mod in ("vllm", "transformers", "torch", "triton"):
        try:
            env[mod] = __import__(mod).__version__
        except Exception as e:
            env[mod] = f"NOT AVAILABLE ({type(e).__name__})"
    try:
        import torch
        env["torch_cuda_build"] = torch.version.cuda
        env["cuda_available"] = bool(torch.cuda.is_available())
        n = torch.cuda.device_count() if torch.cuda.is_available() else 0
        env["gpu_count_detected"] = n
        gpus = []
        for i in range(n):
            free, total = torch.cuda.mem_get_info(i)
            gpus.append({"index": i, "name": torch.cuda.get_device_name(i),
                         "total_gib": round(total / GIB, 1), "free_gib": round(free / GIB, 1)})
        env["gpus_detected"] = gpus
    except Exception:
        env["cuda_available"] = "unknown"
    if mode == "host":
        env["note"] = ("host mode: vLLM/GPU facts here describe the LOGIN node environment and say "
                       "nothing about the container or the compute nodes.")
    return env


def estimates(art: dict, gpus: int, gpu_gib: float, util: float, tp: int, max_len: int) -> dict:
    est = {"label": "ESTIMATES, not measurements", "gpus": gpus, "gpu_gib_requested_class": gpu_gib,
           "gpu_memory_utilization": util, "tensor_parallel_size": tp}
    weights = art.get("total_weights_gib", 0.0)
    usable = gpus * gpu_gib * util
    est.update(weights_gib=weights, usable_gib=round(usable, 1),
               headroom_gib=round(usable - weights, 1),
               headroom_note="before activations / CUDA graphs / runtime overhead")
    c = art.get("_text_cfg", {})
    try:
        heads = c["num_attention_heads"]
        kv = c.get("num_key_value_heads") or heads
        head_dim = c.get("head_dim") or c["hidden_size"] // heads
        layers = c["num_hidden_layers"]
        dtype_bytes = 2
        per_tok = 2 * layers * kv * head_dim * dtype_bytes
        est["kv_cache_gib_one_full_length_sequence_upper_bound"] = round(per_tok * max_len / GIB, 2)
        est["kv_note"] = ("assumes every layer is full attention; hybrid / linear-attention "
                          "architectures need less. Concurrent sequences multiply this.")
    except Exception:
        est["kv_cache_gib_one_full_length_sequence_upper_bound"] = "not derivable from config.json"
    return est


def support_checks(art: dict, tp: int, mode: str, parser: str | None) -> dict:
    out = {}
    c = art.get("_text_cfg", {})
    heads, kv = c.get("num_attention_heads"), c.get("num_key_value_heads") or c.get("num_attention_heads")
    tp_notes = []
    if heads and heads % tp:
        tp_notes.append(f"num_attention_heads={heads} not divisible by tp={tp}")
    if kv and not (kv % tp == 0 or tp % kv == 0):
        tp_notes.append(f"num_key_value_heads={kv} incompatible with tp={tp}")
    ex = art.get("moe_experts")
    if ex and ex % tp:
        tp_notes.append(f"experts={ex} not divisible by tp={tp}")
    out["tp_necessary_conditions"] = tp_notes or "ok (necessary conditions only; real acceptance is at load time)"

    if mode == "host":
        not_checked = "NOT CHECKED on the host: vLLM is only available inside the container"
        out.update(architecture_supported=not_checked, quantization=not_checked,
                   reasoning_parsers_available=not_checked, requested_reasoning_parser=parser or "none")
        return out

    try:
        from vllm.model_executor.models import ModelRegistry
        supported = set(ModelRegistry.get_supported_archs())
        out["architecture_supported"] = {a: a in supported for a in (art.get("architectures") or [])}
    except Exception as e:
        out["architecture_supported"] = f"UNKNOWN: {type(e).__name__}: {e}"
    q = (art.get("quantization_config") or {}).get("quant_method")
    try:
        from vllm.model_executor.layers.quantization import QUANTIZATION_METHODS
        out["quantization"] = "none" if not q else {q: q in QUANTIZATION_METHODS}
    except Exception as e:
        out["quantization"] = f"{q} (support UNKNOWN: {type(e).__name__})" if q else "none"
    try:
        from vllm.reasoning import ReasoningParserManager
    except Exception as e:
        out["reasoning_parsers_available"] = f"UNKNOWN: {type(e).__name__}: {e}"
        out["requested_reasoning_parser"] = f"{parser} (availability UNKNOWN)" if parser else "none"
        return out
    listed = _listed_reasoning_parsers(ReasoningParserManager)
    out["reasoning_parsers_available"] = (
        listed if listed else "UNKNOWN: listing returned no entries (vLLM may register parsers lazily)")
    if parser:
        found = reasoning_parser_available(ReasoningParserManager, parser)
        out["requested_reasoning_parser"] = (
            {parser: found} if found is not None else f"{parser} (availability UNKNOWN)")
    else:
        out["requested_reasoning_parser"] = "none"
    return out


def _listed_reasoning_parsers(manager) -> list[str]:
    """Every parser name the manager exposes, eager or lazy. May well be empty."""
    names: set[str] = set()
    for attr in ("reasoning_parsers", "lazy_parsers"):
        names |= set(getattr(manager, attr, None) or {})
    return sorted(names)


def reasoning_parser_available(manager, name: str) -> bool | None:
    """True / False / None (unknown) for 'can this vLLM resolve parser ``name``'.

    An empty listing proves nothing: vLLM 0.17 returned [] here although its own
    reference job serves with ``--reasoning-parser qwen3``. So a listed name is
    True, and otherwise the manager's own lookup decides. Only a clean KeyError
    from that lookup is a definite "no"; any other failure is "unknown" and is
    left to the server smoke test rather than blocking.
    """
    listed = _listed_reasoning_parsers(manager)
    if name in listed:
        return True
    getter = getattr(manager, "get_reasoning_parser", None)
    if getter is None:
        # No lookup to ask: a non-empty listing is the only evidence there is.
        return False if listed else None
    try:
        getter(name)
        return True
    except KeyError:
        return False
    except Exception:
        return None


def verdict(art: dict, env: dict, est: dict, sup: dict, mode: str, requested_gpus: int) -> tuple[str, list[str]]:
    blockers = []
    if not art["n_shards"]:
        blockers.append("no weight shards (*.safetensors / *.bin) found")
    if est["tensor_parallel_size"] > est["gpus"]:
        blockers.append(f"tensor_parallel_size={est['tensor_parallel_size']} > gpus={est['gpus']}")
    if isinstance(sup["tp_necessary_conditions"], list):
        blockers += sup["tp_necessary_conditions"]
    if est["headroom_gib"] <= 0:
        blockers.append(f"ESTIMATE: weights {est['weights_gib']} GiB exceed usable "
                        f"{est['usable_gib']} GiB for {est['gpus']} GPU(s)")
    if mode == "container":
        if str(env.get("vllm", "")).startswith("NOT AVAILABLE"):
            blockers.append("vllm is not importable inside the container")
        arch = sup["architecture_supported"]
        if isinstance(arch, dict) and not all(arch.values()):
            blockers.append(f"architecture not registered in the container's vLLM: {arch}")
        q = sup["quantization"]
        if isinstance(q, dict) and not all(q.values()):
            blockers.append(f"quantisation method not supported by the container's vLLM: {q}")
        rp = sup["requested_reasoning_parser"]
        if isinstance(rp, dict) and not all(rp.values()):
            blockers.append(f"requested reasoning parser not available in the container's vLLM: {rp}")
        detected = env.get("gpu_count_detected")
        if not env.get("cuda_available") or not detected:
            blockers.append("no CUDA GPU visible inside the container (was --nv passed?)")
        else:
            if detected != requested_gpus:
                blockers.append(f"GPUs visible inside the container ({detected}) != requested --gpus ({requested_gpus})")
            used = env.get("gpus_detected", [])[: est["tensor_parallel_size"]]
            free = sum(g["free_gib"] for g in used)
            need = est["weights_gib"]
            if used and need >= free * est["gpu_memory_utilization"]:
                blockers.append(f"MEASURED free memory on {len(used)} GPU(s) = {free:.1f} GiB; weights alone "
                                f"need {need} GiB (utilisation {est['gpu_memory_utilization']})")
    return ("PREFLIGHT_BLOCKED" if blockers else "PREFLIGHT_PASSED"), blockers


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("model_dir", type=Path)
    ap.add_argument("--repo-id")
    ap.add_argument("--gpus", type=int, default=1)
    ap.add_argument("--tp", type=int, default=None, help="tensor-parallel size (default = --gpus)")
    ap.add_argument("--gpu-gib", type=float, default=80.0, help="requested GPU memory class, GiB")
    ap.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    ap.add_argument("--max-model-len", type=int, default=16384)
    ap.add_argument("--no-hash", action="store_true", help="skip shard sha256 (slow on 100+ GB)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--mode", choices=["host", "container"], default="host")
    ap.add_argument("--reasoning-parser", default=None,
                    help="parser you intend to pass to vLLM; container mode checks it is registered")
    args = ap.parse_args(argv)
    tp = args.tp or args.gpus

    art = artifact_facts(args.model_dir, args.repo_id, not args.no_hash)
    env = environment_facts(args.mode)
    est = estimates(art, args.gpus, args.gpu_gib, args.gpu_memory_utilization, tp, args.max_model_len) \
        if "error" not in art else {}
    sup = support_checks(art, tp, args.mode, args.reasoning_parser) if "error" not in art else {}
    status, blockers = verdict(art, env, est, sup, args.mode, args.gpus) if "error" not in art else \
        ("PREFLIGHT_BLOCKED", [art["error"]])

    art.pop("_text_cfg", None)
    report = {"mode": args.mode, "status": status, "blockers": blockers,
              "runtime_verdict": "NOT_RUN (decided only by the server smoke job)",
              "artifact_facts": art, "environment_facts": env,
              "estimates": est, "support_checks": sup}
    text = json.dumps(report, indent=2, default=str)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)
    sys.exit(0 if status == "PREFLIGHT_PASSED" else 2)


if __name__ == "__main__":
    main()
