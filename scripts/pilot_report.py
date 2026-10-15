"""Acceptance report for one pilot directory (results_test/<tier>/<model>/).

Reads what the pilot wrote -- config.yaml, completions, pass rates, the pilot
response cache, and (if present) feasibility.json and probe.json -- and writes
pilot_report.md + pilot_report.json and appends a row to results_test/INDEX.md.

REPORTING INVARIANT. For every (task, relation) the funnel is shown in order:

  requested -> received -> usable answers -> truncated / unusable / empty
            -> extraction failures (Tier 2 only) -> scored -> pass rate

A pass rate of 0.0 over a cell with no usable answers is NOT a measurement of
the model; the cell is labelled "not interpretable" and says which stage stopped
it. Pass rate is also given over usable answers only. Cells whose cache entry has
no provenance (written before records existed, or not found) read "unknown".

Verdicts are separate, never one overall pass:
PREFLIGHT_HOST, PREFLIGHT_CONTAINER, JOB_GATE, SERVER_SMOKE, RESPONSE_FORMAT, GENERATION, EVALUATION.
The one-model ranking-stability output is not an acceptance criterion.

Usage:
    python scripts/pilot_report.py results_test/tier2/qwen36-35b
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.cache import ResponseCache  # noqa: E402
from meta_real_eval.core.config import CONTROL_RELATION, Config  # noqa: E402
from meta_real_eval.rq2.generator import (  # noqa: E402
    MAX_GENERATE_ATTEMPTS, _mark_as_control, build_task_variants,
)

USABLE = {"answer"}
KEPT_BUT_CUT = {"truncated"}
THINK_RE = re.compile(r"</?think>")


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# Checks the job records BEFORE any server exists (submit_vllm_pilot.sh's fail_gate).
# A failure here says nothing about the server, so it is its own verdict.
JOB_GATE_CHECKS = {"apptainer", "image", "model_dir", "gpu_count", "gpu_in_container",
                   "tensor_parallel", "container_preflight"}


def probe_verdicts(checks: dict) -> dict:
    """JOB_GATE / SERVER_SMOKE / RESPONSE_FORMAT from probe.json's ``checks``."""
    def summarise(keys):
        failed = [k for k in keys if not checks[k].startswith("PASS")]
        return "PASS" if not failed else "FAIL: " + ", ".join(failed)

    gate_keys = [k for k in checks if k in JOB_GATE_CHECKS]
    smoke_keys = [k for k in checks if k not in JOB_GATE_CHECKS and k != "response_format_captured"]
    return {
        "JOB_GATE": "NOT_RUN" if not checks else summarise(gate_keys),
        "SERVER_SMOKE": "NOT_RUN" if not smoke_keys else summarise(smoke_keys),
        "RESPONSE_FORMAT": checks.get("response_format_captured", "NOT_RUN"),
    }


def find_records(cache: ResponseCache, cfg: Config, bench, task, relation: str,
                 model: str, completions: list[str]):
    """Rebuild the request keys the generator used (attempt 1..N) and return the
    cache entry whose choices equal the stored completions, else None."""
    variants = build_task_variants(task, cfg)
    if relation not in variants:
        return None
    prompt_variant, salt = variants[relation]
    messages = bench.generation_messages(task, prompt_variant)
    if relation == CONTROL_RELATION:
        messages = _mark_as_control(messages)
    for attempt in range(1, MAX_GENERATE_ATTEMPTS + 1):
        attempt_salt = salt if attempt == 1 else f"{salt or relation}-retry-{attempt}"
        key = cache.key(model, messages, temperature=cfg.rq2.temperature,
                        max_tokens=cfg.rq2.max_tokens, n=cfg.rq2.n_completions,
                        **({} if attempt_salt is None else {"cache_salt": attempt_salt}))
        entry = cache.get(key)
        if entry and entry.get("choices") == completions:
            return entry
    return None


