"""Decide whether identical completions come from the endpoint or the model.

The response cache shows a large share of n>1 requests returning n identical
completions. Two explanations fit that, with opposite consequences:

  (a) the endpoint mishandles n and clones one completion -- the duplicates are
      an API artifact, and any variance statistic computed over them (notably
      RQ2's control_resample sampling-noise floor) is measuring nothing;
  (b) the models genuinely have very low entropy on easy HumanEval prompts --
      the duplicates are real data and a finding in their own right.

The test that decides it is the SINGLE-CALL route: ask for k samples in one
request (n=k) and count the distinct completions.

  varied    the endpoint honours n, so duplicates in the stored data are the
            model's behaviour (b), not cloning.
  collapsed either (a), or a genuinely peaked distribution on this prompt. This
            script cannot tell them apart -- try a --task or prompt where the
            model should vary.

A second route, k separate n=1 requests, is also run and reported, but it is
NOT a source of independent samples on this endpoint. The cache salt is folded
into the LOCAL cache key only and is never sent to the API, so those k requests
are byte-identical -- and the endpoint returns the same output for repeated
identical requests (measured: 1 distinct of 10 for all three models, including
512-token reasoning traces where a chance duplicate is impossible). A collapsed
n=1 route is therefore expected and says nothing about entropy; it is printed
so that quirk stays visible, and so nobody resamples by re-calling with n=1.

The prompt here is a free-form user message with no system prompt, capped at
--max-tokens, so distinct counts are not comparable with the pipeline's
constrained short-answer completions.

Every request uses a unique cache salt, so nothing is served from the local
cache and no existing entry is overwritten. Cost is (k + 1) requests per model.

Usage:
    python scripts/probe_sampling.py                    # task 0, all configured models
    python scripts/probe_sampling.py --task 94 --k 10
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.config import Config
from meta_real_eval.core.data_loader import load_humaneval
from meta_real_eval.core.llm_client import InnkubeClient


def summarise(label: str, samples: list[str]) -> int:
    distinct = len(set(samples))
    print(f"    {label:<26} {distinct} distinct / {len(samples)}")
    return distinct


async def probe(task, model_id: str, client: InnkubeClient, k: int,
                temperature: float, max_tokens: int) -> None:
    messages = [
        {"role": "user", "content": f"Complete this Python function:\n\n{task.prompt}"},
    ]
    # A run-unique stamp keeps every request below a genuine cache miss, so the
    # probe measures the endpoint rather than replaying an earlier answer.
    stamp = int(time.time())

    print(f"\n  model={model_id}  (temperature={temperature}, k={k})")

    try:
        single = await client.complete(
            model=model_id, messages=messages, temperature=temperature,
            max_tokens=max_tokens, n=k, cache_salt=f"probe-{stamp}-single",
        )
    except Exception as exc:
        print(f"    one call n={k}: FAILED ({type(exc).__name__}: {exc})")
        return
    d_single = summarise(f"one call n={k}:", single)

    separate = []
    for i in range(k):
        try:
            out = await client.complete(
                model=model_id, messages=messages, temperature=temperature,
                max_tokens=max_tokens, n=1, cache_salt=f"probe-{stamp}-sep-{i}",
            )
            separate.extend(out)
        except Exception as exc:
            print(f"    separate call {i}: FAILED ({type(exc).__name__}: {exc})")
    if not separate:
        return
    d_separate = summarise(f"{k} calls n=1:", separate)

    print("    ->", end=" ")
    if d_single > 1:
        print("n>1 IS HONOURED: the single call returned varied samples, so")
        print("       duplicates in the stored data are model behaviour, not cloning.")
        if d_separate <= 1:
            print("       Note: the n=1 route collapsed. Repeated identical n=1 requests")
            print("       return identical output on this endpoint, so they are not")
            print("       independent samples -- do not resample by re-calling with n=1.")
    elif d_separate > 1:
        print("SINGLE CALL COLLAPSED while separate n=1 calls varied: n>1 may be")
        print("       mishandled. Treat n>1 results as unreliable and confirm with")
        print("       another --task before relying on them.")
    else:
        print("INCONCLUSIVE: the single call collapsed to 1 distinct. That is either")
        print("       cloning or a genuinely peaked distribution on this prompt, and")
        print("       the n=1 route cannot separate them (identical requests replay).")
        print("       Try a --task or prompt where the model should vary.")


async def main_async(args) -> None:
    load_dotenv()
    cfg = Config.from_yaml(args.config)
    client = InnkubeClient(cfg.llm, ResponseCache(cfg.llm.cache_dir), mock=cfg.project.mock)

    tasks = {t.task_index: t for t in load_humaneval()}
    task = tasks.get(args.task)
    if task is None:
        raise SystemExit(f"task index {args.task} not in corpus")

    model_ids = [args.model] if args.model else cfg.model_ids()
    print(f"Probing HumanEval/{args.task} -- one n={args.k} call vs {args.k} "
          f"separate n=1 calls, per model.")
    if cfg.project.mock:
        print("WARNING: project.mock is true in config -- responses are stubs, "
              "the probe is meaningless. Set mock: false.")

    for model_id in model_ids:
        await probe(task, model_id, client, args.k, args.temperature, args.max_tokens)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--task", type=int, default=0, help="HumanEval task index")
    parser.add_argument("--model", default=None, help="Single model id (default: all configured)")
    parser.add_argument("--k", type=int, default=10, help="Samples per route")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--max-tokens", type=int, default=512)
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
