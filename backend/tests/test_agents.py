"""Tests for L10 Sub-agent layer."""

import pytest
from unittest.mock import AsyncMock

from offerflow.harness.agents import (
    AgentOrchestrator,
    ContentDiagnosisAgent,
    ExpressionDiagnosisAgent,
    KnowledgeBenchmarkingAgent,
    ReportGenerationAgent,
)
from offerflow.harness.models import KnowledgeBaseEntry


class TestContentDiagnosisAgent:
    @pytest.mark.asyncio
    async def test_heuristic_execution(self):
        agent = ContentDiagnosisAgent()
        result = await agent.execute({
            "question": "什么是闭包？",
            "answer": "闭包是函数可以记住外部变量的机制。",
        })

        assert result.success
        assert result.agent_name == "content_diagnosis"
        assert "completeness_score" in result.data

    @pytest.mark.asyncio
    async def test_missing_input(self):
        agent = ContentDiagnosisAgent()
        result = await agent.execute({"question": "", "answer": ""})

        assert not result.success
        assert "Missing" in result.error


class TestExpressionDiagnosisAgent:
    @pytest.mark.asyncio
    async def test_heuristic_execution(self):
        agent = ExpressionDiagnosisAgent()
        result = await agent.execute({
            "question": "Redis怎么用？",
            "answer": "Redis是一个内存数据库。",
        })

        assert result.success
        assert "coherence_score" in result.data


class TestKnowledgeBenchmarkingAgent:
    @pytest.mark.asyncio
    async def test_finds_gaps(self):
        kb_tool_mock = AsyncMock()
        kb_tool_mock.execute.return_value.success = True
        kb_tool_mock.execute.return_value.data = {
            "entries": [
                {
                    "id": "kb-1",
                    "topic": "缓存穿透",
                    "keywords": ["Redis", "缓存穿透", "布隆过滤器"],
                    "model_answer": "缓存穿透的解决方案包括布隆过滤器和缓存空值。布隆过滤器使用多个哈希函数判断key是否存在。缓存空值将不存在的key缓存并设置较短过期时间。",
                    "scoring_criteria": "",
                    "common_pitfalls": [],
                }
            ]
        }

        agent = KnowledgeBenchmarkingAgent(kb_tool=kb_tool_mock)
        result = await agent.execute({
            "question": "Redis缓存穿透怎么处理？",
            "answer": "布隆过滤器就行。",
        })

        assert result.success
        assert result.data["total_gaps"] > 0
        assert any("缓存空值" in str(g) for g in result.data["gaps"])


class TestReportGenerationAgent:
    @pytest.mark.asyncio
    async def test_generates_report(self):
        agent = ReportGenerationAgent()
        rounds = [
            {
                "round_index": 0,
                "question": "Q1",
                "answer": "A1",
                "content": {
                    "completeness_score": 6.0,
                    "accuracy_score": 6.0,
                    "depth_score": 6.0,
                    "highlights": ["test"],
                    "gaps": [],
                },
            }
        ]
        result = await agent.execute({"rounds": rounds})

        assert result.success
        assert "markdown" in result.data


class TestAgentOrchestrator:
    @pytest.mark.asyncio
    async def test_diagnose_round_parallel(self):
        orch = AgentOrchestrator()
        content = ContentDiagnosisAgent()
        expression = ExpressionDiagnosisAgent()

        task = {"question": "什么是闭包？", "answer": "闭包是函数记住外部变量的机制。"}
        results = await orch.diagnose_round([content, expression], task, timeout=60)

        assert "content_diagnosis" in results
        assert "expression_diagnosis" in results
        assert results["content_diagnosis"].success
        assert results["expression_diagnosis"].success

    @pytest.mark.asyncio
    async def test_diagnose_transcript_integration(self):
        orch = AgentOrchestrator()
        content = ContentDiagnosisAgent()
        expression = ExpressionDiagnosisAgent()
        knowledge = KnowledgeBenchmarkingAgent()
        report = ReportGenerationAgent()

        rounds = [
            {
                "question": "什么是闭包？",
                "answer": "闭包是函数可以访问外部作用域变量的机制。",
            },
            {
                "question": "Redis缓存穿透怎么处理？",
                "answer": "用布隆过滤器，缓存空值。",
            },
        ]

        result = await orch.diagnose_transcript(
            rounds, content, expression, knowledge, report
        )

        assert len(result["rounds"]) == 2
        assert result["report"] is not None
        assert "markdown" in result["report"]
        assert result["agent_summary"]["total_rounds"] == 2

    @pytest.mark.asyncio
    async def test_empty_rounds_handling(self):
        orch = AgentOrchestrator()
        content = ContentDiagnosisAgent()
        expression = ExpressionDiagnosisAgent()
        knowledge = KnowledgeBenchmarkingAgent()
        report = ReportGenerationAgent()

        result = await orch.diagnose_transcript(
            [], content, expression, knowledge, report
        )

        assert len(result["rounds"]) == 0
