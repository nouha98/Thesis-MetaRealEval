"""Check that seeded requests give independent draws on one endpoint.

The control arm (rq2.request_seeds) sends the original prompt again with its
own seed. That is a pure sampling-noise control only if, on this endpoint,
(a) the n parallel samples of one seeded request differ, and (b) a different
seed is a different draw -- not a cached copy of an earlier response. Evidence
only, never proof; a person reads the output.

    T1  n=10, seed S                -> distinct completions (within-request)
    T2  n=1, seeds S+0..S+4         -> how many equal T1's children 0..4
                                       (vLLM's child-seed rule is seed+index;
                                       informative, batching may break it)
    T3  T1 again                    -> identical? (seed honoured, or cached)
    T4  n=10 under 5 other seeds    -> texts shared across requests vs the
                                       within-request duplicate rate
    T5  unseeded request twice      -> identical output only indicates POSSIBLE
                                       caching (low-variance generation can repeat
                                       too): read it with the cache headers, T4
                                       and T6
    T6  --try-no-cache: T5 with LiteLLM's documented request-body cache control
        {"cache": {"no-cache": true}}

Before T1 two warm-up requests run (unseeded n=10, seeded n=1) so a hang can be
pinned on seeded n>1. Each request has a short timeout and no retries; a timeout
prints "HANG after <step>" and exits 3 (the vLLM launcher then fails the job
instead of waiting hours on an engine that has stopped producing tokens).

Every response header containing "cache" is recorded. The request shape (the
model's recommended sampling) comes from the config via resolve_request; only
max_tokens is small. The text compared is content + reasoning field, so a
thinking model that spends the whole budget reasoning still compares.

Calls the endpoint directly (never the response cache). Endpoint and key from
INNKUBE_BASE_URL / INNKUBE_API_KEY (.env), like the pipeline.

    .venv/bin/python scripts/probe_seeds.py --config config/tier2_realclasseval.yaml \
        --model gemma4-31b-it --try-no-cache --out results_tier2_runs/probe_seeds_gemma.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.config import Config  # noqa: E402
from meta_real_eval.core.llm_client import resolve_request  # noqa: E402

PROMPT = [{"role": "user", "content":
           "Invent a name for a fictional city and describe it in one unusual sentence."}]


def _text(choice) -> str:
    m = choice.message
    reasoning = getattr(m, "reasoning_content", None) or getattr(m, "reasoning", None) or ""
    return (m.content or "") + "\n--reasoning--\n" + reasoning


def call(client, cfg: Config, model: str, n: int, seed: int | None, max_tokens: int,
         extra: dict | None = None) -> dict:
    req = resolve_request(cfg.llm, model, temperature=cfg.rq2.temperature,
                          max_tokens=max_tokens, n=n, seed=seed)
    body = {**req.extra, **(extra or {})}
    raw = client.chat.completions.with_raw_response.create(
        model=model, messages=PROMPT, **req.std, **({"extra_body": body} if body else {}))
    resp = raw.parse()
    headers = {k: v for k, v in raw.headers.items() if "cache" in k.lower()}
    return {"seed": seed, "texts": [_text(c) for c in resp.choices], "cache_headers": headers}


def step(label: str, *a, **kw) -> dict:
    print(f"{label} ...", flush=True)
    r = call(*a, **kw)
    print(f"{label}: distinct {len(set(r['texts']))}/{len(r['texts'])}", flush=True)
    return r


def summarize(r: dict) -> dict:
    texts = r["texts"]
    return {"seed": r["seed"], "n": len(texts), "distinct": len(set(texts)),
            "cache_headers": r["cache_headers"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--seed", type=int, default=424242)
    ap.add_argument("--max-tokens", type=int, default=48)
    ap.add_argument("--try-no-cache", action="store_true")
    ap.add_argument("--timeout", type=float, default=120,
                    help="seconds per request; no retries (a hung engine must fail fast)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    load_dotenv(REPO_ROOT / ".env")
    import openai
    from openai import OpenAI
    cfg = Config.from_yaml(args.config)
    client = OpenAI(api_key=os.environ.get("INNKUBE_API_KEY", ""),
                    base_url=os.environ.get("INNKUBE_BASE_URL", "").rstrip("/") + "/v1",
                    timeout=args.timeout, max_retries=0)
    S, mt, m = args.seed, args.max_tokens, args.model

    last = "start"
    try:
        step("T0a unseeded n=10", client, cfg, m, 10, None, mt)
        last = "T0a"
        step("T0b seeded n=1", client, cfg, m, 1, S, mt)
        last = "T0b"
        t1 = step("T1 seeded n=10", client, cfg, m, 10, S, mt)
        last = "T1"
        t2 = [call(client, cfg, m, 1, S + i, mt) for i in range(5)]
        t3 = call(client, cfg, m, 10, S, mt)
        t4 = [call(client, cfg, m, 10, S + 1000 * (k + 1), mt) for k in range(5)]
        t5 = [call(client, cfg, m, 1, None, mt) for _ in range(2)]
    except openai.APITimeoutError:
        print(f"HANG after {last}: no response in {args.timeout:.0f}s", flush=True)
        return 3

    within_dupes = sum(len(r["texts"]) - len(set(r["texts"])) for r in [t1, *t4])
    owners: dict[str, set[int]] = {}
    for k, r in enumerate([t1, *t4]):
        for t in set(r["texts"]):
            owners.setdefault(t, set()).add(k)
    shared_across = sum(1 for ks in owners.values() if len(ks) > 1)

    report = {
        "model": m, "endpoint": os.environ.get("INNKUBE_BASE_URL"), "max_tokens": mt,
        "T1_within_request": summarize(t1),
        "T2_child_seed_matches": sum(1 for i, r in enumerate(t2) if r["texts"][0] == t1["texts"][i]),
        "T3_repeat_identical": t3["texts"] == t1["texts"],
        "T4_across_seeds": {"requests": [summarize(r) for r in t4],
                            "texts_shared_across_requests": shared_across,
                            "within_request_duplicates": within_dupes},
        "T5_unseeded_identical": t5[0]["texts"] == t5[1]["texts"],
        "T5_cache_headers": [r["cache_headers"] for r in t5],
    }
    if args.try_no_cache:
        t6 = [call(client, cfg, m, 1, None, mt, extra={"cache": {"no-cache": True}}) for _ in range(2)]
        report["T6_no_cache_identical"] = t6[0]["texts"] == t6[1]["texts"]
        report["T6_cache_headers"] = [r["cache_headers"] for r in t6]
    report["raw"] = {"T1": t1, "T2": t2, "T3": t3, "T4": t4, "T5": t5}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    brief = {k: v for k, v in report.items() if k != "raw"}
    print(json.dumps(brief, indent=1, ensure_ascii=False))
    print(f"written -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
