"""Decide whether identical completions come from the endpoint or the model.

The response cache shows a large share of n>1 requests returning n identical
completions. Two explanations fit that, with opposite consequences:

  (a) the endpoint mishandles n and clones one completion -- the duplicates are
      an API artifact, and any variance statistic computed over them (notably
      RQ2's control_resample sampling-noise floor) is measuring nothing;
  (b) the models genuinely have very low entropy on easy HumanEval prompts --
      the duplicates are real data and a finding in their own right.

These are distinguishable. For the same prompt, ask for the samples two ways:

  ONE CALL   n=k               -- k samples from a single request
  k CALLS    n=1, unique salt  -- k samples from k independent requests

Under (b) both routes give a similar distinct-count. Under (a) the single call
collapses to 1 distinct while the separate calls stay varied.

Every request here uses a unique cache salt, so nothing is served from cache and
no existing entry is overwritten. Cost is (k + 1) requests per model.

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
    if d_single <= 1 < d_separate:
        print("ENDPOINT ARTIFACT: n>1 collapses, independent calls vary.")
        print("       Treat n>1 results as unreliable; resample via separate")
        print("       salted calls instead.")
    elif d_single <= 1 and d_separate <= 1:
        print("GENUINE LOW ENTROPY: this model/prompt is deterministic either way.")
        print("       Duplicates are real model behaviour, not an API artifact.")
    elif d_single > 1:
        print("n>1 IS HONOURED here: the single call returned varied samples.")
    else:
        print("inconclusive for this prompt -- try another --task.")


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
