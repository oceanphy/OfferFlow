"""Sub-agent protocol — every diagnostic sub-agent implements this."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from offerflow.harness.tools.protocol import ToolProtocol


@dataclass
class AgentResult:
    """Structured return from a sub-agent execution."""

    agent_name: str
    success: bool
    data: Any | None = None
    error: str | None = None
    duration_ms: float = 0


class SubAgent(ABC):
    """A sub-agent has a name, a set of accessible tools, and a bounded context."""

    name: str
    description: str
    tools: list[ToolProtocol] = []
    context_boundary: list[str] = []  # labels for what this agent can see

    @abstractmethod
    async def execute(self, task: dict[str, Any]) -> AgentResult:
        ...

    async def run(
        self, task: dict[str, Any], timeout: float = 120.0
    ) -> AgentResult:
        """Execute with timing and optional timeout."""
        import asyncio

        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(self.execute(task), timeout=timeout)
            result.duration_ms = (time.perf_counter() - start) * 1000
            return result
        except asyncio.TimeoutError:
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=f"Timeout after {timeout}s",
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )
