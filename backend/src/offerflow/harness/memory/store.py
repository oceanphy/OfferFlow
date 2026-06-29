"""L5: Memory — user profiles, diagnosis history, session context.

Following the "restrained writing" principle: only stable conclusions,
no intermediate reasoning. Only profile changes, not every conversation detail.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class UserProfile:
    """Long-term: user goal role, tech stack, recurring weaknesses, improvement trend."""

    target_role: str = ""
    tech_stack: list[str] = field(default_factory=list)
    common_weaknesses: list[str] = field(default_factory=list)  # recurring weak dimensions
    total_diagnoses: int = 0
    improvement_trend: str = ""  # "improving" / "stable" / "declining"
    last_active: str = ""

    @staticmethod
    def load(path: str = "data/user_profile.json") -> "UserProfile":
        if not os.path.exists(path):
            return UserProfile()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return UserProfile(**data)

    def save(self, path: str = "data/user_profile.json") -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.last_active = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)

    def update_from_diagnosis(self, report: dict[str, Any]) -> None:
        self.total_diagnoses += 1
        # track recurring weak dimensions from report summary
        weak_dims: list[str] = []
        for rd in report.get("rounds", []):
            content = rd.get("content", {})
            if content:
                scores = [
                    content.get("completeness_score", 5),
                    content.get("accuracy_score", 5),
                    content.get("depth_score", 5),
                ]
                if sum(scores) / 3 < 5.0:
                    weak_dims.append("content")
            expression = rd.get("expression", {})
            if expression:
                scores = [
                    expression.get("coherence_score", 5),
                    expression.get("structure_score", 5),
                    expression.get("precision_score", 5),
                ]
                if sum(scores) / 3 < 5.0:
                    weak_dims.append("expression")

        if weak_dims:
            self.common_weaknesses = list(set(self.common_weaknesses + weak_dims))[:5]


@dataclass
class DiagnosisHistory:
    """Medium-term: structured summaries, high-frequency weak dimension stats."""

    sessions: list[dict[str, Any]] = field(default_factory=list)
    dimension_stats: dict[str, float] = field(default_factory=dict)

    @staticmethod
    def load(path: str = "data/diagnosis_history.json") -> "DiagnosisHistory":
        if not os.path.exists(path):
            return DiagnosisHistory()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return DiagnosisHistory(
            sessions=data.get("sessions", []),
            dimension_stats=data.get("dimension_stats", {}),
        )

    def save(self, path: str = "data/diagnosis_history.json") -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)

    def add_session(self, report_id: str, summary: dict[str, Any]) -> None:
        self.sessions.append({
            "report_id": report_id,
            "timestamp": datetime.now().isoformat(),
            "rounds": summary.get("total_rounds", 0),
            "gaps": summary.get("total_gaps", 0),
        })
        # keep last 50 sessions
        if len(self.sessions) > 50:
            self.sessions = self.sessions[-50:]


@dataclass
class SessionContext:
    """Short-term: current diagnosis work state, processed/pending queues."""

    session_id: str
    transcript: str = ""
    status: str = "pending"  # pending / splitting / diagnosing / complete / failed
    rounds: list[dict[str, Any]] = field(default_factory=list)
    completed_count: int = 0
    total_count: int = 0
    report_id: str = ""

    @staticmethod
    def load(session_id: str, path: str = "data/sessions") -> "SessionContext | None":
        filepath = os.path.join(path, f"{session_id}.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        return SessionContext(**data)

    def save(self, path: str = "data/sessions") -> None:
        os.makedirs(path, exist_ok=True)
        filepath = os.path.join(path, f"{self.session_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)

    def delete(self, path: str = "data/sessions") -> None:
        filepath = os.path.join(path, f"{self.session_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
