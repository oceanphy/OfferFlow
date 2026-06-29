"""Analyze interview answer content: completeness, accuracy, depth.

Supports both LLM-driven analysis (when LLMClient is available) and heuristic fallback.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from offerflow.harness.engine.llm_client import BaseLLMClient
from offerflow.harness.engine.prompts import CONTENT_DIAGNOSIS_SYSTEM, CONTENT_DIAGNOSIS_USER
from offerflow.harness.engine.token_budget import ResponseCache
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

    def __init__(self, llm: BaseLLMClient | None = None, cache: ResponseCache | None = None):
        self._llm = llm
        self._cache = cache

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
            if self._llm:
                diagnosis = await self._llm_analyze(question, answer, evidence)
            else:
                diagnosis = self._heuristic_analyze(question, answer, evidence)

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

    async def _llm_analyze(
        self, question: str, answer: str, evidence: dict[str, Any]
    ) -> ContentDiagnosis:
        kb_entry = evidence.get("knowledge_base_entry")
        reference_text = ""
        if kb_entry:
            if isinstance(kb_entry, KnowledgeBaseEntry):
                reference_text = kb_entry.model_answer or kb_entry.topic
            elif isinstance(kb_entry, dict):
                reference_text = kb_entry.get("model_answer", "") or kb_entry.get("topic", "")

        user_prompt = CONTENT_DIAGNOSIS_USER.format(
            question=question, answer=answer, reference=reference_text
        )
        messages = [
            {"role": "system", "content": CONTENT_DIAGNOSIS_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]

        # check cache
        if self._cache:
            cached = self._cache.get(messages, self._llm.model)
            if cached:
                return self._parse_llm_json(cached)

        response = await self._llm.complete(messages, temperature=0.3)
        if self._cache:
            self._cache.set(messages, self._llm.model, response)

        return self._parse_llm_json(response)

    @staticmethod
    def _parse_llm_json(response: str) -> ContentDiagnosis:
        # extract JSON from response (may be wrapped in ```json blocks)
        json_match = re.search(r"\{[\s\S]*\}", response.strip())
        if not json_match:
            raise ValueError(f"LLM response contained no JSON: {response[:200]}")

        data = json.loads(json_match.group(0))
        gaps = [
            Gap(
                location=g.get("location", ""),
                description=g.get("description", ""),
                reference=g.get("reference", ""),
                suggestion=g.get("suggestion", ""),
            )
            for g in data.get("gaps", [])
        ]

        return ContentDiagnosis(
            completeness_score=float(data.get("completeness_score", 5)),
            accuracy_score=float(data.get("accuracy_score", 5)),
            depth_score=float(data.get("depth_score", 5)),
            highlights=data.get("highlights", []),
            gaps=gaps,
        )

    def _heuristic_analyze(
        self, question: str, answer: str, evidence: dict[str, Any]
    ) -> ContentDiagnosis:
        highlights: list[str] = []
        gaps: list[Gap] = []
        kb_entry = evidence.get("knowledge_base_entry")

        completeness = 5.0
        if kb_entry and isinstance(kb_entry, KnowledgeBaseEntry):
            completeness = self._check_completeness(answer, kb_entry, highlights, gaps)

        accuracy = self._estimate_accuracy(answer)
        depth = self._estimate_depth(answer, highlights)

        return ContentDiagnosis(
            completeness_score=round(max(0, min(10, completeness)), 1),
            accuracy_score=round(max(0, min(10, accuracy)), 1),
            depth_score=round(max(0, min(10, depth)), 1),
            highlights=highlights,
            gaps=gaps,
        )

    def _check_completeness(
        self, answer: str, kb_entry: KnowledgeBaseEntry,
        highlights: list[str], gaps: list[Gap],
    ) -> float:
        model_answer = kb_entry.model_answer
        if not model_answer:
            return 5.0

        key_points = [s.strip() for s in model_answer.split("。") if len(s.strip()) > 10]
        covered = 0
        for point in key_points:
            keywords = self._extract_keywords(point)
            if keywords and any(kw.lower() in answer.lower() for kw in keywords):
                covered += 1
            else:
                gaps.append(Gap(
                    location="整体回答",
                    description=f"缺少关键点：{point[:80]}...",
                    reference=point,
                    suggestion=f"补充回答：{point}",
                ))

        return max(2, (covered / len(key_points)) * 10) if key_points else 5.0

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        words = re.findall(r"[一-鿿]{2,}|\w{3,}", text)
        stop = {"这个", "那个", "一个", "这种", "那种", "什么", "怎么", "为什么", "可以", "能够"}
        return [w for w in words if w not in stop]

    @staticmethod
    def _estimate_accuracy(answer: str) -> float:
        uncertain = ["可能", "好像", "大概", "也许", "应该", "不确定", "不太清楚", "记不清"]
        clear = ["具体来说", "核心是", "本质上", "关键点", "总结", "举个例子"]
        base = 6.0
        base -= sum(1 for m in uncertain if m in answer) * 0.8
        base += sum(1 for m in clear if m in answer) * 0.5
        return max(2, min(10, base))

    @staticmethod
    def _estimate_depth(answer: str, highlights: list[str]) -> float:
        depth_signals = [
            ("原理", "提到了底层原理"), ("源码", "提到了源码分析"),
            ("权衡", "提到了工程权衡"), ("设计", "提到了设计考量"),
            ("架构", "提到了架构层面"), ("区别", "进行了对比分析"),
            ("优化", "提到了优化策略"), ("场景", "结合了应用场景"),
        ]
        score = 4.0
        for signal, highlight in depth_signals:
            if signal in answer:
                score += 0.8
                highlights.append(highlight)
        if len(answer) > 300:
            score += 1.0
        if len(answer) < 50:
            score -= 1.5
        return max(1, min(10, score))
