"""Pydantic config model loaded from config/default.yaml."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProjectConfig(BaseModel):
    output_dir: Path = Path("./results")
    seed: int = 42
    mock: bool = False


class SamplingConfig(BaseModel):
    """A model's recommended decoding parameters (its model card). None = not sent.

    Ranges are the ones vLLM accepts; a value outside them is rejected here
    rather than by a backend that might silently clamp or ignore it.
    """

    model_config = ConfigDict(extra="forbid")

    temperature: Optional[float] = Field(default=None, ge=0.0)
    top_p: Optional[float] = Field(default=None, gt=0.0, le=1.0)
    top_k: Optional[int] = None                        # -1 (off) or >= 1
    min_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    repetition_penalty: Optional[float] = Field(default=None, gt=0.0, le=2.0)

    @field_validator("top_k")
    @classmethod
    def _top_k_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v != -1 and v < 1:
            raise ValueError("top_k must be -1 (disabled) or >= 1")
        return v

    def resolved(self) -> dict[str, Any]:
        """The fields that are set, i.e. the ones that will be sent."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


# Sent as standard OpenAI arguments; the other sampling fields go in extra_body.
STANDARD_SAMPLING_ARGS = ("temperature", "top_p", "presence_penalty")
EXTRA_BODY_SAMPLING_ARGS = ("top_k", "min_p", "repetition_penalty")

# Body fields the client sets itself; request_params may not smuggle them in.
_RESERVED_BODY_FIELDS = frozenset({
    "model", "messages", "n", "max_tokens", "max_completion_tokens", "stream",
    *STANDARD_SAMPLING_ARGS, *EXTRA_BODY_SAMPLING_ARGS,
})


class LLMModelConfig(BaseModel):
    id: str

    # The model's recommended decoding parameters. Empty -> the request (and
    # its cache key) is exactly the legacy one: the caller's temperature and
    # the server's defaults for everything else.
    sampling: SamplingConfig = Field(default_factory=SamplingConfig)

    # Extra top-level fields sent with every request for this model (OpenAI
    # ``extra_body``), e.g. ``{"reasoning_effort": "none"}`` to switch thinking
    # off on the Innkube gateway. Empty -> the request is exactly what it was
    # before this field existed, and so is its cache key, so every cached
    # completion made without parameters stays valid (and keeps meaning "the
    # server's default for that model" -- which is thinking ON for qwen38-27b
    # and OFF for gemma4-31b-it; see scripts/probe_thinking.py).
    request_params: dict[str, Any] = Field(default_factory=dict)

    # Human label for the inference condition these params create, recorded in
    # <output_dir>/llm_conditions.json. Descriptive only: the condition is
    # defined by sampling + request_params, never by this string.
    condition: Optional[str] = None

    @model_validator(mode="after")
    def _no_reserved_fields(self) -> "LLMModelConfig":
        bad = set(self.request_params) & _RESERVED_BODY_FIELDS
        if bad:
            raise ValueError(f"{self.id}: request_params may not set {sorted(bad)}; "
                             "put decoding parameters under sampling")
        return self

    @property
    def is_profiled(self) -> bool:
        """True if this model's requests differ from the legacy request."""
        return bool(self.sampling.resolved() or self.request_params)

    def effective_condition(self) -> dict[str, Any]:
        """What this model's requests are sent with (beyond the prompt and budget)."""
        return {"sampling": self.sampling.resolved(), "request_params": self.request_params}


class LLMConfig(BaseModel):
    models: list[LLMModelConfig] = Field(default_factory=list)
    max_concurrent_requests: int = 5
    requests_per_minute: int = 20
    retry_max_attempts: int = 5
    retry_base_delay_s: float = 2.0
    cache_dir: Path = Path("./cache/llm_responses")
    # Client-side request timeout (None = the SDK default, 600 s); long thinking
    # at n=10 needs more.
    request_timeout_s: Optional[float] = None

    def model(self, model_id: str) -> Optional[LLMModelConfig]:
        for m in self.models:
            if m.id == model_id:
                return m
        return None

    def request_params_for(self, model_id: str) -> dict[str, Any]:
        """The configured extra request fields for ``model_id``; {} if none.

        A model outside ``models`` (the RQ2 paraphrase generator / judge) has
        none: they are held out of the ranked set on purpose and keep their
        own, unmodified requests.
        """
        m = self.model(model_id)
        return m.request_params if m is not None else {}


