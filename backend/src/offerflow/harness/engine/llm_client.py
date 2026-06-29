"""LLM client — OpenAI-compatible API with streaming, retry, and fallback."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI


class LLMClient:
    """Wraps OpenAI-compatible API with streaming, retry, and model fallback.

    Configuration via environment variables:
        OPENAI_API_KEY  — API key (required)
        OPENAI_BASE_URL — custom endpoint (optional)
        OFFERFLOW_MODEL — primary model (default: gpt-4o-mini)
        OFFERFLOW_FALLBACK_MODEL — fallback model (default: gpt-3.5-turbo)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        fallback_model: str | None = None,
        max_retries: int = 3,
    ) -> None:
        api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.model = model or os.getenv("OFFERFLOW_MODEL", "gpt-4o-mini")
        self.fallback_model = fallback_model or os.getenv(
            "OFFERFLOW_FALLBACK_MODEL", "gpt-3.5-turbo"
        )
        self.max_retries = max_retries
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._total_calls = 0
        self._total_tokens = 0

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stop: list[str] | None = None,
    ) -> str:
        """Non-streaming completion with retry and fallback."""
        self._total_calls += 1
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                return await self._try_complete(
                    self.model,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop=stop,
                )
            except Exception as e:
                last_error = e
                wait = 2**attempt
                await asyncio.sleep(wait)

        # try fallback model
        if self.fallback_model and self.fallback_model != self.model:
            try:
                return await self._try_complete(
                    self.fallback_model,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop=stop,
                )
            except Exception as e:
                last_error = e

        raise last_error or RuntimeError("LLM call failed")

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Streaming completion yielding text chunks."""
        self._total_calls += 1
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                stream = await self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except Exception as e:
                last_error = e
                wait = 2**attempt
                await asyncio.sleep(wait)

        # fallback: non-streaming with fallback model
        if self.fallback_model:
            text = await self.complete(
                messages, temperature=temperature, max_tokens=max_tokens
            )
            yield text
            return

        raise last_error or RuntimeError("LLM stream failed")

    async def _try_complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        stop: list[str] | None,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        )
        content = response.choices[0].message.content or ""
        if response.usage:
            self._total_tokens += response.usage.total_tokens
        return content

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_calls": self._total_calls,
            "total_tokens": self._total_tokens,
            "model": self.model,
            "fallback_model": self.fallback_model,
        }
