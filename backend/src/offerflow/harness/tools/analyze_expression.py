"""Analyze interview answer expression quality: coherence, structure, precision."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict
from typing import Any

from offerflow.harness.engine.llm_client import BaseLLMClient
from offerflow.harness.engine.prompts import (
    EXPRESSION_DIAGNOSIS_SYSTEM,
    EXPRESSION_DIAGNOSIS_USER,
)
from offerflow.harness.engine.token_budget import ResponseCache
from offerflow.harness.models import ExpressionDiagnosis, Gap
from offerflow.harness.tools.protocol import ToolProtocol, ToolResult


class AnalyzeExpressionTool(ToolProtocol):
    name = "analyze_expression"
    description = "诊断面试回答的表达质量（逻辑连贯性、结构性、措辞精准度）"
    parameters = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "面试问题"},
            "answer": {"type": "string", "description": "候选人回答"},
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

        if not question or not answer:
            return self.make_result(
                success=False,
                error_type="input_error",
                error_message="question and answer are required",
                duration_ms=0,
            )

        try:
            if self._llm:
                diagnosis = await self._llm_analyze(question, answer)
            else:
                diagnosis = self._heuristic_analyze(answer)

            return self.make_result(
                success=True,
                data=asdict(diagnosis),
                duration_ms=(time.perf_counter() - start) * 1000,
                params={"answer_length": len(answer)},
            )
        except Exception as e:
            return self.make_result(
                success=False,
                error_type="service_error",
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    async def _llm_analyze(self, question: str, answer: str) -> ExpressionDiagnosis:
        user_prompt = EXPRESSION_DIAGNOSIS_USER.format(question=question, answer=answer)
        messages = [
            {"role": "system", "content": EXPRESSION_DIAGNOSIS_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]

        if self._cache:
            cached = self._cache.get(messages, self._llm.model)
            if cached:
                return self._parse_llm_json(cached)

        response = await self._llm.complete(messages, temperature=0.3)
        if self._cache:
            self._cache.set(messages, self._llm.model, response)

        return self._parse_llm_json(response)

    @staticmethod
    def _parse_llm_json(response: str) -> ExpressionDiagnosis:
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

        return ExpressionDiagnosis(
            coherence_score=float(data.get("coherence_score", 5)),
            structure_score=float(data.get("structure_score", 5)),
            precision_score=float(data.get("precision_score", 5)),
            highlights=data.get("highlights", []),
            gaps=gaps,
        )

    def _heuristic_analyze(self, answer: str) -> ExpressionDiagnosis:
        highlights: list[str] = []
        gaps: list[Gap] = []

        coherence = self._estimate_coherence(answer, highlights, gaps)
        structure = self._estimate_structure(answer, highlights, gaps)
        precision = self._estimate_precision(answer, highlights, gaps)

        return ExpressionDiagnosis(
            coherence_score=round(coherence, 1),
            structure_score=round(structure, 1),
            precision_score=round(precision, 1),
            highlights=highlights,
            gaps=gaps,
        )

    @staticmethod
    def _estimate_coherence(
        answer: str, highlights: list[str], gaps: list[Gap]
    ) -> float:
        score = 5.0
        # transition words suggest coherence
        transitions = ["首先", "其次", "另外", "因为", "所以", "因此", "总结", "一方面", "另一方面", "同时"]
        count = sum(1 for t in transitions if t in answer)
        if count >= 3:
            score += 2
            highlights.append("使用了连接词，逻辑层次较清晰")
        elif count == 0:
            score -= 1.5
            gaps.append(Gap(
                location="全文",
                description="缺少逻辑连接词，段落之间跳跃感强",
                suggestion="使用'首先-其次-最后'或'因为-所以'等连接词增强连贯性",
            ))

        # filler words penalty
        fillers = ["呃", "嗯", "那个", "然后", "就是说", "怎么说呢"]
        filler_count = sum(answer.count(f) for f in fillers)
        if filler_count > 5:
            score -= 2
            gaps.append(Gap(
                location="全文",
                description=f"语气词过多（{filler_count}处），影响流畅度",
                suggestion="放慢语速，用短暂停顿替代语气词",
            ))

        return max(1, min(10, score))

    @staticmethod
    def _estimate_structure(
        answer: str, highlights: list[str], gaps: list[Gap]
    ) -> float:
        score = 5.0

        # check for structured opening
        structured_openings = ["总共", "分为", "有几点", "从几个方面", "关于这个问题"]
        if any(o in answer[:30] for o in structured_openings):
            score += 1.5
            highlights.append("开头有结构化意识")

        # check for numbered points
        if re.search(r"(第[一二三四五]|[1-5][.\)、])", answer):
            score += 1.5
            highlights.append("使用了分点论述")

        # check for summary/closing
        if any(w in answer[-50:] for w in ["总之", "总结", "概括", "所以"]):
            score += 1
            highlights.append("有总结收尾")

        # too short
        if len(answer) < 60:
            score -= 2
            gaps.append(Gap(
                location="全文", description="回答过短，缺乏展开结构",
                suggestion="采用总分总结构：先概括观点，再展开细节，最后总结",
            ))

        return max(1, min(10, score))

    @staticmethod
    def _estimate_precision(
        answer: str, highlights: list[str], gaps: list[Gap]
    ) -> float:
        score = 5.0

        # vague language penalty
        vague = ["可能", "大概", "好像", "应该", "不太清楚", "差不多", "之类", "等等"]
        vague_count = sum(answer.count(v) for v in vague)
        if vague_count > 3:
            score -= 2
            gaps.append(Gap(
                location="全文",
                description="模糊用词过多，术语不够精准",
                suggestion="用精确术语替代模糊表达。不确定时诚实说'我不确定'比用模糊词更好",
            ))

        # precise terms bonus (technical terms)
        if re.findall(r"[A-Z][a-z]+(?:[A-Z][a-z]+)*", answer):
            score += 1
            highlights.append("使用了英文技术术语")

        return max(1, min(10, score))
