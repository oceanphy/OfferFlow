"""Diagnostic sub-agents for content analysis, expression analysis, knowledge benchmarking, and report generation."""

from __future__ import annotations

from typing import Any

from offerflow.harness.agents.protocol import AgentResult, SubAgent
from offerflow.harness.engine.llm_client import BaseLLMClient
from offerflow.harness.engine.token_budget import ResponseCache
from offerflow.harness.tools.analyze_content import AnalyzeContentTool
from offerflow.harness.tools.analyze_expression import AnalyzeExpressionTool
from offerflow.harness.tools.generate_report import GenerateReportTool
from offerflow.harness.tools.query_knowledge_base import QueryKnowledgeBaseTool


class ContentDiagnosisAgent(SubAgent):
    name = "content_diagnosis"
    description = "评估回答的内容完整性、准确性、深度"
    context_boundary = ["question", "answer", "knowledge_base_entry"]

    def __init__(
        self,
        llm: BaseLLMClient | None = None,
        cache: ResponseCache | None = None,
        kb_tool: QueryKnowledgeBaseTool | None = None,
    ):
        self._analyze = AnalyzeContentTool(llm=llm, cache=cache)
        self._kb = kb_tool or QueryKnowledgeBaseTool()
        self.tools = [self._analyze, self._kb]

    async def execute(self, task: dict[str, Any]) -> AgentResult:
        question = task.get("question", "")
        answer = task.get("answer", "")
        if not question or not answer:
            return AgentResult(agent_name=self.name, success=False, error="Missing question or answer")

        # query knowledge base
        kb_result = await self._kb.execute(question=question)
        evidence = {"knowledge_base_entries": kb_result.data} if kb_result.success else {}

        # analyze content
        result = await self._analyze.execute(
            question=question, answer=answer, evidence=evidence
        )
        return AgentResult(
            agent_name=self.name,
            success=result.success,
            data=result.data,
            error=result.error_message,
        )


class ExpressionDiagnosisAgent(SubAgent):
    name = "expression_diagnosis"
    description = "评估回答的逻辑结构、措辞、条理"
    context_boundary = ["question", "answer"]

    def __init__(self, llm: BaseLLMClient | None = None, cache: ResponseCache | None = None):
        self._analyze = AnalyzeExpressionTool(llm=llm, cache=cache)
        self.tools = [self._analyze]

    async def execute(self, task: dict[str, Any]) -> AgentResult:
        question = task.get("question", "")
        answer = task.get("answer", "")
        if not question or not answer:
            return AgentResult(agent_name=self.name, success=False, error="Missing question or answer")

        result = await self._analyze.execute(question=question, answer=answer)
        return AgentResult(
            agent_name=self.name,
            success=result.success,
            data=result.data,
            error=result.error_message,
        )


class KnowledgeBenchmarkingAgent(SubAgent):
    name = "knowledge_benchmarking"
    description = "对比知识库参考答案，输出差距分析"
    context_boundary = ["question", "knowledge_base_entry"]

    def __init__(self, kb_tool: QueryKnowledgeBaseTool | None = None):
        self._kb = kb_tool or QueryKnowledgeBaseTool()
        self.tools = [self._kb]

    async def execute(self, task: dict[str, Any]) -> AgentResult:
        question = task.get("question", "")
        answer = task.get("answer", "")
        if not question:
            return AgentResult(agent_name=self.name, success=False, error="Missing question")

        result = await self._kb.execute(question=question)
        entries = result.data.get("entries", []) if result.success else []

        # check if answer covers key points from matched entries
        gaps: list[dict[str, str]] = []
        for entry in entries:
            if not entry.get("model_answer"):
                continue
            key_points = [
                s.strip()
                for s in entry["model_answer"].split("。")
                if len(s.strip()) > 10
            ]
            for point in key_points:
                keywords = self._extract_keywords(point)
                if keywords and not any(
                    kw.lower() in answer.lower() for kw in keywords
                ):
                    gaps.append({
                        "topic": entry.get("topic", ""),
                        "missing_point": point[:120],
                        "reference": entry.get("model_answer", "")[:200],
                    })

        return AgentResult(
            agent_name=self.name,
            success=True,
            data={
                "matched_entries": len(entries),
                "total_gaps": len(gaps),
                "gaps": gaps,
            },
        )

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        import re

        words = re.findall(r"[一-鿿]{2,}|\w{3,}", text)
        stop = {"这个", "那个", "一个", "这种", "那种", "什么", "怎么", "为什么", "可以", "能够"}
        return [w for w in words if w not in stop]


class ReportGenerationAgent(SubAgent):
    name = "report_generation"
    description = "汇总所有诊断结果，生成最终报告"
    context_boundary = ["diagnosis_summaries"]

    def __init__(self):
        self._report = GenerateReportTool()
        self.tools = [self._report]

    async def execute(self, task: dict[str, Any]) -> AgentResult:
        rounds = task.get("rounds", [])
        if not rounds:
            return AgentResult(agent_name=self.name, success=False, error="No round data")

        result = await self._report.execute(rounds=rounds)
        return AgentResult(
            agent_name=self.name,
            success=result.success,
            data=result.data,
            error=result.error_message,
        )
