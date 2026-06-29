"""Token budget tracker and response cache."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any


class TokenBudget:
    """Tracks token usage against a per-session limit."""

    def __init__(self, max_tokens: int = 32_000) -> None:
        self.max_tokens = max_tokens
        self._used = 0

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self._used)

    def consume(self, tokens: int) -> bool:
        """Consume tokens. Returns True if within budget, False if exceeded."""
        if self._used + tokens > self.max_tokens:
            return False
        self._used += tokens
        return True

    def reset(self) -> None:
        self._used = 0

    @staticmethod
    def estimate(text: str) -> int:
        """Rough token estimation: ~2.5 chars per token for mixed Chinese/English."""
        if not text:
            return 0
        return max(1, len(text) // 2)

    @staticmethod
    def estimate_messages(messages: list[dict[str, str]]) -> int:
        total = 0
        for msg in messages:
            total += TokenBudget.estimate(msg.get("content", ""))
        return total


class ResponseCache:
    """In-memory cache for LLM responses, keyed by prompt hash."""

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 1000) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[str, tuple[float, str]] = {}

    def get(self, messages: list[dict[str, str]], model: str) -> str | None:
        key = self._make_key(messages, model)
        entry = self._store.get(key)
        if entry is None:
            return None
        timestamp, value = entry
        if time.monotonic() - timestamp > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, messages: list[dict[str, str]], model: str, value: str) -> None:
        if len(self._store) >= self._max:
            # evict oldest entry
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]

        key = self._make_key(messages, model)
        self._store[key] = (time.monotonic(), value)

    def _make_key(self, messages: list[dict[str, str]], model: str) -> str:
        raw = json.dumps(messages, sort_keys=True, ensure_ascii=False) + model
        return hashlib.sha256(raw.encode()).hexdigest()

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)
