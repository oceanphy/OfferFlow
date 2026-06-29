"""LLM client — provider-agnostic adapter for OpenAI-compatible and Anthropic APIs.

Supported providers (set via OFFERFLOW_PROVIDER env var):
    openai    — OpenAI API (gpt-4o-mini, gpt-4o, etc.)
    deepseek  — DeepSeek API (OpenAI-compatible, no extra SDK needed)
    anthropic — Anthropic Claude API (requires pip install anthropic)
"""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMConfig:
    """Unified config from environment variables."""
    api_key: str
    base_url: str
    model: str
    fallback_model: str
    provider: str
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("OFFERFLOW_MODEL", "gpt-4o-mini"),
            fallback_model=os.getenv("OFFERFLOW_FALLBACK_MODEL", ""),
            provider=os.getenv("OFFERFLOW_PROVIDER", "openai"),
        )


class BaseLLMClient(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict[str, str]], **kw: Any) -> str: ...
    @abstractmethod
    async def stream(self, messages: list[dict[str, str]], **kw: Any) -> AsyncGenerator[str, None]: ...
    @property
    @abstractmethod
    def model(self) -> str: ...
    @property
    @abstractmethod
    def stats(self) -> dict[str, Any]: ...


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI SDK client — works with OpenAI, DeepSeek, and any compatible endpoint."""

    def __init__(self, config: LLMConfig) -> None:
        from openai import AsyncOpenAI

        self._config = config
        self._client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
        self._total_calls = 0
        self._total_tokens = 0

    @property
    def model(self) -> str:
        return self._config.model

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_calls": self._total_calls,
            "total_tokens": self._total_tokens,
            "model": self._config.model,
            "provider": self._config.provider,
        }

    async def complete(self, messages: list[dict[str, str]], **kw: Any) -> str:
        self._total_calls += 1
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries):
            try:
                return await self._call(self._config.model, messages, **kw)
            except Exception as e:
                last_error = e
                await asyncio.sleep(2 ** attempt)

        # fallback model
        if self._config.fallback_model and self._config.fallback_model != self._config.model:
            try:
                return await self._call(self._config.fallback_model, messages, **kw)
            except Exception as e:
                last_error = e

        raise last_error or RuntimeError("LLM call failed")

    async def stream(self, messages: list[dict[str, str]], **kw: Any) -> AsyncGenerator[str, None]:
        self._total_calls += 1
        temperature = kw.get("temperature", 0.7)
        max_tokens = kw.get("max_tokens", 4096)

        for attempt in range(self._config.max_retries):
            try:
                stream = await self._client.chat.completions.create(
                    model=self._config.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except Exception:
                await asyncio.sleep(2 ** attempt)

        # fallback non-streaming
        if self._config.fallback_model:
            text = await self.complete(messages, temperature=temperature, max_tokens=max_tokens)
            yield text
            return

        raise RuntimeError("LLM stream failed")

    async def _call(self, model: str, messages: list[dict[str, str]], **kw: Any) -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=kw.get("temperature", 0.7),
            max_tokens=kw.get("max_tokens", 4096),
            stop=kw.get("stop"),
        )
        content = response.choices[0].message.content or ""
        if response.usage:
            self._total_tokens += response.usage.total_tokens
        return content


class AnthropicClient(BaseLLMClient):
    """Anthropic Messages API client — requires pip install anthropic."""

    def __init__(self, config: LLMConfig) -> None:
        try:
            import anthropic as _  # noqa: F401
        except ImportError:
            raise ImportError(
                "Anthropic provider requires 'anthropic' package. "
                "Install it with: uv add anthropic"
            )

        from anthropic import AsyncAnthropic

        self._config = config
        self._client = AsyncAnthropic(api_key=config.api_key)
        self._total_calls = 0
        self._total_tokens = 0

    @property
    def model(self) -> str:
        return self._config.model

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_calls": self._total_calls,
            "total_tokens": self._total_tokens,
            "model": self._config.model,
            "provider": "anthropic",
        }

    async def complete(self, messages: list[dict[str, str]], **kw: Any) -> str:
        self._total_calls += 1
        system, user_msgs = self._extract_system(messages)
        response = await self._client.messages.create(
            model=self._config.model,
            max_tokens=kw.get("max_tokens", 4096),
            system=system or None,
            messages=user_msgs,
            temperature=kw.get("temperature", 0.7),
        )
        content = response.content
        if content and isinstance(content[0], type):
            return ""
        text = ""
        for block in content:
            if hasattr(block, "text"):
                text += block.text
        if hasattr(response, "usage"):
            self._total_tokens += response.usage.input_tokens + response.usage.output_tokens
        return text

    async def stream(self, messages: list[dict[str, str]], **kw: Any) -> AsyncGenerator[str, None]:
        self._total_calls += 1
        system, user_msgs = self._extract_system(messages)
        async with self._client.messages.stream(
            model=self._config.model,
            max_tokens=kw.get("max_tokens", 4096),
            system=system or None,
            messages=user_msgs,
            temperature=kw.get("temperature", 0.7),
        ) as stream:
            async for text in stream.text_stream:
                yield text

    @staticmethod
    def _extract_system(
        messages: list[dict[str, str]],
    ) -> tuple[str | None, list[dict[str, str]]]:
        """Anthropic separates system prompt from user messages."""
        system_parts: list[str] = []
        user_msgs: list[dict[str, str]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                user_msgs.append({"role": msg["role"], "content": msg["content"]})
        return "\n\n".join(system_parts) if system_parts else None, user_msgs


# --- Factory ---

def create_llm_client(config: LLMConfig | None = None) -> BaseLLMClient | None:
    """Create the appropriate LLM client based on OFFERFLOW_PROVIDER env var.

    Returns None if no API key is configured (heuristic-only mode).
    """
    if config is None:
        config = LLMConfig.from_env()

    if not config.api_key:
        return None

    if config.provider == "anthropic":
        return AnthropicClient(config)
    else:
        # openai, deepseek, or any OpenAI-compatible endpoint
        return OpenAICompatibleClient(config)
