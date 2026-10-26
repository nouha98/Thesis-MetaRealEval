"""Write serving_<model>.json: what actually served one model in one generation job.

Called by scripts/slurm/submit_vllm_generate.sh after both preflights and
before any request is sent; the merge carries every serving_*.json of a source
into merge_provenance.json. Records the checkpoint (repo, on-disk revision,
dtype, quantization, chat-template hash), the vLLM version, the server command
and the GPUs. A later job of the same group appends its job record.

Nothing secret is written (the API key is never read).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.config import Config  # noqa: E402


def chat_template_sha256(model_dir: Path) -> str | None:
    """Hash of the chat template(s) shipped with the checkpoint; None if none found."""
    h = hashlib.sha256()
    found = False
    cfg = model_dir / "tokenizer_config.json"
    if cfg.is_file():
        tmpl = json.loads(cfg.read_text(encoding="utf-8")).get("chat_template")
        if tmpl is not None:
            h.update(json.dumps(tmpl, sort_keys=True).encode("utf-8"))
            found = True
    for name in ("chat_template.jinja", "chat_template.json"):
        p = model_dir / name
        if p.is_file():
            h.update(p.read_bytes())
            found = True
    return h.hexdigest() if found else None


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def build(args) -> dict:
    cfg = Config.from_yaml(args.config)
    model = cfg.llm.model(args.model)
    if model is None:
        raise SystemExit(f"ERROR: {args.model!r} is not in {args.config}")
    feas = _read(args.job_dir / "feasibility.json")
    cfeas = _read(args.job_dir / "feasibility_container.json")
    art = feas.get("artifact_facts", {})
    env = cfeas.get("environment_facts", {})
    image = Path(args.image) if args.image else None
    info = {
        "model": args.model,
        "served_model_name": args.model,
        "sampling": model.sampling.resolved(),
        "request_params": model.request_params,
        "checkpoint": {"on_disk_revision": art.get("revision"),
                       "repo_id": art.get("repo_id"), "local_dir": str(args.model_dir),
                       "dtype": art.get("dtype"),
                       "quantization_config": art.get("quantization_config"),
                       "chat_template_sha256": chat_template_sha256(Path(args.model_dir))},
        "engine": {"name": "vllm", "version": env.get("vllm"),
                   "torch": env.get("torch"), "transformers": env.get("transformers")},
        "container": {"image": args.image or None,
                      "image_size_bytes": image.stat().st_size if image and image.exists() else None},
        "server": {"command": args.server_cmd, "max_model_len": args.max_model_len,
                   "tensor_parallel_size": args.tp, "reasoning_parser": args.reasoning_parser or None,
                   "extra_args": args.vllm_extra or None},
        "gpus": env.get("gpus_detected"),
        "job": {"slurm_job_id": args.job_id, "host": socket.gethostname(),
                "started_at": args.started_at,
                "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
    }
    return info


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--model", required=True)
    ap.add_argument("--model-dir", required=True, type=Path)
    ap.add_argument("--job-dir", required=True, type=Path,
                    help="where the job wrote feasibility.json / feasibility_container.json")
    ap.add_argument("--out-dir", required=True, type=Path, help="the group's results dir")
    ap.add_argument("--image", default="")
    ap.add_argument("--server-cmd", default="")
    ap.add_argument("--max-model-len", type=int)
    ap.add_argument("--tp", type=int)
    ap.add_argument("--reasoning-parser", default="")
    ap.add_argument("--vllm-extra", default="")
    ap.add_argument("--job-id", default="")
    ap.add_argument("--started-at", default="")
    args = ap.parse_args(argv)

    info = build(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"serving_{args.model}.json"
    jobs = []
    if out.is_file():
        prev = json.loads(out.read_text(encoding="utf-8"))
        jobs = prev.get("jobs", [])
    info["jobs"] = [*jobs, info["job"]]
    out.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
