#!/usr/bin/env python
"""Scan the RealClassEval corpus for third-party imports (Tier 2, M0).

Produces an automatically generated **candidate** dependency set -- not a
claim of completeness. An AST scan cannot see imports behind
``TYPE_CHECKING``, conditional or dynamic imports, or modules a dependency
pulls in transitively. Some imports name the class's *own project* (e.g. a
class from the astropy repository importing ``astropy``): those are
installable only if that project is published, and then only at whatever
version the index serves -- not necessarily the commit the class came from. The authoritative runtime check
is the M0 validity gate (``scripts/validate_realclasseval.py``), which
imports every reference class in the pinned environment and excludes any
that fail as ``missing_dependency``.

    .venv/bin/python scripts/scan_realclasseval_deps.py

Writes:

``requirements-tier2.in``                     candidate distributions,
                                              unpinned, most-used first.
                                              Pin on the cluster with
                                              ``pip install -r requirements-tier2.in
                                              && pip freeze > requirements-tier2.lock.txt``.
``data/realclasseval/dependency_scan.json``   per module and per task.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import warnings
from collections import Counter, defaultdict
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.benchmarks.realclasseval import DEFAULT_CORPUS_PATH, load_corpus_rows  # noqa: E402

# Import name -> PyPI distribution, where they differ. Anything not here and
# not installed locally is assumed to share its name, and flagged as such.
KNOWN_DISTRIBUTIONS = {
    "yaml": "PyYAML", "cv2": "opencv-python", "PIL": "Pillow", "sklearn": "scikit-learn",
    "skimage": "scikit-image", "bs4": "beautifulsoup4", "dateutil": "python-dateutil",
    "dotenv": "python-dotenv", "attr": "attrs", "jwt": "PyJWT", "Crypto": "pycryptodome",
    "OpenSSL": "pyOpenSSL", "serial": "pyserial", "usb": "pyusb", "magic": "python-magic",
    "docx": "python-docx", "pptx": "python-pptx", "git": "GitPython", "zmq": "pyzmq",
    "psycopg2": "psycopg2-binary", "MySQLdb": "mysqlclient", "fitz": "PyMuPDF",
    "Levenshtein": "python-Levenshtein", "telegram": "python-telegram-bot",
    "discord": "discord.py", "faiss": "faiss-cpu", "sentence_transformers": "sentence-transformers",
    "multipart": "python-multipart", "jose": "python-jose", "websocket": "websocket-client",
    "pkg_resources": "setuptools", "googleapiclient": "google-api-python-client",
    "dns": "dnspython", "lxml": "lxml", "markdown": "Markdown", "jinja2": "Jinja2",
}
HARNESS_MODULES = {"pytest", "__future__"}


def _imports(src: str) -> set[str]:
    """Top-level names of every absolute import anywhere in ``src``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _project_tokens(row: dict) -> set[str]:
    """Names that are probably the class's own project: parts of the
    repository name and directories on the class's source path."""
    tokens = {p.lower().replace("-", "_") for p in re.split(r"[/]", row.get("repository_name", "")) if p}
    path_parts = Path(str(row.get("source_file_path", "")).replace("\\", "/")).parts[:-1]
    tokens |= {p.lower() for p in path_parts if p.isidentifier()}
    return tokens


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--requirements", type=Path, default=REPO_ROOT / "requirements-tier2.in")
    parser.add_argument("--report", type=Path, default=DEFAULT_CORPUS_PATH.parent / "dependency_scan.json")
    args = parser.parse_args()

    stdlib = set(sys.stdlib_module_names)
    installed = metadata.packages_distributions()  # import name -> [distributions]

    module_tasks: dict[str, set[str]] = defaultdict(set)
    module_kind: dict[str, str] = {}
    per_task: dict[str, dict] = {}
    for row in load_corpus_rows(args.corpus):
        names = _imports(row["reference_code"]) | _imports(row["test_code"])
        names = {n for n in names
                 if n not in stdlib and n not in HARNESS_MODULES and not n.startswith("snippet_")}
        internal = {n for n in names if n.lower() in _project_tokens(row)}
        external = names - internal
        per_task[row["task_id"]] = {
            "split": row["split"],
            "third_party": sorted(external),
            "own_project": sorted(internal),
            "stdlib_only": not names,
        }
        for n in names:
            module_tasks[n].add(row["task_id"])
            # A name is own-project if it is for any task that uses it.
            if n in internal or module_kind.get(n) == "own_project":
                module_kind[n] = "own_project"
            else:
                module_kind.setdefault(n, "third_party")

    modules = {}
    for name, tasks in module_tasks.items():
        dists = installed.get(name)
        if dists:
            dist, mapping = dists[0], "installed_locally"
        elif name in KNOWN_DISTRIBUTIONS:
            dist, mapping = KNOWN_DISTRIBUTIONS[name], "known_mapping"
        else:
            dist, mapping = name, "assumed_same_name"
        modules[name] = {
            "kind": module_kind[name],
            "distribution": dist,
            "mapping": mapping,
            "n_tasks": len(tasks),
            "n_tasks_by_split": dict(Counter(per_task[t]["split"] for t in tasks)),
        }

    candidates = sorted(
        ((m, info) for m, info in modules.items() if info["kind"] == "third_party"),
        key=lambda kv: (-kv[1]["n_tasks"], kv[0].lower()),
    )
    seen: set[str] = set()
    lines = ["# Candidate Tier 2 dependencies -- generated by scripts/scan_realclasseval_deps.py.",
             "# NOT a completeness claim: the M0 gate is the authoritative runtime check.",
             "# Pin on the cluster: pip install -r requirements-tier2.in && pip freeze > requirements-tier2.lock.txt"]
    for module, info in candidates:
        if info["distribution"] in seen:
            continue
        seen.add(info["distribution"])
        flag = "  # distribution name not verified" if info["mapping"] == "assumed_same_name" else ""
        lines.append(f"{info['distribution']:<32} # {info['n_tasks']} task(s), import {module}{flag}")
    own = sorted(((m, i) for m, i in modules.items() if i["kind"] == "own_project"),
                 key=lambda kv: (-kv[1]["n_tasks"], kv[0].lower()))
    lines += ["", "# Own-project imports (the class's own repository). Installable only if the",
              "# project is published, and version-sensitive; left commented out -- uncomment",
              "# deliberately, and let the M0 gate decide which classes actually import."]
    lines += [f"# {i['distribution']:<30} # {i['n_tasks']} task(s), import {m}" for m, i in own]
    args.requirements.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = defaultdict(Counter)
    for t in per_task.values():
        key = ("stdlib_only" if t["stdlib_only"]
               else "imports_own_project" if t["own_project"]
               else "third_party_installable_candidate")
        summary[t["split"]][key] += 1
    args.report.write_text(json.dumps({
        "summary_by_split": {k: dict(v) for k, v in summary.items()},
        "modules": dict(sorted(modules.items())),
        "tasks": per_task,
    }, indent=2) + "\n", encoding="utf-8")

    for split, counts in summary.items():
        print(f"{split:>13}: {dict(counts)}")
    n_internal = sum(1 for i in modules.values() if i["kind"] == "own_project")
    print(f"{len(seen)} candidate distributions -> {args.requirements}")
    print(f"{n_internal} own-project module name(s), listed commented-out")
    print(f"report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
