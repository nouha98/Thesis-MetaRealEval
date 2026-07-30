"""Async Innkube LLM client with rate limiting, retry, and disk caching."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from openai import AsyncOpenAI, RateLimitError, APIStatusError

from .cache import ResponseCache
from .config import LLMConfig

logger = logging.getLogger(__name__)


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
    ) -> list[str]:
        """Return *n* completion strings.  Returns mock strings if mock=True."""
        if self._mock:
            stub = f"# mock [{model}]\ndef solution():\n    pass\n"
            return [stub] * n

        cache_key = self._cache.key(
            model, messages,
            temperature=temperature, max_tokens=max_tokens, n=n,
        )
        if cached := self._cache.get(cache_key):
            logger.debug("Cache hit %s", cache_key[:12])
            return cached["choices"]

        async with self._semaphore:
            await self._rate_limiter.acquire()
            choices = await self._call_with_retry(model, messages, temperature, max_tokens, n)

        self._cache.put(cache_key, {"choices": choices})
        return choices

    async def _call_with_retry(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        n: int,
    ) -> list[str]:
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
                return [c.message.content or "" for c in response.choices]

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
