"""Protected grading inputs (extensions plan rev. 9, execution protection).

Grading inputs -- hidden test bundles, references, contracts -- must reach a
grader unchanged, and must never be visible where agent-loop code runs.

* :func:`protected_inputs` makes the given files read-only for the duration
  of a grading batch and checks their sha256 before and after; any change
  (or a deleted file) raises :class:`ArtifactTampered`. Modes are restored on
  exit.
* :func:`assert_absent` checks that an agent working directory contains none
  of the forbidden files (hidden tests, references), by name pattern and by
  content hash.

Read-only bits are a tripwire, not a sandbox: they stop accidental writes and
the hash check detects anything else.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Union

PathLike = Union[str, Path]


class ArtifactTampered(RuntimeError):
    """A protected grading input changed, vanished, or appeared where it must not."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _files(paths: Iterable[PathLike]) -> list[Path]:
    out: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(q for q in p.rglob("*") if q.is_file())
        elif p.is_file():
            out.append(p)
        else:
            raise ArtifactTampered(f"protected input missing before grading: {p}")
    return out


@contextmanager
def protected_inputs(paths: Iterable[PathLike]) -> Iterator[dict[str, str]]:
    """Yield {path: sha256} of every protected file; verify on exit."""
    files = _files(paths)
    before = {str(f): _sha(f) for f in files}
    modes = {str(f): f.stat().st_mode for f in files}
    for f in files:
        os.chmod(f, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    try:
        yield dict(before)
    finally:
        problems = []
        for f in files:
            if not f.exists():
                problems.append(f"{f}: deleted")
                continue
            os.chmod(f, modes[str(f)])
            if _sha(f) != before[str(f)]:
                problems.append(f"{f}: content changed")
        if problems:
            raise ArtifactTampered("protected grading inputs changed: " + "; ".join(problems))


def assert_absent(workdir: PathLike, forbidden_patterns: Iterable[str] = (),
                  forbidden_hashes: Iterable[str] = ()) -> None:
    """Raise if ``workdir`` holds a file matching a forbidden name pattern or content hash."""
    pats, hashes = list(forbidden_patterns), set(forbidden_hashes)
    for f in Path(workdir).rglob("*"):
        if not f.is_file():
            continue
        if any(fnmatch.fnmatch(f.name, p) for p in pats):
            raise ArtifactTampered(f"forbidden file in agent workdir: {f}")
        if hashes and _sha(f) in hashes:
            raise ArtifactTampered(f"protected content in agent workdir: {f}")