class BenchmarkConfig(BaseModel):
    # Dispatched on by benchmarks.get_benchmark(): "humaneval" | "realclasseval".
    name: str = "humaneval"
    tasks: Optional[list[int]] = None   # None → all tasks
    # Tier 2 only; None → the adapter's defaults under data/realclasseval/.
    data_path: Optional[Path] = None
    manifest_path: Optional[Path] = None
    splits: Optional[list[str]] = None  # None → both: [csn, post_cut-off]
    docstring_variant: str = "full_docstr"


class ExecutionConfig(BaseModel):
    timeout_s: float = 10.0
    cpu_workers: int = 4


class Stage0Config(BaseModel):
    n_fuzz_inputs: int = 500
    # generate_mutants' own default (5) matches this; Tier 2 classes have more
    # methods to spread mutants across than a single HumanEval function, so
    # the Tier 2 config raises it (see the Tier 2 plan, Stage 0).
    max_mutants_per_operator: int = 5


class RQ1Config(BaseModel):
    operators: list[str] = ["AOR", "ROR", "SDL"]
    # LLM mutant generation budget per completion (was the MUTANT_MAX_TOKENS
    # constant; same default). Tier 2 sets it to rq2.max_tokens: one ceiling
    # for every call where a model is under test.
    max_tokens: int = 8192


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

    # What a failed cell triggers.
    #   legacy          retry a cell that came back empty or fully truncated
    #                   (the behaviour every existing result was produced with)
    #   transport_only  retry only transport failures, inside the client, with
    #                   the same request; empty/truncated/malformed outputs are
    #                   model outcomes and stay in the denominator. Re-drawing
    #                   them would resample conditional on the outcome.
    retry_policy: Literal["legacy", "transport_only"] = "legacy"

    # Two independent switches for the control arm (rq2/generator.py):
    #   request_seeds          send a per-(task, model, relation) seed with every
    #                          RQ2 request; the seed ranges of one cell's relations
    #                          never overlap, so original and control_resample can
    #                          be byte-identical prompts and still be distinct draws
    #                          (and distinct gateway cache entries).
    #   control_marker_models  which models get the neutral marker appended to the
    #                          control arm's system message: None = every model (the
    #                          legacy behaviour), [] = none.
    # Kept apart so turning seeds off can never turn the marker back on.
    request_seeds: bool = False
    control_marker_models: Optional[list[str]] = None

    # The per-cell score the rankings use: "pass@1" (binary, every test passes;
    # Tier 1's metric) or "mean_primary" (the mean per-completion D3 pass rate,
    # i.e. the fraction of valid tests passed -- RealClassEval's own metric).
    # Whichever is not primary is written alongside as the secondary ranking.
    ranking_score: Literal["pass@1", "mean_primary"] = "pass@1"

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
    # The SBC reverse-generation model, an instrument (always the legacy fixed
    # request, never the model's sampling). None = the first configured model.
    sbc_model: Optional[str] = None


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

    @model_validator(mode="after")
    def _strict_policy_needs_profiles(self) -> "Config":
        # The client applies strict transport handling (choice-count check,
        # retries on timeouts) only to profiled requests; transport_only without
        # it would silently fall back to the legacy client behaviour.
        if self.rq2.retry_policy == "transport_only":
            bare = [m.id for m in self.llm.models if not m.is_profiled]
            if bare:
                raise ValueError(f"rq2.retry_policy=transport_only needs a sampling profile "
                                 f"for every model; missing: {bare}")
        # The legacy policy re-draws a cell by changing only the cache salt; with
        # a fixed seed the backend would return the same draw, so the retry buys
        # nothing. Seeds belong to the transport_only protocol.
        if self.rq2.request_seeds and self.rq2.retry_policy != "transport_only":
            raise ValueError("rq2.request_seeds needs rq2.retry_policy=transport_only")
        return self

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
