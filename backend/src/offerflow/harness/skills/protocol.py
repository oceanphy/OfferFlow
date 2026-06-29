"""L2: Skill protocol — task-level orchestration of tools and sub-agents."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillStatus(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SkillResult:
    skill_name: str
    status: SkillStatus
    data: Any | None = None
    error: str | None = None
    duration_ms: float = 0
    steps_completed: int = 0
    steps_total: int = 0


class SkillProtocol(ABC):
    """A Skill is a meaningful composition of tools and sub-agents.

    It represents a complete workflow (e.g., diagnose_transcript),
    with defined steps and lifecycle tracking.
    """

    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs: Any) -> SkillResult:
        ...

    @staticmethod
    def make_result(
        name: str,
        status: SkillStatus,
        **overrides: Any,
    ) -> SkillResult:
        return SkillResult(skill_name=name, status=status, **overrides)
