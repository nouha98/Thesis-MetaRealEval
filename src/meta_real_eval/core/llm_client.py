"""Async Innkube LLM client with rate limiting, retry, and disk caching."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Optional

from openai import AsyncOpenAI, RateLimitError, APIStatusError

from .cache import ResponseCache
from .config import LLMConfig

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
    - Retries use exponential backoff on 429 and 5xx errors only.
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

        Callers that need to tell a *truncated* completion from a genuinely bad
        one should use :meth:`complete_with_meta` instead.
        """
        completions, _finish_reasons = await self.complete_with_meta(
            model, messages, temperature=temperature, max_tokens=max_tokens,
            n=n, cache_salt=cache_salt,
        )
        return completions

    async def complete_with_meta(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        n: int = 1,
        cache_salt: Optional[str] = None,
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
        choices, finish_reasons, _records = await self._complete(
            model, messages, temperature=temperature, max_tokens=max_tokens,
            n=n, cache_salt=cache_salt,
        )
        return choices, finish_reasons

    async def complete_with_records(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        n: int = 1,
        cache_salt: Optional[str] = None,
    ) -> tuple[list[str], list[dict]]:
        """Return ``(completions, records)``; one provenance record per completion.

        Each record holds ``raw_source``, ``finish_reason``, ``delimiter_found``
        (facts about the raw response) and ``disposition`` (what this client
        decided). Cache entries written before records existed report
        ``unknown`` rather than being reconstructed.
        """
        choices, _finish_reasons, records = await self._complete(
            model, messages, temperature=temperature, max_tokens=max_tokens,
            n=n, cache_salt=cache_salt,
        )
        return choices, records

    async def _complete(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
        n: int,
        cache_salt: Optional[str],
    ) -> tuple[list[str], list[str], list[dict]]:
        if self._mock:
            stub = f"# mock [{model}]\ndef solution():\n    pass\n"
            record = {"raw_source": "mock", "finish_reason": "stop",
                      "delimiter_found": False, "disposition": DISP_ANSWER}
            return [stub] * n, ["stop"] * n, [dict(record) for _ in range(n)]

        cache_key = self._cache.key(
            model, messages,
            temperature=temperature, max_tokens=max_tokens, n=n,
            **({} if cache_salt is None else {"cache_salt": cache_salt}),
        )
        if cached := self._cache.get(cache_key):
            logger.debug("Cache hit %s", cache_key[:12])
            choices = cached["choices"]
            finish_reasons = cached.get("finish_reasons") or ["unknown"] * len(choices)
            records = cached.get("records") or [
                {"raw_source": SOURCE_UNKNOWN, "finish_reason": fr,
                 "delimiter_found": None, "disposition": DISP_UNKNOWN}
                for fr in finish_reasons
            ]
            return choices, finish_reasons, records

        async with self._semaphore:
            await self._rate_limiter.acquire()
            result = await self._call_with_retry(model, messages, temperature, max_tokens, n)

        # _call_with_retry returns (choices, finish_reasons, records); a 2-tuple
        # (older callers / test doubles) simply has no records to store.
        choices, finish_reasons, *rest = result
        records = rest[0] if rest else None

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
        self._cache.put(cache_key, entry)
        return choices, finish_reasons, records or [
            {"raw_source": SOURCE_UNKNOWN, "finish_reason": fr,
             "delimiter_found": None, "disposition": DISP_UNKNOWN}
            for fr in finish_reasons
        ]

    async def _call_with_retry(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        n: int,
    ) -> tuple[list[str], list[str], list[dict]]:
        cfg = self._config
        for attempt in range(cfg.retry_max_attempts):
            try:
                response = await self._get_client().chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    n=n,
                )
                classified = [
                    _classify_choice(c.message, c.finish_reason) for c in response.choices
                ]
                return (
                    [text for text, _record in classified],
                    [(c.finish_reason or "unknown") for c in response.choices],
                    [record for _text, record in classified],
                )

            except RateLimitError:
                delay = cfg.retry_base_delay_s * (2 ** attempt)
                logger.warning(
                    "429 rate-limited (attempt %d/%d). Sleeping %.1fs.",
                    attempt + 1, cfg.retry_max_attempts, delay,
                )
                if attempt == cfg.retry_max_attempts - 1:
                    raise
                await asyncio.sleep(delay)

            except APIStatusError as exc:
                if exc.status_code >= 500:
                    delay = cfg.retry_base_delay_s * (2 ** attempt)
                    logger.warning(
                        "Server error %d (attempt %d/%d). Sleeping %.1fs.",
                        exc.status_code, attempt + 1, cfg.retry_max_attempts, delay,
                    )
                    if attempt == cfg.retry_max_attempts - 1:
                        raise
                    await asyncio.sleep(delay)
                else:
                    raise

        raise RuntimeError("retry loop exited without returning")  # unreachable
