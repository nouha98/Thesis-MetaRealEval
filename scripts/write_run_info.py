"""Write (and later finalize) RUN_INFO.json, the provenance card of one pilot run.

Called by scripts/slurm/submit_vllm_pilot.sh twice: once before the pipeline runs
(facts known from the environment and arguments), and once with --finalize after
pilot_report.py, which adds the outcome counts. The API key is never recorded;
the base URL is, with the key redacted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, cwd=REPO_ROOT).strip()
    except Exception as e:
        return f"UNAVAILABLE ({type(e).__name__})"


def _version(mod: str) -> str:
    try:
        return __import__(mod).__version__
    except Exception as e:
        return f"UNAVAILABLE ({type(e).__name__})"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pilot-dir", required=True, type=Path)
    ap.add_argument("--finalize", action="store_true")
    ap.add_argument("--tier")
    ap.add_argument("--base-config")
    ap.add_argument("--model-dir")
    ap.add_argument("--gpus", type=int)
    ap.add_argument("--tp", type=int)
    ap.add_argument("--max-model-len", type=int)
    ap.add_argument("--reasoning-parser", default="")
    ap.add_argument("--vllm-extra", default="")
    ap.add_argument("--stage")
    ap.add_argument("--port")
    ap.add_argument("--server-cmd", default="")
    ap.add_argument("--pipeline-cmds", default="")
    ap.add_argument("--started-at", default="")
    ap.add_argument("--image", default="")
    ap.add_argument("--gpus-detected", type=int)
    ap.add_argument("--apptainer-extra", default="")
    args = ap.parse_args(argv)

    out = args.pilot_dir / "RUN_INFO.json"
    if args.finalize:
        info = json.loads(out.read_text(encoding="utf-8"))
        info["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        report = args.pilot_dir / "pilot_report.json"
        if report.exists():
            rep = json.loads(report.read_text(encoding="utf-8"))
            cells = rep["cells"]
            info["verdicts"] = rep["verdicts"]
            info["output_counts"] = {
                "cells": len(cells),
                "completions_requested": sum(c["requested"] for c in cells),
                "completions_received": sum(c["received"] for c in cells),
                "usable_answers": sum(c["usable_answers"] for c in cells),
                "truncated_kept": sum(c["truncated_kept"] for c in cells),
                "unusable": sum(c["unusable"] for c in cells),
                "empty": sum(c["empty"] for c in cells),
                "finish_length": sum(c["finish_length"] for c in cells),
                "unknown_provenance": sum(c["unknown_provenance"] for c in cells),
            }
        out.write_text(json.dumps(info, indent=2), encoding="utf-8")
        return

    from meta_real_eval.core.config import Config
    cfg_path = args.pilot_dir / "config.yaml"
    cfg = Config.from_yaml(cfg_path)
    feas = {}
    if (args.pilot_dir / "feasibility.json").exists():
        feas = json.loads((args.pilot_dir / "feasibility.json").read_text(encoding="utf-8"))
    art = feas.get("artifact_facts", {})

    cfeas = {}
    if (args.pilot_dir / "feasibility_container.json").exists():
        cfeas = json.loads((args.pilot_dir / "feasibility_container.json").read_text(encoding="utf-8"))
    cenv = cfeas.get("environment_facts", {})
    image = Path(args.image) if args.image else None
    base = os.environ.get("INNKUBE_BASE_URL", "").rstrip("/")
    info = {
        "tier": args.tier, "stage": args.stage,
        "config_model_id": cfg.model_ids()[0],
        "served_model_name": cfg.model_ids()[0],
        "model": {"repo_id": art.get("repo_id"), "local_dir": args.model_dir,
                  "revision": art.get("revision"), "dtype": art.get("dtype"),
                  "quantization_config": art.get("quantization_config"),
                  "weight_format": art.get("weight_format"),
                  "total_weights_gib": art.get("total_weights_gib"),
                  "shard_sha256": {s["name"]: s.get("sha256") for s in art.get("shards", [])}},
        # The server runs inside the container; the client/pipeline run on the host.
        "versions": {
            "container": {k: cenv.get(k) for k in ("vllm", "torch", "triton", "transformers", "torch_cuda_build")},
            "host_client": {"python": sys.version.split()[0], "vllm": _version("vllm"),
                            "torch": _version("torch")},
        },
        "container": {"image": args.image or None,
                      "image_size_bytes": image.stat().st_size if image and image.exists() else None,
                      "image_mtime": (datetime.fromtimestamp(image.stat().st_mtime, timezone.utc)
                                      .isoformat(timespec="seconds") if image and image.exists() else None),
                      "apptainer": _run(["apptainer", "--version"]),
                      "extra_flags": args.apptainer_extra,
                      "container_preflight": cfeas.get("status", "NOT_RUN")},
        "gpu": {"query": _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]),
                "requested_gpus": args.gpus, "detected_gpus": args.gpus_detected,
                "container_detected_gpus": cenv.get("gpu_count_detected"),
                "container_gpus": cenv.get("gpus_detected"), "tensor_parallel_size": args.tp},
        "vllm_serving": {"max_model_len": args.max_model_len,
                         "reasoning_parser": args.reasoning_parser or "none",
                         "extra_args": args.vllm_extra, "server_command": args.server_cmd},
        "endpoint": {"effective_base_url": f"{base}/v1" if base else "UNSET",
                     "api_key": "<redacted>", "port": args.port},
        "paths": {"output_dir": str(cfg.project.output_dir), "cache_dir": str(cfg.llm.cache_dir),
                  "triton_cache_dir": os.environ.get("TRITON_CACHE_DIR")},
        "sampling": {"temperature": cfg.rq2.temperature, "n_completions": cfg.rq2.n_completions,
                     "max_tokens": cfg.rq2.max_tokens, "seed_in_config": cfg.project.seed,
                     "seed_sent_to_server": False},
        "tasks": cfg.benchmark.tasks,
        "relations": cfg.rq2.relations,
        "pipeline_commands": args.pipeline_cmds,
        "base_config": args.base_config,
        "config_sha256": hashlib.sha256(cfg_path.read_bytes()).hexdigest(),
        "git": {"commit": _run(["git", "rev-parse", "HEAD"]),
                "tracked_changes": _run(["git", "status", "--porcelain", "--untracked-files=no"]).splitlines()},
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "node": os.environ.get("SLURMD_NODENAME"),
        "started_at": args.started_at, "finished_at": None,
        "serving_backend_note": "vLLM local server; other models in the study were served by the Innkube gateway.",
    }
    out.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
