"""Stage 4 A3 development pilot: the bounded test agent (decisions 7 and 10.3; plan rev. 9.3).

    # 1. one model at a time (vLLM GPU job via launch_vllm_generate.sh --run, or the gateway for gemma)
    python scripts/build_a3.py run --config config/tier2_extensions.yaml --llm-config config/tier2_runs/<group>.yaml \
        --model qwen38-27b --a2 results_tier2_ext/a2/dev_k5_r7b --witness results_tier2_ext/witness/dev_pilot_reviewed \
        --out results_tier2_ext/a3/dev_pilot
    # 2. merge the models: A3-only and A2 u A3 test files (+ private-rename control on A3 tests)
    python scripts/build_a3.py merge --config config/tier2_extensions.yaml --a2 results_tier2_ext/a2/dev_k5_r7b \
        --out results_tier2_ext/a3/dev_pilot
    # 3. after eval_heldout (A3 and union) and grade_hidden --compare (A2 vs union) on the development tasks:
    python scripts/build_a3.py report --config config/tier2_extensions.yaml --a2 results_tier2_ext/a2/dev_k5_r7b \
        --out results_tier2_ext/a3/dev_pilot --eval-a2 results_tier2_ext/a2/full_v2

Targets (fixed): per development task with admitted A2 tests, the primary-confirmed discovery groups that
no final A2 test kills, in group-id order, at most ``--max-groups`` (3); every model targets the same
groups; at most ``--attempts`` (3) proposals per (model, group). Without ``--targets`` only development tasks
are used.

A3 v2 and the evaluation runs (decisions 10.6):

    # once, after H v1 is frozen: the shared target list of v1 and v2 (v1's rule on the 55-task cohort)
    python scripts/build_a3.py freeze-targets --config config/tier2_extensions.yaml --a2 results_tier2_ext/hidden_v1 \
        --witness results_tier2_ext/witness/full --audit results_tier2_ext/audit_h/round1/audit_reserved.json
    # a version on the cohort (--version v1 | v2; v1 is the pilot's code path, unchanged)
    python scripts/build_a3.py run --version v2 --targets config/extensions_protocol/a3_targets_v1.json \
        --config config/tier2_extensions.yaml --llm-config <group>.yaml --model <model> --a2 results_tier2_ext/hidden_v1 \
        --witness results_tier2_ext/witness/full --out results_tier2_ext/a3/eval_v2
    python scripts/build_a3.py merge --targets config/extensions_protocol/a3_targets_v1.json \
        --config config/tier2_extensions.yaml --a2 results_tier2_ext/hidden_v1 --out results_tier2_ext/a3/eval_v2
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import difflib
import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.benchmarks.contracts import load_contract  # noqa: E402
from meta_real_eval.benchmarks.witness import GEN_ALIAS  # noqa: E402
from meta_real_eval.oracles import agent  # noqa: E402
from meta_real_eval.oracles.admission import admit, private_rename, run_tests  # noqa: E402
from meta_real_eval.oracles.fault_groups import load_split  # noqa: E402

MAX_GROUPS, ATTEMPTS = 3, 3
TARGETS = ec.PROTOCOL_DIR / "a3_targets_v1.json"
TARGET_RULE = ("per cohort task: the primary-confirmed discovery groups with runnable code that no final A2 test of "
               "the frozen H v1 kills, in group-id order, at most 3 (v1's rule, decisions 10.6)")


def surviving(a2: dict) -> list[str]:
    """Discovery groups no final A2 test kills (the A3 targets), in group-id order."""
    return sorted(set(a2.get("discovery_groups", [])) - set(a2.get("covered_final", [])))


def a2_ready(a2_dir: Path, development: list[str]) -> dict:
    out = {}
    for lab in development:
        p = a2_dir / lab / "a2.json"
        if p.is_file() and (a := json.loads(p.read_text(encoding="utf-8"))).get("ready"):
            out[lab] = a
    return out


def seed_of(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16) % 2**31


def fault_diff(ref: str, code: str, n: int = 3) -> str:
    """v1: three context lines; v2: none (``-U0``, decisions 10.6)."""
    return "".join(difflib.unified_diff(ref.splitlines(True), code.splitlines(True), "reference", "faulty", n=n))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def load_targets(path: Path, a2_dir: Path) -> dict:
    """The frozen target list; ``a2_dir`` must be the frozen H v1 bundle it was computed from."""
    import freeze_h
    rec = json.loads(path.read_text(encoding="utf-8"))
    h = freeze_h.verify(a2_dir)
    if h["version"] != "tier2-hidden-v1" or h["global_sha256"] != rec["h_v1_sha256"]:
        raise SystemExit(f"ERROR: {a2_dir} is not the frozen H v1 the target list was computed from")
    return rec


def selected(args, cfg) -> dict:
    """{task: its A2 record}: the cohort of the target list (evaluation) or the ready development tasks."""
    if args.targets:
        rec = load_targets(args.targets, args.a2)
        return {lab: json.loads((args.a2 / lab / "a2.json").read_text(encoding="utf-8")) for lab in rec["cohort"]}
    return a2_ready(args.a2, cfg.extensions.development_tasks)


def freeze_targets(args, cfg) -> dict:
    """The shared A3 target list of v1 and v2, frozen before either evaluation run (decisions 10.6)."""
    import build_a2
    import freeze_h
    from meta_real_eval.core.provenance import file_sha256, git_state
    if TARGETS.exists():
        raise SystemExit(f"ERROR: {TARGETS} exists; the target list is never recomputed")
    if not (args.witness and args.audit):
        raise SystemExit("ERROR: freeze-targets needs --witness and --audit")
    h = freeze_h.verify(args.a2)
    if h["version"] != "tier2-hidden-v1":
        raise SystemExit(f"ERROR: targets come from the frozen H v1 bundle, not {h['version']}")
    audit = set(json.loads(args.audit.read_text(encoding="utf-8"))["tasks"])
    cohort = sorted(set(h["tasks"]) - audit)
    if len(cohort) != 55:
        raise SystemExit(f"ERROR: cohort has {len(cohort)} tasks, expected 55")
    tasks, _ = ec.load_tasks(cfg, args.ungated)
    bench = get_benchmark(cfg)
    baseline = Path(cfg.extensions.baseline_scores)
    split_groups, _ = load_split(ec.PROTOCOL_DIR / "fault_split_v1.json")
    targets = {}
    for lab in cohort:
        a2 = json.loads((args.a2 / lab / "a2.json").read_text(encoding="utf-8"))
        wit = json.loads((args.witness / lab / "witness.json").read_text(encoding="utf-8"))
        disc = build_a2.discovery_codes(wit, tasks[lab], bench, baseline, split_groups)
        targets[lab] = [{"group_id": g, "code_sha256": sha(disc[g])} for g in surviving(a2) if disc.get(g)][:MAX_GROUPS]
    rec = {"version": "a3_targets_v1", "rule": TARGET_RULE, "h_v1_sha256": h["global_sha256"],
           "witness": str(args.witness), "witness_files": {lab: file_sha256(args.witness / lab / "witness.json")
                                                           for lab in cohort},
           "audit_reserved": file_sha256(args.audit), "cohort": cohort,
           "tasks_with_targets": sum(bool(v) for v in targets.values()), "n_targets": sum(map(len, targets.values())),
           "targets": targets, "git": git_state()}
    TARGETS.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return {"tasks_with_targets": rec["tasks_with_targets"], "n_targets": rec["n_targets"], "written": str(TARGETS)}


# --- run -----------------------------------------------------------------------------------------

async def run_model(args, cfg, llm_cfg) -> dict:
    import build_a2
    from meta_real_eval.core.cache import ResponseCache
    from meta_real_eval.core.llm_client import InnkubeClient

    tasks, gated = ec.load_tasks(cfg, args.ungated)
    bench = get_benchmark(cfg)
    baseline = Path(cfg.extensions.baseline_scores)
    split_groups, _ = load_split(ec.PROTOCOL_DIR / "fault_split_v1.json")
    ready = selected(args, cfg)
    plan = json.loads(args.targets.read_text(encoding="utf-8"))["targets"] if args.targets else None
    out_dir = args.out / "runs" / args.model
    client = InnkubeClient(llm_cfg.llm, ResponseCache(out_dir / "llm_cache"))   # never the frozen RQ2 caches
    timeout_s = cfg.execution.timeout_s
    tag = f"a3{args.version}"                  # seeds and cache salts: (version, task, group, model, attempt)
    write_manifest(args, llm_cfg, out_dir)

    async def one_task(lab: str, a2: dict) -> dict:
        path = out_dir / lab / "a3.json"
        if path.is_file() and not args.force:
            old = json.loads(path.read_text(encoding="utf-8"))
            if old.get("version", "v1") != args.version:
                raise SystemExit(f"ERROR: {path} holds A3 {old.get('version', 'v1')}, not {args.version}")
            return old
        task = tasks[lab]
        wit = json.loads((args.witness / lab / "witness.json").read_text(encoding="utf-8"))
        disc = build_a2.discovery_codes(wit, task, bench, baseline, split_groups)
        if plan is not None:                       # the frozen list: same groups, same code, for v1 and v2
            targets = [t["group_id"] for t in plan[lab]]
            bad = [t["group_id"] for t in plan[lab]
                   if not disc.get(t["group_id"]) or sha(disc[t["group_id"]]) != t["code_sha256"]]
            if bad:
                raise SystemExit(f"ERROR: {lab}: target code differs from the frozen list: {bad}")
        else:
            targets = [g for g in surviving(a2) if disc.get(g)][:args.max_groups]
        contract = load_contract(ec.REPO / a2["contract"]["path"])

        async def one_target(gid: str) -> dict:
            calls = []

            async def ask(msgs, k):
                t0 = time.monotonic()
                try:
                    r = await client.complete_detailed(args.model, msgs, temperature=0.6, max_tokens=args.max_tokens,
                                                       n=1, cache_salt=f"{tag}:{lab}:{gid}:{k}",
                                                       seed=seed_of(tag, lab, gid, args.model, k))
                except Exception as exc:                  # a transport failure costs the attempt, not the run
                    meta = {"seconds": round(time.monotonic() - t0, 1), "error": f"{type(exc).__name__}: {exc}"}
                    calls.append(meta)
                    return "", meta
                meta = {"seconds": round(time.monotonic() - t0, 1), "usage": r.meta.get("usage"),
                        "finish_reason": (r.finish_reasons or [None])[0], "cache_hit": r.meta.get("cache_hit", False)}
                calls.append(meta)
                return (r.choices or [""])[0], meta
            t0 = time.monotonic()
            if args.version == "v1":
                msgs = agent.first_prompt(task.prompt, contract, task.reference_code,
                                          fault_diff(task.reference_code, disc[gid]))
            else:                                  # v2: no reference, no diff context, value-free feedback
                msgs = agent.first_prompt_v2(task.prompt, contract, fault_diff(task.reference_code, disc[gid], n=0))
            res = await agent.run_target(ask, msgs, task.module_name, task.reference_code, disc[gid], timeout_s,
                                         args.attempts, checker=agent.check_v2 if args.version == "v2" else None)
            return {"group_id": gid, "admitted": res.admitted is not None, "code": res.admitted,
                    "attempts": res.attempts, "seconds": round(time.monotonic() - t0, 1)}
        recs = await asyncio.gather(*(one_target(g) for g in targets))
        rec = {"task": lab, "model": args.model, "version": args.version, "gated": gated, "targets": recs,
               "n_targets": len(targets), "admitted": sum(r["admitted"] for r in recs)}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
        print(f"[{args.model}] {lab}: {rec['admitted']}/{len(targets)} target(s) admitted", flush=True)
        return rec
    recs = await asyncio.gather(*(one_task(lab, a2) for lab, a2 in ready.items()))
    return {"model": args.model, "tasks": len(recs), "targets": sum(r["n_targets"] for r in recs),
            "admitted": sum(r["admitted"] for r in recs)}


def write_manifest(args, llm_cfg, out_dir: Path) -> None:
    """Recorded at the start of every run (decisions 10.6, safeguard 5): code, prompts, model, config, seeds."""
    import os
    from meta_real_eval.core.provenance import write_run_manifest
    m = llm_cfg.llm.model(args.model)
    write_run_manifest(out_dir, stage=f"a3_{args.version}_run", config_path=args.config,
                       inputs={"agent": Path(agent.__file__), "build_a3": Path(__file__),
                               "llm_config": args.llm_config, **({"targets": args.targets} if args.targets else {})},
                       seeds={"rule": f"sha256(a3{args.version}|task|group|model|attempt)[:8] mod 2^31"},
                       settings={"version": args.version, "model": args.model,
                                 "model_config": m.model_dump(mode="json") if m else None,
                                 "endpoint": os.environ.get("INNKUBE_BASE_URL"), "temperature": 0.6,
                                 "max_tokens": args.max_tokens, "attempts": args.attempts, "max_groups": args.max_groups,
                                 "prompt_sha256": sha(agent.SYSTEM + agent.RULES), "evaluation": bool(args.targets)})


# --- merge ---------------------------------------------------------------------------------------

def renamed(body: str, name: str) -> str:
    return re.sub(rf"\bdef {agent.TEST_NAME}\(", f"def {name}(", body, count=1)


def merge(args, cfg) -> dict:
    tasks, _ = ec.load_tasks(cfg, args.ungated)
    ready = selected(args, cfg)
    runs = sorted(p for p in (args.out / "runs").iterdir() if p.is_dir())
    summary = {}
    for lab, a2 in ready.items():
        task = tasks[lab]
        a3 = [{"model": r.name, "target": t["group_id"], "code": t["code"]}
              for r in runs if (r / lab / "a3.json").is_file()
              for t in json.loads((r / lab / "a3.json").read_text(encoding="utf-8"))["targets"] if t["admitted"]]
        n2 = len(a2["final_tests"])
        for i, t in enumerate(a3):
            t["name"] = f"test_h_{n2 + i}"                 # same names in the A3-only and the union file
        head = f"import pytest\nimport {task.module_name} as {GEN_ALIAS}\n\n\n"
        a3_code = head + "\n\n".join(renamed(t["code"], t["name"]) for t in a3) if a3 else ""
        union = (a2["final_code"] + "\n\n\nimport pytest\n\n\n" + "\n\n".join(renamed(t["code"], t["name"]) for t in a3)
                 if a3 else a2["final_code"])
        names = [t["name"] for t in a3]
        control = {"applicable": False}
        if a3 and a2.get("control", {}).get("valid"):
            variant = private_rename(task.reference_code, load_contract(ec.REPO / a2["contract"]["path"])["class_name"])
            outs = run_tests(task.module_name, variant, a3_code, names, cfg.execution.timeout_s)
            control = {"applicable": True, "over_specified": [n for n in names if outs[n] != "ordinary_pass"]}
        adm = admit(task.module_name, task.reference_code, union,
                    re.findall(r"^def (test_h_\d+)\(\)", union, flags=re.M), cfg.execution.timeout_s) if union else {}
        for kind, code in (("a3", a3_code), ("union", union)):
            d = args.out / kind / lab
            d.mkdir(parents=True, exist_ok=True)
            (d / "hidden_tests.py").write_text(code, encoding="utf-8")
            rec = {**a2, "final_tests": a2["final_tests"] if kind == "union" else [], "a3_tests": a3,
                   "a3_control": control, "ready": bool(code)}
            (d / "a2.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
        summary[lab] = {"a2_tests": n2, "a3_tests": len(a3), "by_model": {r.name: sum(t["model"] == r.name for t in a3)
                                                                          for r in runs},
                        "control_over_specified": control.get("over_specified", []),
                        "union_not_admitted": [n for n, a in adm.items() if not a["admitted"]]}
    (args.out / "merge_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


# --- report --------------------------------------------------------------------------------------

def detections(heldout: Path) -> dict:
    """{(task, group_id): detected} for primary held-out groups."""
    rows = json.loads(heldout.read_text(encoding="utf-8"))["rows"]
    return {(r["task"], r["group_id"]): r["h_detected"] for r in rows
            if any(p.startswith("primary") for p in r["populations"])}


def condition3(a2_det: dict, a3_det: dict) -> dict:
    extra = sorted(k for k, v in a3_det.items() if v and a2_det.get(k) is False)
    tasks = sorted({t for t, _ in extra})
    return {"a3_only_groups": [f"{t}/{g}" for t, g in extra], "tasks": tasks, "ok": len(tasks) >= 3}


def report(args, cfg) -> dict:
    import audit_h
    ready = a2_ready(args.a2, cfg.extensions.development_tasks)
    tasks, _ = ec.load_tasks(cfg, args.ungated)
    a2_det = detections(args.a2 / "heldout.json")
    a3_det = detections(args.out / "a3" / "heldout.json")
    c3 = condition3(a2_det, a3_det)
    # condition 4: development cost per targeted group, projected on the evaluation tasks (counts only)
    cost = {}
    for r in sorted((args.out / "runs").iterdir()):
        recs = [json.loads(p.read_text(encoding="utf-8")) for p in r.glob("*/a3.json")]
        tg = [t for x in recs for t in x["targets"]]
        toks = sum(((a["meta"] or {}).get("usage") or {}).get("total_tokens") or 0 for t in tg for a in t["attempts"])
        cost[r.name] = {"targets": len(tg), "tokens": toks, "seconds": sum(t["seconds"] for t in tg),
                        "tokens_per_target": toks / len(tg) if tg else None,
                        "seconds_per_target": sum(t["seconds"] for t in tg) / len(tg) if tg else None}
    eval_targets = None
    if args.eval_a2:
        eval_targets = sum(min(MAX_GROUPS, len(surviving(json.loads(p.read_text(encoding="utf-8")))))
                           for p in args.eval_a2.glob("*/a2.json")
                           if json.loads(p.read_text(encoding="utf-8")).get("ready"))
    # condition 1 sheet: every A3 test + the seeded A2 sample (min(5, n) per task), judged against the docstrings
    items, L = [], ["# A3 development pilot: Q1 validity sheet (decisions 7, condition 1)", "",
                    "Per test: *valid* / *over-specified* / *invalid* against the docstrings. Write the verdicts in "
                    "`a3_items.csv`.", ""]
    for lab, a2 in ready.items():
        rec = json.loads((args.out / "a3" / lab / "a2.json").read_text(encoding="utf-8"))
        L += [f"## {lab}", "", "<details><summary>skeleton</summary>", "", "```python", tasks[lab].prompt.strip(), "```",
              "", "</details>", ""]
        for t in rec["a3_tests"]:
            iid = f"A3-{len(items) + 1}"
            items.append({"id": iid, "arm": "A3", "task": lab, "item": t["name"], "weight": 1.0, "verdict": ""})
            L += [f"### {iid}: `{t['name']}` ({t['model']}, target {t['target']})", "", "```python", t["code"].strip(),
                  "```", "", "Verdict: ______", ""]
        tests = a2["final_tests"]
        rng = audit_h.task_rng(lab, cfg.extensions.seed)
        q = sorted(rng.sample(range(len(tests)), min(audit_h.PER_TASK, len(tests))))
        for i in q:
            t = tests[i]
            iid = f"A2-{len(items) + 1}"
            items.append({"id": iid, "arm": "A2", "task": lab, "item": t["name"], "weight": len(tests) / len(q),
                          "verdict": ""})
            L += [f"### {iid}: A2 `{t['name']}`", "", "| step | asserted |", "|---|---|"]
            for k, st in enumerate(t["steps"]):
                exp = t["expected"].get(f"api:s{k}")
                L.append(f"| `{st['src'][:160]}` | {audit_h.show_token(exp) if exp else '-'} |")
            L += ["", "Verdict: ______", ""]
    (args.out / "a3_sheet.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    with (args.out / "a3_items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "arm", "task", "item", "weight", "verdict"])
        w.writeheader()
        w.writerows(items)
    merged = json.loads((args.out / "merge_summary.json").read_text(encoding="utf-8"))
    res = {"condition3": c3, "cost": cost, "evaluation_targets_projected": eval_targets,
           "control_over_specified": {k: v["control_over_specified"] for k, v in merged.items()
                                      if v["control_over_specified"]},
           "union_not_admitted": {k: v["union_not_admitted"] for k, v in merged.items() if v["union_not_admitted"]},
           "a3_tests": {k: v["a3_tests"] for k, v in merged.items()},
           "q1_items": {"A3": sum(i["arm"] == "A3" for i in items), "A2": sum(i["arm"] == "A2" for i in items)}}
    (args.out / "report.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["run", "merge", "report", "freeze-targets"])
    ap.add_argument("--version", choices=["v1", "v2"], default="v1", help="A3 version (v2: decisions 10.6)")
    ap.add_argument("--targets", type=Path, help="the frozen target list (evaluation runs, decisions 10.6)")
    ap.add_argument("--audit", type=Path, help="freeze-targets: audit_reserved.json (excluded from the cohort)")
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--llm-config", type=Path, help="the model's serving-group config (llm section, profile)")
    ap.add_argument("--model")
    ap.add_argument("--a2", type=Path, required=True, help="development A2 suite (e.g. a2/dev_k5_r7b)")
    ap.add_argument("--witness", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--eval-a2", type=Path, help="evaluation A2 build: only to count targets for condition 4")
    ap.add_argument("--max-groups", type=int, default=MAX_GROUPS)
    ap.add_argument("--attempts", type=int, default=ATTEMPTS)
    ap.add_argument("--max-tokens", type=int, default=32768)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--ungated", action="store_true")
    args = ap.parse_args(argv)
    cfg = ec.load_ext_config(args.config)
    if args.cmd == "freeze-targets":              # reads stored records only; no model code runs
        print(json.dumps(freeze_targets(args, cfg), indent=1))
        return 0
    if args.out is None:
        raise SystemExit("ERROR: --out is required")
    if args.cmd in ("run", "merge"):              # model-written code runs: scrub credentials, kill process trees
        import dataclasses
        from meta_real_eval.core import canary
        policy = dataclasses.replace(cfg.extensions.exec_policy.to_policy(), isolate_home=True)
        policy.activate()
        canary.require_canary(policy=policy, timeout_s=cfg.execution.timeout_s, warmup=True)
    if args.cmd == "run":
        from dotenv import load_dotenv
        from meta_real_eval.core.config import Config
        load_dotenv()                             # gateway credentials (gemma); a vLLM job sets its own
        if not (args.llm_config and args.model and args.witness):
            raise SystemExit("ERROR: run needs --llm-config, --model and --witness")
        llm_cfg = Config.from_yaml(args.llm_config)
        if args.model not in llm_cfg.model_ids():
            raise SystemExit(f"ERROR: {args.llm_config} does not list {args.model}")
        res = asyncio.run(run_model(args, cfg, llm_cfg))
    elif args.cmd == "merge":
        res = merge(args, cfg)
    else:
        res = report(args, cfg)
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
