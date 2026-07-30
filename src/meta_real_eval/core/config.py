"""Pydantic config model loaded from config/default.yaml."""

from __future__ import annotations

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
