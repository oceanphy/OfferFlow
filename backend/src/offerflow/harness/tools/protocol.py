"""Tool protocol — every tool in OfferFlow implements this interface."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ToolResult:
    """Structured return from any tool execution."""

    success: bool
    data: Any | None = None
    error_type: Literal["input_error", "service_error", "timeout"] | None = None
    error_message: str | None = None
    duration_ms: float = 0
    tool_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def to_audit_entry(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "success": self.success,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }


class ToolProtocol(ABC):
    """Every tool must have a name, description, JSON Schema params, and execute()."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for the tool's input

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        ...

    def make_result(self, success: bool, **overrides: Any) -> ToolResult:
        return ToolResult(
            success=success,
            tool_name=self.name,
            **overrides,
        )
