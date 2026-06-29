"""Analyze interview answer content: completeness, accuracy, depth."""

from __future__ import annotations

import time
from typing import Any

from offerflow.harness.models import ContentDiagnosis, Gap, KnowledgeBaseEntry
from offerflow.harness.tools.protocol import ToolProtocol, ToolResult


class AnalyzeContentTool(ToolProtocol):
    name = "analyze_content"
    description = "诊断面试回答的内容质量（完整性、准确性、深度）"
    parameters = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "面试问题"},
            "answer": {"type": "string", "description": "候选人回答"},
            "evidence": {
                "type": "object",
                "description": "证据源数据，如知识库条目",
            },
        },
        "required": ["question", "answer"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        question = kwargs.get("question", "")
        answer = kwargs.get("answer", "")
        evidence = kwargs.get("evidence") or {}

        if not question or not answer:
            return self.make_result(
                success=False,
                error_type="input_error",
                error_message="question and answer are required",
                duration_ms=0,
            )

        try:
            diagnosis = self._analyze(question, answer, evidence)
            return self.make_result(
                success=True,
                data=diagnosis.__dict__,
                duration_ms=(time.perf_counter() - start) * 1000,
                params={"question_length": len(question), "answer_length": len(answer)},
            )
        except Exception as e:
            return self.make_result(
                success=False,
                error_type="service_error",
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def _analyze(
        self, question: str, answer: str, evidence: dict[str, Any]
    ) -> ContentDiagnosis:
        highlights: list[str] = []
        gaps: list[Gap] = []
        kb_entry = evidence.get("knowledge_base_entry")

        # --- completeness check ---
        completeness = 5.0
        if kb_entry:
            completeness = self._check_completeness(
                answer, kb_entry, highlights, gaps
            )

        # --- accuracy check ---
        accuracy = self._estimate_accuracy(answer)

        # --- depth check ---
        depth = self._estimate_depth(answer, highlights)

        # clamp scores
        completeness = max(0, min(10, completeness))
        accuracy = max(0, min(10, accuracy))
        depth = max(0, min(10, depth))

        return ContentDiagnosis(
            completeness_score=round(completeness, 1),
            accuracy_score=round(accuracy, 1),
            depth_score=round(depth, 1),
            highlights=highlights,
            gaps=gaps,
        )

    def _check_completeness(
        self,
        answer: str,
        kb_entry: KnowledgeBaseEntry,
        highlights: list[str],
        gaps: list[Gap],
    ) -> float:
        """Check how many key points from the model answer are covered."""
        model_answer = kb_entry.model_answer
        if not model_answer:
            return 5.0

        # split model answer into key points by sentences
        key_points = [s.strip() for s in model_answer.split("。") if len(s.strip()) > 10]

        covered = 0
        for point in key_points:
            # simple keyword overlap check
            keywords = self._extract_keywords(point)
            if keywords and any(kw.lower() in answer.lower() for kw in keywords):
                covered += 1
            else:
                gaps.append(
                    Gap(
                        location="整体回答",
                        description=f"缺少关键点：{point[:80]}...",
                        reference=point,
                        suggestion=f"补充回答：{point}",
                    )
                )

        if key_points:
            score = (covered / len(key_points)) * 10
            return max(2, score)

        return 5.0

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Extract meaningful keywords from text."""
        import re

        # Chinese: 2+ chars; English: 3+ chars
        words = re.findall(r"[一-鿿]{2,}|\w{3,}", text)
        # filter stop words
        stop = {"这个", "那个", "一个", "这种", "那种", "什么", "怎么", "为什么", "可以", "能够"}
        return [w for w in words if w not in stop]

    @staticmethod
    def _estimate_accuracy(answer: str) -> float:
        """Estimate accuracy based on signpost words and confidence markers."""
        # words that suggest uncertainty
        uncertain_markers = ["可能", "好像", "大概", "也许", "应该", "不确定", "不太清楚", "记不清"]
        # words that suggest clarity/confidence
        clear_markers = ["具体来说", "核心是", "本质上", "关键点", "总结", "举个例子"]

        uncertainty_count = sum(
            1 for m in uncertain_markers if m in answer
        )
        clarity_count = sum(1 for m in clear_markers if m in answer)

        base = 6.0
        base -= uncertainty_count * 0.8
        base += clarity_count * 0.5
        return max(2, min(10, base))

    @staticmethod
    def _estimate_depth(answer: str, highlights: list[str]) -> float:
        """Estimate depth based on presence of technical details and reasoning."""
        depth_signals = [
            ("原理", "提到了底层原理"),
            ("源码", "提到了源码分析"),
            ("权衡", "提到了工程权衡"),
            ("设计", "提到了设计考量"),
            ("架构", "提到了架构层面"),
            ("区别", "进行了对比分析"),
            ("优化", "提到了优化策略"),
            ("场景", "结合了应用场景"),
        ]

        score = 4.0
        for signal, highlight in depth_signals:
            if signal in answer:
                score += 0.8
                highlights.append(highlight)

        # longer answers tend to have more depth (but cap the bonus)
        if len(answer) > 300:
            score += 1.0
        if len(answer) < 50:
            score -= 1.5

        return max(1, min(10, score))
