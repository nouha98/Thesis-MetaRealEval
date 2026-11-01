#!/usr/bin/env python
"""Gate C (manual review) for a paraphrase corpus: carry verdicts over, sheet, apply.

A filled review sheet (scripts/paraphrase_report.py's format, verdicts typed into
its table) records a person's verdict on exact rewrite texts. A later corpus can
contain the same texts again -- the gateway cache replays a generation for a
task built before -- so a verdict carries over to a variant only when its text
is byte-identical to the reviewed one. A variant in a reviewed (task, variant)
slot whose text differs was never reviewed, and is always put on the next sheet.

A verdict is the reviewer's answer to the sheet's one question: does the rewrite
demand exactly the same class as the original? "not equivalent" means a change
in meaning, nothing else -- variants that failed Gate A or B never reach the
corpus, so they never appear on a sheet. A slot is (task, variant id), and a
variant is the WHOLE rewritten skeleton (every docstring of the class), so a
verdict is matched on task + variant id + full text, never on text alone.

    sheet   write a review sheet: every changed slot, plus a family-balanced
            random sample of the variants no sheet has reviewed
    apply   remove every variant a sheet marks "not equivalent" (identical text
            only), recompute coverage and the sha256, and record what was removed
            in manifest.gate_c; prints the sha to pin

    .venv/bin/python scripts/gate_c.py sheet --corpus data/paraphrases/realclasseval_v1.json \
        --reviewed doc/gate_c/realclasseval_pilot2.review_sheet.md --n 120 \
        --out data/paraphrases/realclasseval_v1.review_sheet.md
    .venv/bin/python scripts/gate_c.py apply --corpus data/paraphrases/realclasseval_v1.json \
        --sheet doc/gate_c/realclasseval_pilot2.review_sheet.md \
        --sheet doc/gate_c/realclasseval_v1.review_sheet.md
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from meta_real_eval.rq2.corpus import tasks_sha256  # noqa: E402
from generate_paraphrases import _coverage_block  # noqa: E402
from paraphrase_report import sample_variants, write_sheet  # noqa: E402

_ITEM_RE = re.compile(
    r"^## (\d+)\. (\S+) — `([^`]+)` \((\w+)\)\n.*?\*\*Rewrite\*\*\n\n```python\n(.*?)\n```\n\n_judge:",
    re.MULTILINE | re.DOTALL)
_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|(.*)\|\s*$", re.MULTILINE)


def parse_sheet(path: Path) -> list[dict]:
    """The reviewed items of a filled sheet: slot, exact rewrite text, verdict."""
    doc = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    rows = {int(m[1]): (m[2].strip(), m[3].strip()) for m in _ROW_RE.finditer(doc)}
    items = []
    for m in _ITEM_RE.finditer(doc):
        raw, note = rows.get(int(m[1]), ("", ""))
        verdict = ("reject" if raw.lower().startswith("not equivalent")
                   else "accept" if raw.lower().startswith("equivalent") else None)
        items.append({"n": int(m[1]), "task_id": m[2], "variant_id": m[3], "family": m[4],
                      "text": m[5], "verdict": verdict, "note": note, "sheet": path.name})
    return items


def classify(corpus: dict, reviewed: list[dict]) -> dict[str, list]:
    """Each corpus variant against the reviewed items: accepted / rejected
    (identical text), changed (a reviewed slot, different text), unreviewed."""
    by_slot: dict[tuple[str, str], list[dict]] = {}
    for item in reviewed:
        by_slot.setdefault((item["task_id"], item["variant_id"]), []).append(item)
    out: dict[str, list] = {"accepted": [], "rejected": [], "changed": [], "unreviewed": []}
    for task_id, entry in corpus["tasks"].items():
        for v in entry["variants"]:
            items = by_slot.get((task_id, v["variant_id"]), [])
            same = [i for i in items if i["text"] == v["text"].rstrip("\n") and i["verdict"]]
            row = (task_id, v, same[-1] if same else None)
            if same:
                out["rejected" if same[-1]["verdict"] == "reject" else "accepted"].append(row)
            else:
                out["changed" if items else "unreviewed"].append(row)
    return out


def _print_counts(groups: dict[str, list]) -> None:
    for name, rows in groups.items():
        print(f"  {name:10s} {len(rows)}")


def cmd_sheet(args) -> int:
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    reviewed = [i for s in args.reviewed for i in parse_sheet(s)]
    groups = classify(corpus, reviewed)
    print(f"{args.corpus}: {sum(len(e['variants']) for e in corpus['tasks'].values())} variants "
          f"against {len(reviewed)} reviewed item(s)")
    _print_counts(groups)

    pool: dict = {"tasks": {}}
    for task_id, v, _ in groups["unreviewed"]:
        pool["tasks"].setdefault(task_id, {"original": corpus["tasks"][task_id]["original"],
                                           "variants": []})["variants"].append(v)
    flat = lambda task_id, v: {"task_id": task_id, "original": corpus["tasks"][task_id]["original"], **v}  # noqa: E731
    sampled = sample_variants(pool, args.n, args.seed) if args.n > 0 else []
    items = [flat(t, v) for t, v, _ in groups["changed"]] + sampled
    random.Random(args.seed).shuffle(items)
    write_sheet(items, corpus, args.out)
    print(f"\nWrote {args.out}: {len(groups['changed'])} changed + "
          f"{len(items) - len(groups['changed'])} sampled = {len(items)} item(s)")
    return 0


def cmd_apply(args) -> int:
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    manifest = corpus["manifest"]
    if manifest.get("sha256") != tasks_sha256(corpus):
        raise SystemExit(f"{args.corpus}: contents do not match its manifest sha256; "
                         "not applying Gate C to a hand-edited file")
    reviewed = [i for s in args.sheet for i in parse_sheet(s)]
    unfilled = [f"{i['sheet']}#{i['n']}" for i in reviewed if i["verdict"] is None]
    if unfilled:
        raise SystemExit(f"verdict missing for {len(unfilled)} item(s): {', '.join(unfilled)}")
    groups = classify(corpus, reviewed)
    print(f"{args.corpus} against {len(reviewed)} reviewed item(s):")
    _print_counts(groups)

    drop = {(t, v["variant_id"]) for t, v, _ in groups["rejected"]}
    for task_id, entry in corpus["tasks"].items():
        entry["variants"] = [v for v in entry["variants"] if (task_id, v["variant_id"]) not in drop]
    gate_c = manifest.setdefault("gate_c", {"sha256_before": manifest["sha256"],
                                            "sheets": [], "removed": []})
    gate_c["sheets"] = sorted(set(gate_c["sheets"]) | {s.name for s in args.sheet})
    gate_c["removed"] += [{"task_id": t, "variant_id": v["variant_id"], "note": i["note"],
                           "sheet": i["sheet"]} for t, v, i in groups["rejected"]]
    gate_c["reviewed_accepted"] = len(groups["accepted"])
    families = manifest["families"]
    manifest["coverage"] = _coverage_block(corpus["tasks"], manifest["n_per_family"], families)
    manifest["sha256"] = tasks_sha256(corpus)

    cov = manifest["coverage"]
    print(f"\nremoved {len(drop)}; variants now "
          f"{sum(len(e['variants']) for e in corpus['tasks'].values())}; coverage "
          f"{cov['n_tasks_meeting_threshold']}/{cov['n_tasks_total']} tasks meet "
          f">= {cov['min_families_covered']}/{len(families)} families")
    for t, v, i in groups["rejected"]:
        print(f"  - {t} {v['variant_id']}: {i['note']}")
    if groups["changed"]:
        print(f"WARNING: {len(groups['changed'])} variant(s) in reviewed slots have new, "
              "unreviewed text (put them on a sheet)")
    if args.dry_run:
        print("\n--dry-run: corpus not written")
        return 0
    tmp = args.corpus.with_suffix(".tmp")
    tmp.write_text(json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(args.corpus)
    print(f"\nWrote {args.corpus}\nPin it in the config:\n"
          f"  rq2.corpus_sha256: \"{manifest['sha256']}\"")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("--corpus", type=Path, required=True)
    s.add_argument("--reviewed", type=Path, action="append", default=[])
    s.add_argument("--n", type=int, default=120, help="sampled unreviewed variants, family-balanced")
    s.add_argument("--seed", type=int, default=42)
    s.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("apply")
    a.add_argument("--corpus", type=Path, required=True)
    a.add_argument("--sheet", type=Path, action="append", required=True)
    a.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    return cmd_sheet(args) if args.cmd == "sheet" else cmd_apply(args)


if __name__ == "__main__":
    raise SystemExit(main())
