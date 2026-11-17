"""Solution groups for Stage 2b (section 9.2): every stored RQ2 completion of a task, built into a
runnable module, grouped by the docstring-insensitive normalised program (the fault-group rule).
A group is one candidate fault; members keep (relation, model, index) and the stored P verdict.
"""

from __future__ import annotations

import hashlib
from typing import Callable

from .fault_groups import group_id, normalise_program


def build_solution_groups(task: str, completions: dict, pass_rates: dict, build: Callable[[str], str]) -> dict:
    """``completions``: {relation: {model: [text, ...]}} (rq2/generate/<task>/completions.json);
    ``pass_rates``: the matching rq2/evaluate file (``per_completion`` = stored P verdict);
    ``build``: completion text -> module source. Returns {group_id: group}, deterministic."""
    groups: dict[str, dict] = {}
    for rel in sorted(completions):
        for model in sorted(completions[rel]):
            verdicts = (pass_rates.get(rel, {}).get(model) or {}).get("per_completion") or []
            for i, text in enumerate(completions[rel][model]):
                code = build(text)
                gid = group_id(task, normalise_program(code))
                g = groups.setdefault(gid, {"code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                                            "members": []})
                g["members"].append({"relation": rel, "model": model, "index": i,
                                     "stored_p_pass": bool(verdicts[i]) if i < len(verdicts) and verdicts[i] is not None else None})
    for g in groups.values():
        g["models"] = sorted({m["model"] for m in g["members"]})
        g["representative"] = {k: g["members"][0][k] for k in ("relation", "model", "index")}
    return dict(sorted(groups.items()))


def digest(groups: dict) -> str:
    """Order-independent fingerprint of a task's groups (ids, code hashes, member provenance)."""
    rows = [f"{gid}:{g['code_sha256']}:" + ",".join(f"{m['relation']}/{m['model']}/{m['index']}" for m in g["members"])
            for gid, g in sorted(groups.items())]
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()