def cell_row(cfg, bench, task, relation, model, completions, entry, per_completion, is_tier2):
    requested = cfg.rq2.n_completions
    records = (entry or {}).get("records")
    disp = [r["disposition"] for r in records] if records else ["unknown"] * len(completions)
    sources = sorted({r["raw_source"] for r in records}) if records else ["unknown"]
    finishes = [r["finish_reason"] for r in records] if records else \
        ((entry or {}).get("finish_reasons") or ["unknown"] * len(completions))
    usable_idx = [i for i, d in enumerate(disp) if d in USABLE | KEPT_BUT_CUT]
    row = {
        "task": task.label, "relation": relation,
        "requested": requested, "received": len(completions),
        "usable_answers": sum(d in USABLE for d in disp),
        "truncated_kept": sum(d in KEPT_BUT_CUT for d in disp),
        "unusable": sum(d.startswith("unusable") for d in disp),
        "empty": sum(d == "empty" for d in disp),
        "unknown_provenance": sum(d == "unknown" for d in disp),
        "finish_length": sum(f == "length" for f in finishes),
        "raw_sources": sources,
        "leftover_think_tags": sum(bool(THINK_RE.search(c)) for c in completions),
        "extraction": None,
        "scored": len(per_completion) if per_completion is not None else None,
        "pass_rate": None, "pass_rate_over_usable": None, "interpretation": "",
    }
    if is_tier2:
        from meta_real_eval.benchmarks.realclasseval import build_solution_with_report
        counts: dict[str, int] = {}
        for c in completions:
            if c.strip():
                how = build_solution_with_report(c, task.prompt, task.target)[1].extraction
                counts[how] = counts.get(how, 0) + 1
        row["extraction"] = counts
    if per_completion:
        row["pass_rate"] = round(sum(per_completion) / len(per_completion), 3)
        if records and usable_idx:
            row["pass_rate_over_usable"] = round(
                sum(per_completion[i] for i in usable_idx if i < len(per_completion)) / len(usable_idx), 3)
    # Which stage stopped this cell?
    if not completions:
        row["interpretation"] = "NOT INTERPRETABLE: generation produced nothing"
    elif records and not usable_idx:
        row["interpretation"] = ("NOT INTERPRETABLE: no usable answers "
                                 f"(unusable={row['unusable']}, empty={row['empty']}); "
                                 "a 0.0 here is a generation/format outcome, not model quality")
    elif is_tier2 and row["extraction"] and set(row["extraction"]) == {"failed"}:
        row["interpretation"] = "extraction failed for every non-empty completion (D7)"
    elif not records:
        row["interpretation"] = "provenance unknown (no records in cache entry)"
    else:
        row["interpretation"] = "ok"
    return row


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pilot_dir", type=Path)
    args = ap.parse_args(argv)
    pdir = args.pilot_dir.resolve()

    cfg = Config.from_yaml(pdir / "config.yaml")
    model = cfg.model_ids()[0]
    bench = get_benchmark(cfg)
    tasks = bench.load_tasks(cfg.benchmark.tasks)
    cache = ResponseCache(cfg.llm.cache_dir)
    is_tier2 = cfg.benchmark.name == "realclasseval"
    relations = cfg.rq2.relations

    # A smoke-stage job never runs the pipeline, so missing completions are expected,
    # not a "problem": GENERATION / EVALUATION stay NOT_RUN.
    if (_read(pdir / "RUN_INFO.json") or {}).get("stage") == "smoke":
        tasks = []

    rows, gen_problems, eval_problems = [], [], []
    for task in tasks:
        gdir = pdir / "rq2" / "generate" / task.label
        edir = pdir / "rq2" / "evaluate" / task.label
        comp = _read(gdir / "completions.json")
        rates = _read(edir / "pass_rates.json")
        if (gdir / "generation_failed.json").exists():
            gen_problems.append(f"{task.label}: generation_failed.json present")
        if comp is None:
            gen_problems.append(f"{task.label}: completions.json missing")
            continue
        if rates is None:
            eval_problems.append(f"{task.label}: pass_rates.json missing")
        for relation in relations:
            cell = (comp.get(relation) or {}).get(model)
            if cell is None:
                gen_problems.append(f"{task.label}/{relation}: no cell for {model}")
                continue
            entry = find_records(cache, cfg, bench, task, relation, model, cell)
            pr = ((rates or {}).get(relation) or {}).get(model) or {}
            row = cell_row(cfg, bench, task, relation, model, cell, entry,
                           pr.get("per_completion"), is_tier2)
            rows.append(row)
            if row["received"] != row["requested"]:
                gen_problems.append(f"{task.label}/{relation}: received {row['received']} of {row['requested']}")
            if row["interpretation"].startswith("NOT INTERPRETABLE"):
                gen_problems.append(f"{task.label}/{relation}: {row['interpretation']}")
            if rates is not None and pr and pr.get("n") != row["received"]:
                eval_problems.append(f"{task.label}/{relation}: scored {pr.get('n')} != received {row['received']}")
            if rates is not None and not pr:
                eval_problems.append(f"{task.label}/{relation}: no pass_rates entry")
            if row["leftover_think_tags"]:
                gen_problems.append(f"{task.label}/{relation}: {row['leftover_think_tags']} completion(s) with leftover think tags")

    feas = _read(pdir / "feasibility.json") or {}
    cfeas = _read(pdir / "feasibility_container.json") or {}
    probe = _read(pdir / "probe.json") or {}
    verdicts = {
        "PREFLIGHT_HOST": feas.get("status", "NOT_RUN"),
        "PREFLIGHT_CONTAINER": cfeas.get("status", "NOT_RUN"),
        **probe_verdicts(probe.get("checks", {})),
        "GENERATION": ("NOT_RUN" if not rows else "PASS" if not gen_problems
                       else f"FAIL: {len(gen_problems)} problem(s)"),
        "EVALUATION": ("NOT_RUN" if not rows else "PASS" if not eval_problems
                       else f"FAIL: {len(eval_problems)} problem(s)"),
    }

    report = {"pilot_dir": str(pdir), "tier": "tier2" if is_tier2 else "tier1", "model": model,
              "verdicts": verdicts, "generation_problems": gen_problems,
              "evaluation_problems": eval_problems, "cells": rows,
              "run_info": _read(pdir / "RUN_INFO.json")}
    (pdir / "pilot_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = [f"# Pilot report: {report['tier']} / {model}", "", "## Verdicts", ""]
    md += [f"- **{k}**: {v}" for k, v in verdicts.items()]
    md += ["", "## Funnel per (task, relation)", "",
           "| task | relation | req | recv | usable | trunc(kept) | unusable | empty | finish=length | extraction | scored | pass | pass/usable | note |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| {task} | {relation} | {requested} | {received} | {usable_answers} | {truncated_kept} | "
                  "{unusable} | {empty} | {finish_length} | {extraction} | {scored} | {pass_rate} | "
                  "{pass_rate_over_usable} | {interpretation} |".format(**r))
    for title, items in (("Generation problems", gen_problems), ("Evaluation problems", eval_problems)):
        md += ["", f"## {title}", ""] + ([f"- {i}" for i in items] or ["- none"])
    md += ["", "Note: the one-model ranking-stability output is not an acceptance criterion."]
    (pdir / "pilot_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    index = pdir.parent.parent / "INDEX.md"
    if not index.exists():
        index.write_text("| date | tier | model | job | " + " | ".join(verdicts) + " |\n"
                         "|---|---|---|---|" + "---|" * len(verdicts) + "\n", encoding="utf-8")
    info = report["run_info"] or {}
    with index.open("a", encoding="utf-8") as f:
        f.write(f"| {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')} | {report['tier']} | {model} | {info.get('slurm_job_id', '?')} | "
                + " | ".join(verdicts.values()) + " |\n")

    print("\n".join(md))


if __name__ == "__main__":
    main()
