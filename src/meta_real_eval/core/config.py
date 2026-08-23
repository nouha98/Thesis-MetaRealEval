"""Pydantic config model loaded from config/default.yaml."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    output_dir: Path = Path("./results")
    seed: int = 42
    mock: bool = False


class LLMModelConfig(BaseModel):
    id: str


class LLMConfig(BaseModel):
    models: list[LLMModelConfig] = Field(default_factory=list)
    max_concurrent_requests: int = 5
    requests_per_minute: int = 20
    retry_max_attempts: int = 5
    retry_base_delay_s: float = 2.0
    cache_dir: Path = Path("./cache/llm_responses")


class BenchmarkConfig(BaseModel):
    name: str = "humaneval"
    tasks: Optional[list[int]] = None   # None → all tasks


class ExecutionConfig(BaseModel):
    timeout_s: float = 10.0
    cpu_workers: int = 4


class Stage0Config(BaseModel):
    n_fuzz_inputs: int = 500


class RQ1Config(BaseModel):
    operators: list[str] = ["AOR", "ROR", "SDL"]


class RQ2Config(BaseModel):
    n_completions: int = 10
    temperature: float = 0.8
    relations: list[str] = ["original", "persona", "formal", "reorder", "terse"]


class RQ3Config(BaseModel):
    n_shared_inputs: int = 200
    divergence_threshold: Optional[float] = None


class RQ4Config(BaseModel):
    degradation_levels: list[float] = [0.0, 0.2, 0.5, 0.8]


class Config(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    benchmark: BenchmarkConfig = Field(default_factory=BenchmarkConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    stage0: Stage0Config = Field(default_factory=Stage0Config)
    rq1: RQ1Config = Field(default_factory=RQ1Config)
    rq2: RQ2Config = Field(default_factory=RQ2Config)
    rq3: RQ3Config = Field(default_factory=RQ3Config)
    rq4: RQ4Config = Field(default_factory=RQ4Config)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data or {})

    def model_ids(self) -> list[str]:
        return [m.id for m in self.llm.models]


# ---------------------------------------------------------------------------
# Calibration write-back
# ---------------------------------------------------------------------------

# Matches the value of a `divergence_threshold:` line, keeping indentation and
# any trailing comment. A full YAML round-trip (load -> dump) would work too but
# would strip every explanatory comment in the file, so the edit is textual.
_THRESHOLD_RE = re.compile(
    r"^(?P<indent>[ \t]*)divergence_threshold:[ \t]*"
    r"(?P<value>[^#\n]*?)[ \t]*(?P<comment>#[^\n]*)?$",
    re.MULTILINE,
)


class CalibrationError(RuntimeError):
    """Raised when the threshold cannot be written back safely."""


def write_divergence_threshold(config_path: str | Path, value: float) -> Optional[float]:
    """Set ``rq3.divergence_threshold`` in ``config_path`` in place.

    Editing the text (rather than re-dumping the parsed YAML) keeps the file's
    comments, which carry the calibration instructions themselves.

    Returns the previous value.  Raises CalibrationError if the key is missing or
    ambiguous, or if the file does not read back with the intended value — the
    threshold decides which tasks get MT augmentation, so a half-applied edit
    must not pass silently.
    """
    path = Path(config_path)
    text = path.read_text(encoding="utf-8")

    matches = list(_THRESHOLD_RE.finditer(text))
    if not matches:
        raise CalibrationError(
            f"no 'divergence_threshold:' key in {path} — add it under rq3: first"
        )
    if len(matches) > 1:
        raise CalibrationError(
            f"{len(matches)} 'divergence_threshold:' keys in {path} — cannot tell "
            "which one belongs to rq3:; fix the file by hand"
        )

    previous = Config.from_yaml(path).rq3.divergence_threshold
    match = matches[0]
    comment = f"  {match.group('comment')}" if match.group("comment") else ""
    replacement = f"{match.group('indent')}divergence_threshold: {value!r}{comment}"
    text = text[: match.start()] + replacement + text[match.end():]
    path.write_text(text, encoding="utf-8")

    written = Config.from_yaml(path).rq3.divergence_threshold
    if written is None or abs(written - value) > 1e-12:
        raise CalibrationError(
            f"wrote {value!r} to {path} but it reads back as {written!r}"
        )
    return previous
