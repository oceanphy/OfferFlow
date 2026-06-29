"""Diagnose transcript skill — the core pipeline."""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, is_dataclass
from typing import Any

from offerflow.harness.agents.diagnosis_agents import (
    ContentDiagnosisAgent,
    ExpressionDiagnosisAgent,
    KnowledgeBenchmarkingAgent,
    ReportGenerationAgent,
)
from offerflow.harness.agents.orchestrator import AgentOrchestrator
from offerflow.harness.engine.llm_client import BaseLLMClient
from offerflow.harness.engine.token_budget import ResponseCache
from offerflow.harness.skills.protocol import SkillProtocol, SkillResult, SkillStatus
from offerflow.harness.tools.split_rounds import SplitRoundsTool


class DiagnoseTranscriptSkill(SkillProtocol):
    name = "diagnose_transcript"
    description = "诊断完整面试文字稿：拆分回合 → 并行诊断 → 生成报告"

    def __init__(
        self,
        llm: BaseLLMClient | None = None,
        cache: ResponseCache | None = None,
    ):
        self._splitter = SplitRoundsTool()
        self._content_agent = ContentDiagnosisAgent(llm=llm, cache=cache)
        self._expression_agent = ExpressionDiagnosisAgent(llm=llm, cache=cache)
        self._knowledge_agent = KnowledgeBenchmarkingAgent()
        self._report_agent = ReportGenerationAgent()
        self._orchestrator = AgentOrchestrator()
        self._on_progress: Any = None

    def on_progress(self, callback: Any) -> None:
        self._on_progress = callback

    async def execute(self, **kwargs: Any) -> SkillResult:
        start = time.perf_counter()
        transcript = kwargs.get("transcript", "")

        if not transcript:
            return self.make_result(self.name, SkillStatus.FAILED, error="transcript is required")

        try:
            await self._emit("splitting", {"message": "正在拆分面试回合..."})

            split_result = await self._splitter.execute(transcript=transcript)
            if not split_result.success:
                return self.make_result(self.name, SkillStatus.FAILED, error=split_result.error_message)

            rounds = split_result.data
            await self._emit("split_complete", {"rounds": len(rounds)})

            total = len(rounds)
            for i, rd in enumerate(rounds):
                await self._emit("diagnosing", {
                    "round": i + 1, "total": total,
                    "question": rd.get("question", "")[:80],
                    "message": f"正在诊断第 {i + 1}/{total} 回合...",
                })

                agent_results = await self._orchestrator.diagnose_round(
                    [self._content_agent, self._expression_agent, self._knowledge_agent],
                    {"round_index": i, "question": rd.get("question", ""), "answer": rd.get("answer", "")},
                )

                rd["content"] = _extract_agent_data(agent_results.get("content_diagnosis"))
                rd["expression"] = _extract_agent_data(agent_results.get("expression_diagnosis"))
                rd["knowledge_gaps"] = _extract_agent_data(agent_results.get("knowledge_benchmarking"))

            await self._emit("generating_report", {"message": "正在生成诊断报告..."})

            report_result = await self._report_agent.execute({"rounds": rounds})
            report_data = _extract_agent_data(report_result) if report_result.success else None

            await self._emit("complete", {"message": "诊断完成"})

            return SkillResult(
                skill_name=self.name, status=SkillStatus.COMPLETED,
                data={"rounds": rounds, "report": report_data},
                duration_ms=(time.perf_counter() - start) * 1000,
                steps_completed=3, steps_total=3,
            )
        except Exception as e:
            return self.make_result(self.name, SkillStatus.FAILED,
                                    error=str(e), duration_ms=(time.perf_counter() - start) * 1000)

    async def _emit(self, event: str, data: dict[str, Any]) -> None:
        if self._on_progress:
            result = self._on_progress(event, data)
            if asyncio.iscoroutine(result):
                await result


def _extract_agent_data(result: Any) -> dict[str, Any] | None:
    """Extract structured data from an AgentResult, handling all edge cases."""
    if result is None:
        return None

    # AgentResult / ToolResult (has .data attr)
    if hasattr(result, "data"):
        data = result.data
        if data is None:
            return {"error": getattr(result, "error", "unknown error"), "success": False}
        if isinstance(data, dict):
            return data
        if is_dataclass(data):
            return asdict(data)
        # fallback: try __dict__
        if hasattr(data, "__dict__"):
            return vars(data)
        return {"raw": str(data)}

    # raw dict
    if isinstance(result, dict):
        return result

    return {"raw": str(result)}
