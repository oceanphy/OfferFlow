"""Domain models shared across tools and layers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InterviewRound:
    """A single interview topic + its follow-up chain."""

    index: int
    question: str
    answer: str
    is_followup: bool = False  # True if this round continues a prior topic


@dataclass
class KnowledgeBaseEntry:
    """A structured knowledge base entry for a specific interview question."""

    id: str
    topic: str
    keywords: list[str] = field(default_factory=list)
    model_answer: str = ""
    scoring_criteria: str = ""
    common_pitfalls: list[str] = field(default_factory=list)


@dataclass
class ContentDiagnosis:
    """Content dimension diagnosis for a single interview round."""

    completeness_score: float  # 0-10
    accuracy_score: float  # 0-10
    depth_score: float  # 0-10
    highlights: list[str] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)


@dataclass
class Gap:
    """A specific deficiency in an answer."""

    location: str  # which part of the answer
    description: str  # what's missing/wrong
    reference: str = ""  # what the standard answer says
    suggestion: str = ""  # how to improve


@dataclass
class ExpressionDiagnosis:
    """Expression dimension diagnosis for a single interview round."""

    coherence_score: float  # 0-10
    structure_score: float  # 0-10
    precision_score: float  # 0-10
    highlights: list[str] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)


@dataclass
class RoundDiagnosis:
    """Complete diagnosis for a single interview round."""

    round_index: int
    question: str
    answer: str
    content: ContentDiagnosis | None = None
    expression: ExpressionDiagnosis | None = None
    knowledge_gaps: list[Gap] = field(default_factory=list)


@dataclass
class DiagnosisReport:
    """Complete diagnosis report for an entire interview."""

    overall_score: float
    content_breakdown: dict[str, float]
    expression_breakdown: dict[str, float]
    rounds: list[RoundDiagnosis] = field(default_factory=list)
    summary: str = ""
