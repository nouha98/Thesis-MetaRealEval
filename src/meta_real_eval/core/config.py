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


BASELINE_RELATION = "original"

# The unmodified prompt, re-submitted as its own variant.  Its tau_b is the
# sampling-noise floor: without it every relation is implicitly compared against
# a perfect 1.0, which is why a grand mean of 0.909 reads as "stable".
CONTROL_RELATION = "control_resample"


class RQ2Config(BaseModel):
    n_completions: int = 10
    temperature: float = 0.8

    # Generation budget per completion. Mirrors rq1/llm_mutator.py's
    # MUTANT_MAX_TOKENS, and for the same reason: a model that reasons before
    # answering spends this budget on deliberation first, so a low cap returns
    # a completion truncated mid-thought -- which is indistinguishable from a
    # wrong answer once it fails to parse, and enters the leaderboard as a real
    # zero. Err high; an unused budget costs nothing.
    max_tokens: int = 8192

    # Template control arm (src/meta_real_eval/rq2/paraphraser.py).  Kept so the
    # LLM corpus can be compared against it — "templates understate instability
    # by X" is then a measured result rather than a speculative limitation.
    template_relations: list[str] = ["persona", "formal", "reorder", "terse"]

    # LLM paraphrase corpus (src/meta_real_eval/rq2/corpus.py).  None → template
    # arm only, i.e. the pre-corpus behaviour.
    paraphrase_corpus: Optional[Path] = None
    corpus_sha256: Optional[str] = None
    include_control_resample: bool = True

    # Models used to build the corpus.  Both must sit OUTSIDE llm.models: judging
    # paraphrases with the models being ranked would filter on the dependent
    # variable and drive RQ2 toward a null by construction.
    generator_model: Optional[str] = None
    judge_model: Optional[str] = None

    @property
    def relations(self) -> list[str]:
        """Every relation key RQ2 generates, in a stable order.

        Derived rather than configured so that ``rq2/ranking.py``,
        ``rq4/interaction.py`` and ``rq4/runner.py`` — which all read
        ``cfg.rq2.relations`` and filter out the baseline — keep working unchanged
        as the corpus grows.  The corpus is read (and cached) on demand; the
        import is local because ``rq2.corpus`` imports back through this module.
        """
        relations = [BASELINE_RELATION]
        if self.include_control_resample:
            relations.append(CONTROL_RELATION)
        relations.extend(self.template_relations)
        if self.paraphrase_corpus is not None:
            from ..rq2.corpus import corpus_variant_ids, load_corpus
            relations.extend(corpus_variant_ids(load_corpus(self.paraphrase_corpus)))
        return relations


class RQ3Config(BaseModel):
    n_shared_inputs: int = 200
    divergence_threshold: Optional[float] = None
    # Divergence cost is O(n_solutions * n_shared_inputs) subprocess spawns, so
    # RQ3 must not inherit RQ2's full variant count: at 20 relations x 3 models x
    # 200 inputs x 164 tasks that is ~2M spawns.  One seeded variant per family
    # keeps the per-task solution count near the k=15 the tau_div calibration was
    # derived at.  Templates are excluded — they are RQ2's control arm.
    variant_sample_per_family: int = 1


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
