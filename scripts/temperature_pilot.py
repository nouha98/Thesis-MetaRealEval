#!/usr/bin/env python
"""Temperature pilot: does a higher shared temperature improve generation?

Only the temperature changes between arms; tasks, prompts (``original``
relation), models, max_tokens, n and evaluation are fixed. The temperature is
to be chosen on these generation-side measures, never on RQ2's ranking
instability.

    diagnose   5 independent requests per model at T=0.8 on an open-ended
               prompt: does the endpoint vary its output at all?
    generate   per task x model x temperature: one n-sample request (the
               production cache is reused where it matches, e.g. T=0.8). Raw
               outputs and metadata go to <out>/raw.json. No byte-identical
               repeat request: the gateway caches identical request bodies, so
               a repeat would measure that cache, not the model.
    analyze    no API calls: extraction/truncation, validated-suite scores,
               normalized-AST diversity, pairwise behavioural disagreement
               (RQ3's definition) -> <out>/summary.json and a printed table.

    .venv/bin/python scripts/temperature_pilot.py diagnose --config config/tier2_m1_pilot.yaml
    .venv/bin/python scripts/temperature_pilot.py generate --config config/tier2_m1_pilot.yaml
    .venv/bin/python scripts/temperature_pilot.py analyze  --config config/tier2_m1_pilot.yaml
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import collections
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.benchmarks.realclasseval import build_solution_with_report  # noqa: E402
from meta_real_eval.core.cache import ResponseCache  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402
from meta_real_eval.core.llm_client import InnkubeClient  # noqa: E402
from meta_real_eval.rq3.divergence import compute_divergence_generic  # noqa: E402

# Many free token choices, so a sampling endpoint almost surely varies; "pick a
# random word" is a poor probe because instruct models mode-collapse onto it.
DIAGNOSE_PROMPT = "Write a four-line poem about the sea."


# ---------------------------------------------------------------------------
# diagnose
# ---------------------------------------------------------------------------

async def diagnose(cfg: Config, out: Path) -> None:
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        client = InnkubeClient(cfg.llm, ResponseCache(Path(tmp)))
        messages = [{"role": "user", "content": DIAGNOSE_PROMPT}]
        for model_cfg in cfg.llm.models:
            responses = await asyncio.gather(*[
                client.complete_with_meta(model_cfg.id, messages, temperature=0.8,
                                          max_tokens=cfg.rq2.max_tokens, n=1, cache_salt=f"diag-{i}")
                for i in range(5)
            ], return_exceptions=True)
            texts = [r[0][0] for r in responses if not isinstance(r, Exception)]
            errors = [repr(r) for r in responses if isinstance(r, Exception)]
            results[model_cfg.id] = {"texts": texts, "errors": errors}
            print(f"{model_cfg.id:32s} requests=5 ok={len(texts)} distinct={len(set(texts))} errors={len(errors)}")
            for t in texts:
                print(f"    {t[:90]!r}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "diagnose.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

async def _fetch(client, cfg, model, messages, temperature, salt):
    kw = {} if salt is None else {"cache_salt": salt}
    n = cfg.rq2.n_completions
    key = client._cache.key(model, messages, temperature=temperature,
                            max_tokens=cfg.rq2.max_tokens, n=n, **kw)
    cached = client._cache.get(key) is not None
    comps, fin = await client.complete_with_meta(model, messages, temperature=temperature,
                                                 max_tokens=cfg.rq2.max_tokens, n=n, **kw)
    return {"completions": comps, "finish_reasons": fin, "from_cache": cached}


async def generate(cfg: Config, temperatures: list[float], out: Path) -> None:
    bench = get_benchmark(cfg)
    client = InnkubeClient(cfg.llm, ResponseCache(cfg.llm.cache_dir))

    async def one(task, model, temperature):
        messages = bench.generation_messages(task, task.prompt)
        row = {"task_id": task.task_id, "label": task.label, "model": model, "temperature": temperature}
        try:
            row["first"] = await _fetch(client, cfg, model, messages, temperature, None)
        except Exception as exc:  # recorded, not fatal: the cache makes a re-run cheap
            row["first"] = {"error": f"{type(exc).__name__}: {exc}"}
        return row

    cells = await asyncio.gather(*[
        one(task, m.id, t)
        for task in bench.load_tasks(cfg.benchmark.tasks) for m in cfg.llm.models for t in temperatures
    ])

    requests = [c["first"] for c in cells]
    ok = [r for r in requests if "completions" in r]
    meta = {
        "config": str(cfg.project.output_dir), "temperatures": temperatures,
        "n_per_request": cfg.rq2.n_completions, "max_tokens": cfg.rq2.max_tokens,
        "requests_total": len(requests),
        "requests_from_cache": sum(r["from_cache"] for r in ok),
        "api_calls_attempted": sum(1 for r in requests if not r.get("from_cache")),
        "requests_failed": len(requests) - len(ok),
        "completions_total": sum(len(r["completions"]) for r in ok),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "raw.json").write_text(json.dumps({"meta": meta, "cells": cells}, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=1))
    for c in cells:
        if "error" in c["first"]:
            print("ERROR", c["label"], c["model"], c["temperature"], c["first"]["error"])


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

def _normalized_ast(code: str):
    """AST dump with docstrings dropped (comments and formatting vanish in parse)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    for node in list(ast.walk(tree)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree, annotate_fields=False, include_attributes=False)


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def analyze(cfg: Config, out: Path, workers: int, scenario_timeout: float) -> None:
    raw = json.loads((out / "raw.json").read_text(encoding="utf-8"))
    bench = get_benchmark(cfg)
    tasks = {t.label: t for t in bench.load_tasks(cfg.benchmark.tasks)}
    cells = [c for c in raw["cells"] if "completions" in c["first"]]

    def evaluate(item):
        task, completion = item
        code, report = build_solution_with_report(completion, task.prompt, task.target)
        result = bench.run_suite(task, code, timeout_s=cfg.execution.timeout_s)
        return {"extraction": report.extraction, "primary": result.scores.get("primary"),
                "passed_all": result.passed_all, "ast": _normalized_ast(code)}

    items = [(tasks[c["label"]], comp) for c in cells for comp in c["first"]["completions"]]
    print(f"evaluating {len(items)} completions with {workers} workers ...", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        evaluated = list(ex.map(evaluate, items))

    rows, pos = [], 0
    for c in cells:
        task, model = tasks[c["label"]], c["model"]
        comps, fins = c["first"]["completions"], c["first"]["finish_reasons"]
        ev = evaluated[pos:pos + len(comps)]
        pos += len(comps)
        n = len(comps)
        n_pass = sum(e["passed_all"] for e in ev)
        asts = [e["ast"] for e in ev if e["ast"] is not None]

        rate = None
        try:
            div = compute_divergence_generic(
                cfg, task, {f"c{i}": {model: [comp]} for i, comp in enumerate(comps)},
                n_shared_inputs=cfg.rq3.n_shared_inputs, timeout_s=scenario_timeout,
                seed=cfg.project.seed, cpu_workers=workers,
                pass_rates={f"c{i}": {model: {"per_completion": [e["passed_all"]]}} for i, e in enumerate(ev)},
            )
            rate = div["pairwise_disagreement_rate"]
        except Exception as exc:
            print("divergence failed:", c["label"], model, c["temperature"], repr(exc))

        rows.append({
            "label": c["label"], "model": model, "temperature": c["temperature"], "n": n,
            "distinct_completions": len(set(comps)),
            "truncated_rate": fins.count("length") / n,
            "extraction_failed_rate": sum(e["extraction"] == "failed" for e in ev) / n,
            "mean_primary": _mean(e["primary"] for e in ev),
            "n_passed_all": n_pass,
            "mixed_pass_fail": 0 < n_pass < n,
            "distinct_normalized_asts": len(set(asts)),
            "unparseable": n - len(asts),
            "pairwise_disagreement": rate,
        })
        print(f"  {c['label']:22s} {model:30s} T={c['temperature']}  distinct={rows[-1]['distinct_completions']}/{n}  "
              f"asts={rows[-1]['distinct_normalized_asts']}  pass={n_pass}/{n}  disagree={rate}", flush=True)

    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r["model"], r["temperature"])].append(r)
    summary = []
    for (model, temp), rs in sorted(groups.items()):
        summary.append({
            "model": model, "temperature": temp, "cells": len(rs),
            "distinct_completions_frac": _mean(r["distinct_completions"] / r["n"] for r in rs),
            "truncated_rate": _mean(r["truncated_rate"] for r in rs),
            "extraction_failed_rate": _mean(r["extraction_failed_rate"] for r in rs),
            "mean_primary": _mean(r["mean_primary"] for r in rs),
            "mixed_pass_fail_frac": _mean(r["mixed_pass_fail"] for r in rs),
            "distinct_normalized_asts_frac": _mean(r["distinct_normalized_asts"] / r["n"] for r in rs),
            "pairwise_disagreement": _mean(r["pairwise_disagreement"] for r in rs),
        })
    (out / "summary.json").write_text(json.dumps({"aggregate": summary, "cells": rows}, indent=1) + "\n",
                                      encoding="utf-8")

    def f(v):
        return "   -  " if v is None else f"{float(v):6.3f}"

    print(f"\n{'model':30s} {'T':>4s} {'distinct':>8s} {'trunc':>6s} {'exFail':>6s} "
          f"{'primary':>7s} {'mixed':>6s} {'astDist':>7s} {'disagr':>6s}")
    for s in summary:
        print(f"{s['model']:30s} {s['temperature']:4.1f} {f(s['distinct_completions_frac'])} "
              f"{f(s['truncated_rate'])} {f(s['extraction_failed_rate'])} "
              f"{f(s['mean_primary'])} {f(s['mixed_pass_fail_frac'])} {f(s['distinct_normalized_asts_frac'])} "
              f"{f(s['pairwise_disagreement'])}")
    print(f"\nwritten -> {out / 'summary.json'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["diagnose", "generate", "analyze"])
    parser.add_argument("--config", default="config/tier2_m1_pilot.yaml")
    parser.add_argument("--temperatures", type=float, nargs="+", default=[0.8, 1.0, 1.2])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--scenario-timeout", type=float, default=5.0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    cfg = Config.from_yaml(args.config)
    out = args.out or Path(cfg.project.output_dir) / "temperature_pilot"

    if args.command == "diagnose":
        asyncio.run(diagnose(cfg, out))
    elif args.command == "generate":
        asyncio.run(generate(cfg, args.temperatures, out))
    else:
        analyze(cfg, out, args.workers, args.scenario_timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
