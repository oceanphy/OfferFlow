"""Query the knowledge base for relevant entries."""

from __future__ import annotations

import time
from typing import Any

from offerflow.harness.models import KnowledgeBaseEntry
from offerflow.harness.tools.protocol import ToolProtocol, ToolResult


class QueryKnowledgeBaseTool(ToolProtocol):
    name = "query_knowledge_base"
    description = "从知识库检索与面试问题匹配的知识条目"
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "面试问题文本，用于检索匹配的知识库条目",
            },
            "top_k": {
                "type": "integer",
                "description": "返回最匹配的条目数量，默认 3",
            },
        },
        "required": ["question"],
    }

    def __init__(self, entries: list[KnowledgeBaseEntry] | None = None):
        self._entries: list[KnowledgeBaseEntry] = entries or []

    def add_entry(self, entry: KnowledgeBaseEntry) -> None:
        self._entries.append(entry)

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        question = kwargs.get("question", "")
        top_k = kwargs.get("top_k", 3)

        if not question:
            return self.make_result(
                success=False,
                error_type="input_error",
                error_message="question is required",
                duration_ms=0,
            )

        try:
            matches = self._search(question, top_k)
            return self.make_result(
                success=True,
                data={
                    "entries": [e.__dict__ for e in matches],
                    "total_matches": len(matches),
                },
                duration_ms=(time.perf_counter() - start) * 1000,
                params={"question": question[:100], "top_k": top_k},
            )
        except Exception as e:
            return self.make_result(
                success=False,
                error_type="service_error",
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def _search(self, question: str, top_k: int) -> list[KnowledgeBaseEntry]:
        if not self._entries:
            return []

        scored: list[tuple[float, KnowledgeBaseEntry]] = []
        for entry in self._entries:
            score = self._score(question, entry)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    @staticmethod
    def _score(question: str, entry: KnowledgeBaseEntry) -> float:
        """Simple keyword overlap scoring."""
        q_lower = question.lower()
        score = 0.0

        # topic match
        if entry.topic.lower() in q_lower:
            score += 3.0

        # keyword overlap
        for kw in entry.keywords:
            if kw.lower() in q_lower:
                score += 2.0

            # partial keyword match (for Chinese 2-char subs)
            if len(kw) >= 3:
                for i in range(len(kw) - 1):
                    sub = kw[i : i + 2]
                    if sub in q_lower:
                        score += 1.0
                        break

        return score
