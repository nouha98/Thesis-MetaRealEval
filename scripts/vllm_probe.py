"""Server smoke test + raw-response probe against a running local vLLM server.

Run by scripts/slurm/submit_vllm_pilot.sh after `vllm serve` is up, from inside
the pilot directory. Needs INNKUBE_BASE_URL (no /v1) and INNKUBE_API_KEY in the
environment, exactly as the pipeline does, and the pilot config.

It reports separate verdicts, never one overall pass:

  SERVER_SMOKE     served model name == config id; the project client reaches the
                   endpoint; a short request and an n=10 request both succeed;
                   n=10 returns 10 distinct-position choices with their finish
                   reasons recorded; requests were REAL cache misses (the pilot
                   cache is used, so a cached answer can never count as evidence);
                   no Permission/Triton error in the server log; TRITON_CACHE_DIR
                   writable.
  RESPONSE_FORMAT  raw OpenAI responses dumped BEFORE any normalisation for a real
                   pipeline prompt at the real token budget, and what the client's
                   classification makes of each choice. This is the evidence for
                   choosing a reasoning parser / answer rule per model; it does
                   not decide one.

Errors are recorded, never retried until something succeeds.

Usage (inside the job):
    python scripts/vllm_probe.py --config config.yaml --out probe.json \\
        --server-log server.log --triton-count-before N
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.cache import ResponseCache  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402
from meta_real_eval.core.llm_client import InnkubeClient, _classify_choice  # noqa: E402
from meta_real_eval.rq2.generator import build_task_variants  # noqa: E402

LOG_ERROR_RE = re.compile(r"PermissionError|Permission denied|triton.*(error|exception)", re.I)


def count_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file()) if root.exists() else 0


def verdict(ok: bool, reason: str = "") -> str:
    return "PASS" if ok else f"FAIL: {reason}"


async def main_async(args) -> int:
    load_dotenv()                      # env vars already set win (override=False)
    cfg = Config.from_yaml(args.config)
    model = cfg.model_ids()[0]
    base = os.environ.get("INNKUBE_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("INNKUBE_API_KEY", "")
    result: dict = {"model": model, "effective_base_url": f"{base}/v1",
                    "api_key": "<set>" if api_key else "<EMPTY>", "checks": {}}
    print(f"effective base URL: {base}/v1   api key: {result['api_key']}")

    cache_dir = cfg.llm.cache_dir
    cache = ResponseCache(cache_dir)
    client = InnkubeClient(cfg.llm, cache, mock=cfg.project.mock)
    raw = AsyncOpenAI(api_key=api_key, base_url=base + "/v1")
    checks = result["checks"]

    # --- served model name ------------------------------------------------
    try:
        served = [m.id for m in (await raw.models.list()).data]
        result["served_model_names"] = served
        checks["served_model_name"] = verdict(model in served, f"{model!r} not in served {served}")
    except Exception as e:
        checks["served_model_name"] = verdict(False, f"{type(e).__name__}: {e}")

    # --- project-client requests, real cache misses -----------------------
    salt = uuid.uuid4().hex[:8]
    msgs = [{"role": "user", "content": "Reply with the single word: ready"}]
    files_before = count_files(cache_dir)
    try:
        t0 = time.time()
        short, short_rec = await client.complete_with_records(
            model, msgs, temperature=cfg.rq2.temperature, max_tokens=256, n=1, cache_salt=f"smoke-{salt}")
        result["short_request"] = {"seconds": round(time.time() - t0, 2),
                                   "completion": short, "records": short_rec}
        checks["short_request"] = verdict(len(short) == 1)
    except Exception as e:
        checks["short_request"] = verdict(False, f"{type(e).__name__}: {e}")

    code_msgs = [{"role": "user", "content": "Write a Python function add(a, b) that returns a + b."}]
    try:
        t0 = time.time()
        comps, recs = await client.complete_with_records(
            model, code_msgs, temperature=cfg.rq2.temperature, max_tokens=512, n=10,
            cache_salt=f"smoke10-{salt}")
        distinct = len(set(comps))
        result["n10_request"] = {"seconds": round(time.time() - t0, 2), "returned": len(comps),
                                 "distinct_completions": distinct,
                                 "finish_reasons": [r["finish_reason"] for r in recs],
                                 "dispositions": [r["disposition"] for r in recs],
                                 "empty": sum(1 for c in comps if not c.strip())}
        checks["n10_returns_10_choices"] = verdict(len(comps) == 10, f"got {len(comps)}")
        # Informational only: the same text 10 times is reported, not failed.
        print(f"n=10: {distinct} distinct of {len(comps)}; "
              f"dispositions {sorted(set(r['disposition'] for r in recs))}")
    except Exception as e:
        checks["n10_returns_10_choices"] = verdict(False, f"{type(e).__name__}: {e}")
    new_files = count_files(cache_dir) - files_before
    result["pilot_cache"] = {"dir": str(cache_dir), "new_entries": new_files}
    checks["real_cache_misses_in_pilot_cache"] = verdict(new_files == 2, f"{new_files} new entries, expected 2")

    # --- triton / server log ----------------------------------------------
    tdir = Path(os.environ.get("TRITON_CACHE_DIR", ""))
    try:
        probe_file = tdir / f".write_probe_{salt}"
        probe_file.write_text("ok")
        probe_file.unlink()
        checks["triton_cache_writable"] = verdict(True)
    except Exception as e:
        checks["triton_cache_writable"] = verdict(False, f"{tdir!r}: {type(e).__name__}: {e}")
    if args.server_log and Path(args.server_log).is_file():
        hits = [l.strip() for l in Path(args.server_log).read_text(errors="replace").splitlines()
                if LOG_ERROR_RE.search(l)]
        checks["no_permission_or_triton_error_in_server_log"] = verdict(not hits, "; ".join(hits[:3]))
        result["server_log_error_lines"] = hits[:20]
    after = count_files(tdir)
    before = args.triton_count_before
    result["triton_cache"] = {"dir": str(tdir), "files_before_server_start": before, "files_now": after,
                              "compile_activity": ("observed" if before is not None and after > before
                                                   else "not exercised / not observed (not a failure)")}

    # --- RESPONSE_FORMAT: raw responses for a real pipeline prompt --------
    try:
        bench = get_benchmark(cfg)
        task = bench.load_tasks(cfg.benchmark.tasks)[0]
        prompt_variant, _salt = build_task_variants(task, cfg)["original"]
        messages = bench.generation_messages(task, prompt_variant)
        t0 = time.time()
        resp = await raw.chat.completions.create(
            model=model, messages=messages, temperature=cfg.rq2.temperature,
            max_tokens=cfg.rq2.max_tokens, n=args.format_n)
        dump = resp.model_dump()
        analysed = []
        for c in resp.choices:
            text, rec = _classify_choice(c.message, c.finish_reason)
            analysed.append({"classification": rec, "kept_text_chars": len(text),
                             "kept_text_head": text[:200]})
        result["response_format"] = {"task": task.label, "seconds": round(time.time() - t0, 2),
                                     "raw_response": dump, "client_view": analysed}
        checks["response_format_captured"] = verdict(True)
        print("RESPONSE_FORMAT: client dispositions:",
              sorted({a["classification"]["disposition"] for a in analysed}),
              "raw sources:", sorted({a["classification"]["raw_source"] for a in analysed}))
    except Exception as e:
        checks["response_format_captured"] = verdict(False, f"{type(e).__name__}: {e}")

    Path(args.out).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    for k, v in checks.items():
        print(f"  {k}: {v}")
    smoke_keys = [k for k in checks if k != "response_format_captured"]
    failed = [k for k in smoke_keys if not checks[k].startswith("PASS")]
    print("SERVER_SMOKE:", "PASS" if not failed else f"FAIL ({', '.join(failed)})")
    print("RESPONSE_FORMAT:", checks.get("response_format_captured", "NOT_RUN"),
          "(inspect probe.json; the answer rule per model is a human decision)")
    return 0 if not failed else 1


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--server-log")
    ap.add_argument("--triton-count-before", type=int, default=None)
    ap.add_argument("--format-n", type=int, default=2, help="choices for the real-prompt format probe")
    args = ap.parse_args(argv)
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
