"""Async Innkube LLM client with rate limiting, retry, and disk caching."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import (
    APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError,
)

from .cache import ResponseCache
from .config import EXTRA_BODY_SAMPLING_ARGS, STANDARD_SAMPLING_ARGS, LLMConfig

logger = logging.getLogger(__name__)

# Some models on this endpoint write their chain-of-thought inline in
# `message.content`, closed by a literal </think> tag, rather than in the
# separate `reasoning_content` field OpenAI's schema has room for (confirmed:
# soofi-s-isar-preview does this; qwen36-35b uses the separate field instead,
# leaving `content` blank — see _message_text, which reads that field when
# `content` is empty; gemma4-31b-it / qwen3-next-80b-a3b-instruct never emit
# either). Left unstripped, every caller downstream — pass@1 execution,
# paraphrase validation, mutant extraction — would silently treat 10-30KB of
# deliberation as the answer. Only the text after the LAST closing tag is kept;
# an unclosed <think> with no matching tag is left alone rather than guessed at.
_THINK_BLOCK_RE = re.compile(r"^.*</think>", re.DOTALL)


def _strip_reasoning(text: str) -> str:
    return _THINK_BLOCK_RE.sub("", text, count=1)


_THINK_CLOSE = "</think>"

# Values of ChoiceRecord["raw_source"].
SOURCE_CONTENT = "content"
SOURCE_REASONING = "reasoning_field"
SOURCE_NONE = "none"
SOURCE_UNKNOWN = "unknown"          # cache entry written before records existed

# Values of ChoiceRecord["disposition"] -- the client's decision, kept apart
# from the raw-response facts (raw_source, delimiter_found, finish_reason).
DISP_ANSWER = "answer"
DISP_TRUNCATED = "truncated"                    # text kept as before, but cut at the token cap
DISP_UNUSABLE_TRUNCATED = "unusable_truncated"  # reasoning-field text, no answer boundary, length
DISP_UNUSABLE_AMBIGUOUS = "unusable_ambiguous"  # reasoning-field text, no answer boundary, stop
DISP_EMPTY = "empty"
DISP_UNKNOWN = "unknown"


def _raw_message(message) -> tuple[str, str]:
    """``(text, raw_source)`` -- wherever this endpoint actually put the text.

    Most models answer in ``message.content``. qwen36-35b put its text in the
    separate ``reasoning_content`` field instead (per the module comment above)
    and left ``content`` empty -- reading only ``content`` for it silently
    returns "" for every completion. The openai SDK's response models allow
    extra fields, so the field is already available as an attribute when the
    API sends it; nothing to parse out of raw JSON. Newer vLLM releases name
    that field ``reasoning``; both spellings are read.

    Whether reasoning-field text is a final *answer* is NOT decided here; see
    ``_classify_choice``.
    """
    content = message.content or ""
    if content.strip():
        return content, SOURCE_CONTENT
    reasoning = (
        getattr(message, "reasoning_content", None)
        or getattr(message, "reasoning", None)
        or ""
    )
    if reasoning:
        return reasoning, SOURCE_REASONING
    return "", SOURCE_NONE


def _message_text(message) -> str:
    """The raw text of a message, from ``content`` or else the reasoning field."""
    return _raw_message(message)[0]


def _classify_choice(message, finish_reason: Optional[str]) -> tuple[str, dict]:
    """Decide what, if anything, of one choice is a usable final answer.

    Returns ``(text, record)``. ``record`` keeps the raw-response facts
    (``raw_source``, ``finish_reason``, ``delimiter_found``) apart from the
    decision taken (``disposition``).

    * Text from ``content``: handled exactly as before (everything up to the
      last ``</think>`` is dropped). If the model was cut off at the token cap
      the text is still returned, so existing scoring is unchanged, but the
      record says ``truncated`` so it is never mistaken for a clean answer.
    * Text from the reasoning field: ``finish_reason == "stop"`` does not make
      it an answer -- a finished reasoning trace can contain no answer at all.
      It is accepted only when there is a reliable answer boundary: a closing
      ``</think>`` followed by non-empty text. Anything else becomes "" and is
      recorded as unusable; nothing is guessed. A model-specific exception, if a
      real response ever proves one is needed, belongs here, documented and
      tested on its own.
    """
    finish = finish_reason or "unknown"
    raw, source = _raw_message(message)
    delimiter = _THINK_CLOSE in raw

    def record(disposition: str) -> dict:
        return {
            "raw_source": source,
            "finish_reason": finish,
            "delimiter_found": delimiter,
            "disposition": disposition,
        }

    if source == SOURCE_NONE:
        return "", record(DISP_EMPTY)

    text = _strip_reasoning(raw)
    if source == SOURCE_CONTENT:
        return text, record(DISP_TRUNCATED if finish == "length" else DISP_ANSWER)

    # Reasoning field: only text after a closing tag counts as an answer.
    if delimiter and text.strip():
        return text, record(DISP_TRUNCATED if finish == "length" else DISP_ANSWER)
    return "", record(DISP_UNUSABLE_TRUNCATED if finish == "length" else DISP_UNUSABLE_AMBIGUOUS)


def _reasoning_field_chars(message) -> Optional[int]:
    """Length of the reasoning field; None if the response has no such field.

    Characters, never converted to tokens. An absent or empty field does not
    prove thinking was off (a model can reason inline, or a server without a
    reasoning parser can leave it in ``content``).
    """
    text = getattr(message, "reasoning_content", None)
    if text is None:
        text = getattr(message, "reasoning", None)
    return None if text is None else len(text)


LENGTH_TAIL_CHARS = 2000


def _length_tail(message) -> str:
    """The last characters a length-truncated choice produced: its reasoning
    field if it has one, else its content. Kept so a truncation can be read as
    a repetition loop or as long, coherent work cut off (audit_rq2_generation)."""
    text = (getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None)
            or getattr(message, "content", None) or "")
    return text[-LENGTH_TAIL_CHARS:]


def _usage_dict(usage) -> Optional[dict]:
    """The response's usage block exactly as returned; None if there is none."""
    if usage is None:
        return None
    dump = getattr(usage, "model_dump", None)
    return dump() if callable(dump) else dict(usage)


