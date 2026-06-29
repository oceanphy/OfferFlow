"""Agent orchestrator — parallel dispatch, timeout control, result aggregation."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from offerflow.harness.agents.protocol import AgentResult, SubAgent

DEFAULT_TIMEOUT = 120.0  # seconds


class AgentOrchestrator:
    """Orchestrates parallel sub-agent dispatch for multi-round diagnosis.

    For each interview round, dispatches content diagnosis + expression diagnosis
    + knowledge benchmarking in parallel. After all rounds are complete, dispatches
    report generation to aggregate results.
    """

    def __init__(self, max_concurrency: int = 10):
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def diagnose_round(
        self,
        agents: list[SubAgent],
        task: dict[str, Any],
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict[str, AgentResult]:
        """Run multiple agents on a single round in parallel."""
        async def run_one(agent: SubAgent) -> tuple[str, AgentResult]:
            async with self._semaphore:
                result = await agent.run(task, timeout=timeout)
                return agent.name, result

        results = await asyncio.gather(
            *(run_one(a) for a in agents), return_exceptions=True
        )

        output: dict[str, AgentResult] = {}
        for item in results:
            if isinstance(item, Exception):
                continue
            name, result = item
            output[name] = result

        return output

    async def diagnose_transcript(
        self,
        rounds: list[dict[str, Any]],
        content_agent: SubAgent,
        expression_agent: SubAgent,
        knowledge_agent: SubAgent,
        report_agent: SubAgent,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """Full transcript diagnosis pipeline.

        1. For each round, dispatch content + expression + knowledge agents in parallel
        2. Collect all round diagnoses
        3. Generate the final report
        """
        start = time.perf_counter()
        round_results: list[dict[str, Any]] = []

        for i, rd in enumerate(rounds):
            task = {
                "round_index": i,
                "question": rd.get("question", ""),
                "answer": rd.get("answer", ""),
            }
            agent_results = await self.diagnose_round(
                [content_agent, expression_agent, knowledge_agent],
                task,
                timeout=timeout,
            )

            round_data = {
                "round_index": i,
                "question": task["question"],
                "answer": task["answer"],
                "content": self._extract_data(agent_results.get("content_diagnosis")),
                "expression": self._extract_data(agent_results.get("expression_diagnosis")),
                "knowledge_gaps": self._extract_data(agent_results.get("knowledge_benchmarking")),
            }
            round_results.append(round_data)

        # generate final report
        report_result = await report_agent.run({"rounds": round_results}, timeout=timeout)
        report_data = self._extract_data(report_result)

        return {
            "rounds": round_results,
            "report": report_data,
            "total_duration_ms": (time.perf_counter() - start) * 1000,
            "agent_summary": self._summarize_results(round_results),
        }

    @staticmethod
    def _extract_data(result: AgentResult | None) -> dict[str, Any] | None:
        if result is None:
            return None
        if result.success and result.data is not None:
            return result.data if isinstance(result.data, dict) else vars(result.data)
        return {"error": result.error}

    @staticmethod
    def _summarize_results(round_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Count successes and failures across all rounds."""
        total_rounds = len(round_results)
        content_ok = sum(1 for r in round_results if r.get("content") and "error" not in str(r["content"]))
        expression_ok = sum(1 for r in round_results if r.get("expression") and "error" not in str(r["expression"]))
        return {
            "total_rounds": total_rounds,
            "content_analyzed": content_ok,
            "expression_analyzed": expression_ok,
        }
