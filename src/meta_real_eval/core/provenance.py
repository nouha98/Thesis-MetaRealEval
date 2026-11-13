"""Run manifests for the thesis extensions (plan rev. 8).

Every extension output root (``results_tier2_ext/<stage>/...``) gets a
``run_manifest.json`` that says exactly what produced it:

  git        commit, ``-dirty`` flag and the dirty tracked files
  config     path and sha256 of the config the run read (if any)
  inputs     per named input: number of files and one digest over the sorted
             (relative path, sha256) list; the per-file hashes go to a
             sibling ``input_hashes.json`` so the manifest stays readable
  seeds      whatever seeds the caller used
  packages   versions of python and the packages that can change a result
  host/time  provenance only

This module only reads inputs and writes inside ``out_dir``; it never
touches an existing result directory. The historical pipeline does not use
it (its own provenance, ``core/conditions.py``, is unchanged).
"""

from __future__ import annotations

import hashlib
import json
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Iterable, Mapping, Optional, Union

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_NAME = "run_manifest.json"
INPUT_HASHES_NAME = "input_hashes.json"
DEFAULT_PACKAGES = ("numpy", "scipy", "pytest", "hypothesis", "pydantic", "openai")
UNTRACKED_CODE_PREFIXES = ("src/", "scripts/", "config/")

InputSpec = Union[Path, str, Iterable[Union[Path, str]]]


def file_sha256(path: Union[Path, str]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# Text files are checked out with CRLF on Windows (core.autocrlf) and LF on the cluster, so a pin
# on raw bytes would differ between machines for identical content. Pins and config records use
# this line-ending-normalised content hash for text files; binary files keep their raw hash.
TEXT_SUFFIXES = (".yaml", ".yml", ".json", ".md", ".txt", ".py", ".csv", ".cfg", ".toml", ".in", ".sh")


def content_sha256(path: Union[Path, str]) -> str:
    """sha256 of the file's content: CRLF -> LF for text files, the DECOMPRESSED bytes for .gz
    (gzip headers and compression levels differ between machines that staged the same data),
    raw bytes otherwise. A .gz that is not valid gzip falls back to its raw hash."""
    import gzip
    p = Path(path)
    if p.suffix.lower() == ".gz":
        try:
            return hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()
        except (OSError, EOFError):
            return file_sha256(p)
    if p.suffix.lower() in TEXT_SUFFIXES:
        return hashlib.sha256(p.read_bytes().replace(bytes([13, 10]), bytes([10]))).hexdigest()
    return file_sha256(p)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def digest_files(paths: Iterable[Union[Path, str]]) -> dict:
    """sha256 per file plus one digest of the sorted ``path:sha`` lines.
    Directories are expanded recursively; missing paths are listed, not hashed."""
    files: dict[str, str] = {}
    missing: list[str] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for q in sorted(x for x in p.rglob("*") if x.is_file()):
                files[_rel(q)] = file_sha256(q)
        elif p.is_file():
            files[_rel(p)] = file_sha256(p)
        else:
            missing.append(_rel(p))
    lines = "\n".join(f"{k}:{v}" for k, v in sorted(files.items()))
    return {"n_files": len(files), "digest": hashlib.sha256(lines.encode()).hexdigest(),
            "missing": sorted(missing), "files": files}


def git_state(repo: Path = REPO_ROOT) -> dict:
    def run(*args) -> str:
        try:
            return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                                  timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    head = run("rev-parse", "HEAD")
    status = run("status", "--porcelain", "--untracked-files=all").splitlines()
    dirty = [line for line in status if not line.startswith("??")]
    # untracked code/config can change a result just as much as a modified tracked file
    untracked = [line[3:] for line in status
                 if line.startswith("??") and line[3:].startswith(UNTRACKED_CODE_PREFIXES)]
    return {"commit": head + ("-dirty" if dirty or untracked else ""), "head": head,
            "dirty_tracked_files": dirty, "untracked_code_files": untracked}


def package_versions(names: Iterable[str] = DEFAULT_PACKAGES) -> dict:
    out = {"python": platform.python_version()}
    for n in names:
        try:
            out[n] = metadata.version(n)
        except metadata.PackageNotFoundError:
            out[n] = None
    return out


class PinMismatch(SystemExit):
    """A pinned input exists but its content changed."""


def verify_pins(pins: Mapping[str, str], *, require_all: bool = False,
                root: Path = REPO_ROOT) -> dict[str, str]:
    """Check pinned files (path relative to the repo root -> content sha256, see
    :func:`content_sha256`: line endings do not matter for text files).

    Returns path -> "ok" | "missing". A present file with another hash raises
    :class:`PinMismatch`; a missing one raises only with ``require_all`` (the gate
    manifest, for example, exists on the cluster but not on every machine)."""
    status: dict[str, str] = {}
    bad: list[str] = []
    for rel, expected in sorted(pins.items()):
        p = Path(rel) if Path(rel).is_absolute() else root / rel
        if not p.is_file():
            if require_all:
                bad.append(f"{rel}: missing")
            status[rel] = "missing"
            continue
        got = content_sha256(p)
        if got != expected:
            bad.append(f"{rel}: content sha256 {got} != pinned {expected}")
            continue
        status[rel] = "ok"
    if bad:      # every mismatch at once, not just the first
        raise PinMismatch("ERROR: pinned inputs differ:" + "".join(chr(10) + "  " + line for line in bad))
    return status


def _config_record(config_path: Union[Path, str]) -> dict:
    """Path + sha256 of the config, and of its ``base_config`` chain if it overlays one."""
    import yaml
    p = Path(config_path)
    rec = {"path": _rel(p), "sha256": content_sha256(p), "file_sha256": file_sha256(p)}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    base = data.get("base_config") if isinstance(data, dict) else None
    if base:
        rec["base"] = _config_record(p.parent / base)
    return rec


def _as_list(spec: InputSpec) -> list[Path]:
    if isinstance(spec, (str, Path)):
        return [Path(spec)]
    return [Path(p) for p in spec]


def write_run_manifest(
    out_dir: Union[Path, str],
    *,
    stage: str,
    config_path: Optional[Union[Path, str]] = None,
    inputs: Optional[Mapping[str, InputSpec]] = None,
    seeds: Optional[Mapping[str, object]] = None,
    settings: Optional[Mapping[str, object]] = None,
    argv: Optional[list[str]] = None,
    packages: Iterable[str] = DEFAULT_PACKAGES,
    checks: Optional[Mapping[str, object]] = None,
) -> Path:
    """Write ``run_manifest.json`` (+ ``input_hashes.json``) into ``out_dir`` and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    digests = {name: digest_files(_as_list(spec)) for name, spec in (inputs or {}).items()}
    manifest = {
        "format": 1,
        "stage": stage,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "argv": list(argv if argv is not None else sys.argv),
        "git": git_state(),
        "config": _config_record(config_path) if config_path else None,
        "inputs": {name: {k: v for k, v in d.items() if k != "files"} for name, d in digests.items()},
        "seeds": dict(seeds or {}),
        "settings": dict(settings or {}),
        "packages": package_versions(packages),
        # runtime checks made by the run itself (e.g. the execution canary, pin verification)
        "checks": dict(checks or {}),
    }
    (out_dir / INPUT_HASHES_NAME).write_text(
        json.dumps({name: d["files"] for name, d in digests.items()}, indent=1, sort_keys=True),
        encoding="utf-8")
    path = out_dir / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=1, default=str), encoding="utf-8")
    return path