def _reasoning_tokens(usage: Optional[dict]) -> Optional[int]:
    """Only if the API reports them; never estimated. Missing -> None, not 0."""
    details = (usage or {}).get("completion_tokens_details") or {}
    return details.get("reasoning_tokens")


@dataclass(frozen=True)
class ResolvedRequest:
    """One request as it will be sent and cached.

    Built by :func:`resolve_request` and used by BOTH the cache key and the API
    call, so the two can never disagree about what was asked.
    """

    profiled: bool                 # a profile applies -> strict transport handling
    std: dict[str, Any]            # standard OpenAI arguments (besides model/messages)
    extra: dict[str, Any]          # extra_body fields
    key_params: dict[str, Any]     # cache-key fields besides model/messages


def logical_prompt_sha256(messages: list[dict]) -> str:
    """Hash of the chat messages before any chat template: the logical prompt.

    The same logical prompt renders to different tokens under each model's
    template, so this is what is compared across models and endpoints.
    """
    blob = json.dumps(messages, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def resolve_request(
    config: LLMConfig, model: str, *, temperature: float, max_tokens: int, n: int,
    cache_salt: Optional[str] = None, use_profile: bool = True, seed: Optional[int] = None,
) -> ResolvedRequest:
    """Apply ``model``'s recommended sampling and request_params to a request.

    Precedence: the model's own temperature overrides the caller's, which stays
    the fallback for a model without one. top_p / presence_penalty are standard
    arguments; top_k / min_p / repetition_penalty and request_params go in
    extra_body. ``use_profile=False`` (an instrument call, e.g. SBC) sends the
    legacy request whatever the model's profile.

    Cache key: a model without a profile gets exactly the legacy key, so every
    existing cache entry stays valid. With a profile the key also carries the
    sampling / request_params, so a recommended-config run can never be served
    an old T=0.8 response.

    ``seed``, when given, is a standard argument and part of the key; when
    None neither the request nor the key changes.
    """
    m = config.model(model)
    profiled = use_profile and m is not None and m.is_profiled
    std: dict[str, Any] = {"temperature": temperature, "max_tokens": max_tokens, "n": n}
    extra: dict[str, Any] = {}
    key: dict[str, Any] = {}
    if profiled:
        sampling = m.sampling.resolved()
        for k in STANDARD_SAMPLING_ARGS:
            if k in sampling:
                std[k] = sampling[k]
        for k in EXTRA_BODY_SAMPLING_ARGS:
            if k in sampling:
                extra[k] = sampling[k]
        extra.update(m.request_params)
        if sampling:
            key["sampling"] = sampling
        if m.request_params:
            key["request_params"] = m.request_params

    key = {"temperature": std["temperature"], "max_tokens": max_tokens, "n": n, **key}
    if seed is not None:
        std["seed"] = key["seed"] = seed
    if cache_salt is not None:
        key["cache_salt"] = cache_salt
    return ResolvedRequest(profiled=profiled, std=std, extra=extra, key_params=key)


@dataclass
class CompletionResult:
    """Completions plus everything known about how they were obtained."""

    choices: list[str]
    finish_reasons: list[str]
    records: list[dict]
    meta: dict = field(default_factory=dict)


class TransportFailure(RuntimeError):
    """No model output after every transport retry (profiled requests only).

    Carries the per-attempt record so a caller can log it as a transport
    failure -- never as a model outcome.
    """

    def __init__(self, message: str, attempts: list[dict]) -> None:
        super().__init__(message)
        self.attempts = attempts


class _ChoiceCountError(RuntimeError):
    pass


class _TokenBucket:
    """Enforces a minimum interval between dispatched requests.

    With requests_per_minute=20 this gives one slot every 3 seconds.
    The lock ensures that concurrent coroutines queue up rather than
    all sleeping the same interval and bursting together.
    """

    def __init__(self, rate_per_minute: float) -> None:
        self._interval = 60.0 / max(rate_per_minute, 0.1)
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            loop = asyncio.get_event_loop()
            now = loop.time()
            wait = max(0.0, self._interval - (now - self._last))
            if wait:
                await asyncio.sleep(wait)
            self._last = loop.time()


class InnkubeClient:
    """OpenAI-compatible async client for the Innkube university LLM endpoint.

    Concurrency model
    -----------------
    - ``_semaphore`` limits the number of in-flight HTTP requests (asyncio-level).
    - ``_rate_limiter`` enforces a sustained throughput cap (token/bucket).
    - Cache lookup happens *before* entering the semaphore, so cached hits are free.
    - Retries use exponential backoff on 429 and 5xx errors only -- for a
      profiled request also on 408/409, timeouts, connection errors and a wrong
      number of choices (see ``_call_with_retry``).
    """

    def __init__(
        self,
        config: LLMConfig,
        cache: ResponseCache,
        mock: bool = False,
    ) -> None:
        self._config = config
        self._cache = cache
        self._mock = mock
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self._rate_limiter = _TokenBucket(config.requests_per_minute)
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = os.environ.get("INNKUBE_API_KEY", "")
            base_url = os.environ.get("INNKUBE_BASE_URL", "").rstrip("/") + "/v1"
            self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        return self._client

    async def complete(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        n: int = 1,
        cache_salt: Optional[str] = None,
        use_profile: bool = True,
    ) -> list[str]:
        """Return *n* completion strings.  Returns mock strings if mock=True.

        ``cache_salt`` is folded into the cache key and **not** sent to the API.
        It exists so a caller can deliberately re-sample a request it has already
        made: without it, submitting the identical prompt twice returns the
        identical cached completions, which would make RQ2's ``control_resample``
        arm report a sampling-noise floor of exactly zero, and would make the
        paraphrase generator's retry budget replay its first attempt forever.
        Callers that pass nothing keep their existing keys, so adding this
        parameter invalidates no cache entry.

        ``use_profile=False`` marks an *instrument* call (SBC): the model's
        sampling and request_params are not applied and the request is exactly
        the legacy one.

        Callers that need to tell a *truncated* completion from a genuinely bad
        one should use :meth:`complete_with_meta` instead.
        """
        result = await self._complete(
            model, messages, temperature=temperature, max_tokens=max_tokens,
            n=n, cache_salt=cache_salt, use_profile=use_profile,
        )
        return result.choices

    async def complete_with_meta(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        n: int = 1,
        cache_salt: Optional[str] = None,
        use_profile: bool = True,
    ) -> tuple[list[str], list[str]]:
        """Return ``(completions, finish_reasons)``.

        ``finish_reason == "length"`` means the model ran out of budget
        mid-answer. That is an *infrastructure* outcome, not a wrong answer, and
        the two are indistinguishable once the reason is dropped: a truncated
        completion fails to parse and enters the leaderboard as a real 0. This
        matters most for models that reason inline before answering, where the
        budget is consumed by deliberation and the answer never arrives.

        Entries written before finish reasons were recorded have no
        ``finish_reasons`` key; they report ``"unknown"`` so an old cache stays
        usable and is never mistaken for a run of clean stops.
        """
        result = await self._complete(
            model, messages, temperature=temperature, max_tokens=max_tokens,
            n=n, cache_salt=cache_salt, use_profile=use_profile,
        )
        return result.choices, result.finish_reasons

    async def complete_with_records(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        n: int = 1,
        cache_salt: Optional[str] = None,
        use_profile: bool = True,
    ) -> tuple[list[str], list[dict]]:
        """Return ``(completions, records)``; one provenance record per completion.

        Each record holds ``raw_source``, ``finish_reason``, ``delimiter_found``
        (facts about the raw response) and ``disposition`` (what this client
        decided). Cache entries written before records existed report
        ``unknown`` rather than being reconstructed.
        """
        result = await self._complete(
            model, messages, temperature=temperature, max_tokens=max_tokens,
            n=n, cache_salt=cache_salt, use_profile=use_profile,
        )
        return result.choices, result.records

    async def complete_detailed(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        n: int = 1,
        cache_salt: Optional[str] = None,
        use_profile: bool = True,
        seed: Optional[int] = None,
    ) -> CompletionResult:
        """Completions, finish reasons, records, and the request's telemetry.

        ``meta`` holds the effective request (without the messages), the
        logical prompt hash, the usage block exactly as returned (missing fields
        stay None, per-choice token counts are never derived from it), the
        reasoning-token count only if the API reports it, per-attempt latency
        and status, and per-choice answer / reasoning-field character counts.
        A cache hit returns the meta stored with the original call plus
        ``cache_hit: True``; an entry written before meta existed has none.
        """
        return await self._complete(
            model, messages, temperature=temperature, max_tokens=max_tokens,
            n=n, cache_salt=cache_salt, use_profile=use_profile, seed=seed,
        )

    async def _complete(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
        n: int,
        cache_salt: Optional[str],
        use_profile: bool = True,
        seed: Optional[int] = None,
    ) -> CompletionResult:
        if self._mock:
            stub = f"# mock [{model}]\ndef solution():\n    pass\n"
            record = {"raw_source": "mock", "finish_reason": "stop",
                      "delimiter_found": False, "disposition": DISP_ANSWER}
            return CompletionResult([stub] * n, ["stop"] * n,
                                    [dict(record) for _ in range(n)], {"mock": True})

        req = resolve_request(self._config, model, temperature=temperature,
                              max_tokens=max_tokens, n=n, cache_salt=cache_salt,
                              use_profile=use_profile, seed=seed)
        cache_key = self._cache.key(model, messages, **req.key_params)
        if cached := self._cache.get(cache_key):
            logger.debug("Cache hit %s", cache_key[:12])
            choices = cached["choices"]
            finish_reasons = cached.get("finish_reasons") or ["unknown"] * len(choices)
            records = cached.get("records") or [
                {"raw_source": SOURCE_UNKNOWN, "finish_reason": fr,
                 "delimiter_found": None, "disposition": DISP_UNKNOWN}
                for fr in finish_reasons
            ]
            meta = {**(cached.get("meta") or {}), "cache_hit": True}
            return CompletionResult(choices, finish_reasons, records, meta)

        # Only non-default arguments are passed on, so a test double with the
        # legacy five-argument signature still works for a legacy call.
        extra_kwargs: dict[str, Any] = {}
        if not use_profile:
            extra_kwargs["use_profile"] = False
        if seed is not None:
            extra_kwargs["seed"] = seed
        async with self._semaphore:
            await self._rate_limiter.acquire()
            result = await self._call_with_retry(model, messages, temperature, max_tokens, n,
                                                 **extra_kwargs)

        # _call_with_retry returns (choices, finish_reasons, records, meta); a
        # shorter tuple (older callers / test doubles) simply lacks the rest.
        choices, finish_reasons, *rest = result
        records = rest[0] if rest else None
        meta = dict(rest[1]) if len(rest) > 1 and rest[1] else {}
        meta["logical_prompt_sha256"] = logical_prompt_sha256(messages)
        meta["cache_hit"] = False

        truncated = sum(1 for r in finish_reasons if r == "length")
        if truncated:
            logger.warning(
                "%s: %d/%d completion(s) hit the %d-token cap (finish_reason=length) "
                "— raise max_tokens or the answer is being cut off mid-generation.",
                model, truncated, len(finish_reasons), max_tokens,
            )
        if records:
            unusable = sum(1 for r in records if r["disposition"].startswith("unusable"))
            if unusable:
                logger.warning(
                    "%s: %d/%d completion(s) had text only in the reasoning field "
                    "with no answer boundary — recorded as unusable, not scored as answers.",
                    model, unusable, len(records),
                )

        entry = {"choices": choices, "finish_reasons": finish_reasons}
        if records:
            entry["records"] = records
        entry["meta"] = meta
        self._cache.put(cache_key, entry)
        return CompletionResult(choices, finish_reasons, records or [
            {"raw_source": SOURCE_UNKNOWN, "finish_reason": fr,
             "delimiter_found": None, "disposition": DISP_UNKNOWN}
            for fr in finish_reasons
        ], meta)

    async def _call_with_retry(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        n: int,
        *,
        use_profile: bool = True,
        seed: Optional[int] = None,
    ) -> tuple[list[str], list[str], list[dict], dict]:
        """One logical request, with transport retries.

        Legacy (unprofiled) requests behave exactly as before: the SDK's own
        retries, then backoff on 429 / 5xx, anything else raised at once.

        Profiled requests get strict transport handling: the SDK retries are
        switched off so every attempt is timed and recorded here; 429, 5xx,
        408/409, timeouts, connection errors and a wrong number of choices are
        all retried with the SAME request; and when every attempt
        fails, :class:`TransportFailure` carries the attempt log.
        """
        cfg = self._config
        req = resolve_request(cfg, model, temperature=temperature, max_tokens=max_tokens,
                              n=n, use_profile=use_profile, seed=seed)
        client = self._get_client()
        options: dict[str, Any] = {}
        if req.profiled:
            options["max_retries"] = 0
        if cfg.request_timeout_s is not None:
            options["timeout"] = cfg.request_timeout_s
        with_options = getattr(client, "with_options", None)
        if options and callable(with_options):
            client = with_options(**options)
        kwargs: dict[str, Any] = {"model": model, "messages": messages, **req.std}
        # Sent as top-level body fields; omitted entirely when empty so an
        # unconfigured model's request is unchanged.
        if req.extra:
            kwargs["extra_body"] = dict(req.extra)

        attempts: list[dict] = []
        started = time.monotonic()

        def failed(status: str, t0: float, exc: BaseException) -> None:
            attempts.append({"attempt": len(attempts) + 1, "status": status,
                             "latency_s": round(time.monotonic() - t0, 3),
                             "error": f"{type(exc).__name__}: {str(exc)[:200]}"})

        last_exc: Optional[BaseException] = None
        for attempt in range(cfg.retry_max_attempts):
            final = attempt == cfg.retry_max_attempts - 1
            delay = cfg.retry_base_delay_s * (2 ** attempt)
            t0 = time.monotonic()
            try:
                response = await client.chat.completions.create(**kwargs)
                if req.profiled and len(response.choices) != n:
                    raise _ChoiceCountError(
                        f"asked for n={n}, got {len(response.choices)} choice(s)")
                latency = round(time.monotonic() - t0, 3)
                attempts.append({"attempt": len(attempts) + 1, "status": "ok", "latency_s": latency})
                classified = [
                    _classify_choice(c.message, c.finish_reason) for c in response.choices
                ]
                usage = _usage_dict(getattr(response, "usage", None))
                meta = {
                    "effective_request": {"model": model, **req.std,
                                          "extra_body": dict(req.extra) or None},
                    "strict_transport": req.profiled,
                    "served_model": getattr(response, "model", None),
                    "usage": usage,
                    "reasoning_tokens": _reasoning_tokens(usage),
                    "choices": [
                        {"answer_chars": len(text),
                         "reasoning_field_chars": _reasoning_field_chars(c.message),
                         **({"reasoning_tail": _length_tail(c.message)}
                            if c.finish_reason == "length" else {})}
                        for (text, _record), c in zip(classified, response.choices)
                    ],
                    "attempts": attempts,
                    "success_latency_s": latency,
                    "total_latency_s": round(time.monotonic() - started, 3),
                }
                return (
                    [text for text, _record in classified],
                    [(c.finish_reason or "unknown") for c in response.choices],
                    [record for _text, record in classified],
                    meta,
                )

            except RateLimitError as exc:
                failed("http_429", t0, exc)
                last_exc = exc
                logger.warning(
                    "429 rate-limited (attempt %d/%d). Sleeping %.1fs.",
                    attempt + 1, cfg.retry_max_attempts, delay,
                )
                if final:
                    break
                await asyncio.sleep(delay)

            except APIStatusError as exc:
                failed(f"http_{exc.status_code}", t0, exc)
                last_exc = exc
                retryable = exc.status_code >= 500 or (req.profiled and exc.status_code in (408, 409))
                if not retryable:
                    raise
                logger.warning(
                    "Server error %d (attempt %d/%d). Sleeping %.1fs.",
                    exc.status_code, attempt + 1, cfg.retry_max_attempts, delay,
                )
                if final:
                    break
                await asyncio.sleep(delay)

            except (APIConnectionError, _ChoiceCountError) as exc:
                # APITimeoutError is an APIConnectionError. Legacy requests keep
                # their old behaviour: raised at once (after the SDK's retries).
                if not req.profiled:
                    raise
                status = ("timeout" if isinstance(exc, APITimeoutError)
                          else "choice_count" if isinstance(exc, _ChoiceCountError)
                          else "connection_error")
                failed(status, t0, exc)
                last_exc = exc
                logger.warning("%s on %s (attempt %d/%d). Sleeping %.1fs.",
                               status, model, attempt + 1, cfg.retry_max_attempts, delay)
                if final:
                    break
                await asyncio.sleep(delay)

        if last_exc is None:
            raise RuntimeError("retry loop exited without returning")  # unreachable
        if req.profiled:
            raise TransportFailure(
                f"{model}: no response after {len(attempts)} attempt(s); last: "
                f"{type(last_exc).__name__}: {str(last_exc)[:200]}", attempts) from last_exc
        raise last_exc
