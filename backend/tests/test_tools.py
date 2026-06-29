"""Tests for L1 Tools and L3 Engine."""

import pytest
from unittest.mock import AsyncMock
from offerflow.harness.tools import (
    AnalyzeContentTool,
    AnalyzeExpressionTool,
    GenerateReportTool,
    QueryKnowledgeBaseTool,
    SplitRoundsTool,
)
from offerflow.harness.models import KnowledgeBaseEntry


class TestSplitRoundsTool:
    @pytest.mark.asyncio
    async def test_split_marked_transcript(self):
        tool = SplitRoundsTool()
        transcript = (
            "面试官：你的项目用了Redis，怎么处理缓存穿透？\n"
            "候选人：我用布隆过滤器来应对缓存穿透。\n"
            "面试官：能详细讲一下布隆过滤器的原理吗？\n"
            "候选人：布隆过滤器是一种空间效率高的概率数据结构，用多个哈希函数来判断一个元素是否在集合中。"
        )
        result = await tool.execute(transcript=transcript)

        assert result.success
        assert len(result.data) >= 2
        assert "缓存穿透" in result.data[0]["question"]
        assert "布隆过滤器" in result.data[0]["answer"]

        # second round should be a follow-up
        followups = [r for r in result.data if r.get("is_followup")]
        assert len(followups) >= 1

    @pytest.mark.asyncio
    async def test_split_heuristic_fallback(self):
        tool = SplitRoundsTool()
        transcript = (
            "你对微服务架构的理解是什么？\n\n"
            "微服务是将单体应用拆分为独立的小服务，每个服务有自己的数据存储。\n\n"
            "你们项目里微服务之间怎么通信的？\n\n"
            "主要用gRPC做同步调用，异步消息用Kafka。"
        )
        result = await tool.execute(transcript=transcript)

        assert result.success
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_empty_transcript(self):
        tool = SplitRoundsTool()
        result = await tool.execute(transcript="")

        assert not result.success
        assert result.error_type == "input_error"

    @pytest.mark.asyncio
    async def test_audit_fields(self):
        tool = SplitRoundsTool()
        result = await tool.execute(transcript="面试官：测试？\n候选人：测试回答。")

        assert result.success
        assert result.tool_name == "split_rounds"
        assert result.duration_ms >= 0
        assert "transcript_length" in result.params


class TestAnalyzeContentTool:
    @pytest.mark.asyncio
    async def test_basic_analysis(self):
        tool = AnalyzeContentTool()
        result = await tool.execute(
            question="Redis缓存穿透怎么处理？",
            answer="用布隆过滤器，把所有可能存在的key哈希到一个bitmap里，查询时先过布隆过滤器，不存在的直接返回空。",
        )

        assert result.success
        data = result.data
        assert "completeness_score" in data
        assert "accuracy_score" in data
        assert "depth_score" in data
        assert isinstance(data["highlights"], list)
        assert isinstance(data["gaps"], list)

    @pytest.mark.asyncio
    async def test_analysis_with_kb_entry(self):
        tool = AnalyzeContentTool()
        kb_entry = KnowledgeBaseEntry(
            id="kb-1",
            topic="缓存穿透",
            keywords=["布隆过滤器", "缓存穿透", "空值缓存"],
            model_answer="缓存穿透的解决方案包括布隆过滤器和缓存空值。布隆过滤器利用多个哈希函数判断key是否存在，能高效过滤非法请求。缓存空值是将不存在的key也缓存起来，设置较短过期时间。",
        )
        result = await tool.execute(
            question="Redis缓存穿透怎么处理？",
            answer="布隆过滤器就行。",
            evidence={"knowledge_base_entry": kb_entry},
        )

        assert result.success
        data = result.data
        # should have lower completeness due to missing "空值缓存"
        assert data["completeness_score"] < 8
        assert len(data["gaps"]) > 0

    @pytest.mark.asyncio
    async def test_uncertain_answer_penalized(self):
        tool = AnalyzeContentTool()
        result_clear = await tool.execute(
            question="什么是闭包？",
            answer="闭包是函数能够访问其外部作用域变量的机制，核心原理是词法作用域。",
        )
        result_uncertain = await tool.execute(
            question="什么是闭包？",
            answer="闭包好像是函数可以记住外面的变量，可能跟作用域有关，大概是这样，我也不太确定。",
        )

        assert result_clear.success and result_uncertain.success
        assert result_clear.data["accuracy_score"] > result_uncertain.data["accuracy_score"]

    @pytest.mark.asyncio
    async def test_missing_input(self):
        tool = AnalyzeContentTool()
        result = await tool.execute(question="", answer="something")

        assert not result.success
        assert result.error_type == "input_error"


class TestQueryKnowledgeBaseTool:
    @pytest.mark.asyncio
    async def test_empty_entries(self):
        tool = QueryKnowledgeBaseTool()
        result = await tool.execute(question="什么是闭包？")

        assert result.success
        assert len(result.data["entries"]) == 0

    @pytest.mark.asyncio
    async def test_keyword_match(self):
        entries = [
            KnowledgeBaseEntry(
                id="kb-1",
                topic="闭包",
                keywords=["闭包", "Closure", "词法作用域"],
            ),
            KnowledgeBaseEntry(
                id="kb-2",
                topic="缓存穿透",
                keywords=["Redis", "缓存穿透", "布隆过滤器"],
            ),
        ]
        tool = QueryKnowledgeBaseTool(entries=entries)
        result = await tool.execute(question="请讲一下JavaScript闭包是什么？")

        assert result.success
        assert len(result.data["entries"]) >= 1
        assert result.data["entries"][0]["id"] == "kb-1"

    @pytest.mark.asyncio
    async def test_no_match(self):
        entries = [
            KnowledgeBaseEntry(
                id="kb-3",
                topic="微服务",
                keywords=["微服务", "Docker", "Kubernetes"],
            ),
        ]
        tool = QueryKnowledgeBaseTool(entries=entries)
        result = await tool.execute(question="闭包是什么？")

        assert result.success
        assert len(result.data["entries"]) == 0

    @pytest.mark.asyncio
    async def test_top_k(self):
        entries = [
            KnowledgeBaseEntry(id=f"kb-{i}", topic=f"topic_{i}", keywords=[f"kw_{i}"])
            for i in range(10)
        ]
        tool = QueryKnowledgeBaseTool(entries=entries)
        result = await tool.execute(question="topic_1 kw_1", top_k=2)

        assert result.success
        assert len(result.data["entries"]) <= 2


class TestGenerateReportTool:
    @pytest.mark.asyncio
    async def test_generates_markdown(self):
        tool = GenerateReportTool()
        rounds = [
            {
                "question": "Redis缓存穿透怎么处理？",
                "answer": "用布隆过滤器。",
                "content": {
                    "completeness_score": 5.0,
                    "accuracy_score": 6.0,
                    "depth_score": 4.0,
                    "highlights": ["提到了布隆过滤器"],
                    "gaps": [
                        {"description": "缺少缓存空值方案", "suggestion": "补充空值缓存说明"}
                    ],
                },
                "expression": {
                    "coherence_score": 6.0,
                    "structure_score": 5.0,
                    "precision_score": 6.0,
                },
            }
        ]
        result = await tool.execute(rounds=rounds)

        assert result.success
        assert "markdown" in result.data
        assert "面试诊断报告" in result.data["markdown"]
        assert "Redis缓存穿透" in result.data["markdown"]
        assert result.data["summary"]["total_rounds"] == 1
        assert result.data["summary"]["total_gaps"] == 1

    @pytest.mark.asyncio
    async def test_empty_rounds(self):
        tool = GenerateReportTool()
        result = await tool.execute(rounds=[])

        assert not result.success
        assert result.error_type == "input_error"

    @pytest.mark.asyncio
    async def test_overall_score_calculation(self):
        tool = GenerateReportTool()
        rounds = [
            {
                "question": "Q1",
                "answer": "A1",
                "content": {
                    "completeness_score": 8.0,
                    "accuracy_score": 8.0,
                    "depth_score": 8.0,
                },
                "expression": {
                    "coherence_score": 6.0,
                    "structure_score": 6.0,
                    "precision_score": 6.0,
                },
            },
            {
                "question": "Q2",
                "answer": "A2",
                "content": {
                    "completeness_score": 4.0,
                    "accuracy_score": 4.0,
                    "depth_score": 4.0,
                },
                "expression": {
                    "coherence_score": 4.0,
                    "structure_score": 4.0,
                    "precision_score": 4.0,
                },
            },
        ]
        result = await tool.execute(rounds=rounds)

        assert result.success
        md = result.data["markdown"]
        # average content = (8+4)/2 = 6, expression = (6+4)/2 = 5, total = 6*0.6 + 5*0.4 = 5.6
        assert "5.6" in md


class TestAnalyzeExpressionTool:
    @pytest.mark.asyncio
    async def test_basic_analysis(self):
        tool = AnalyzeExpressionTool()
        result = await tool.execute(
            question="什么是闭包？",
            answer="闭包是函数可以访问外部作用域变量的机制，核心在于词法作用域。",
        )

        assert result.success
        data = result.data
        assert "coherence_score" in data
        assert "structure_score" in data
        assert "precision_score" in data

    @pytest.mark.asyncio
    async def test_filler_words_penalized(self):
        tool = AnalyzeExpressionTool()
        result = await tool.execute(
            question="什么是缓存穿透？",
            answer="呃，缓存穿透就是，那个，大量的请求直接穿透了缓存层，然后呢，怎么说呢，打到了数据库上，然后呢，怎么说呢，可能会导致数据库压力过大。",
        )

        assert result.success
        assert len(result.data["gaps"]) >= 1
        gap_descs = [
            g.description if hasattr(g, "description") else g["description"]
            for g in result.data["gaps"]
        ]
        assert any("语气词" in d for d in gap_descs)

    @pytest.mark.asyncio
    async def test_structured_answer_bonus(self):
        tool = AnalyzeExpressionTool()
        result = await tool.execute(
            question="怎么优化数据库性能？",
            answer="首先，优化可以从几个方面考虑。第一，索引优化。第二，SQL优化。第三，架构层面优化比如读写分离。总结一下，必须从多个层面协同优化。",
        )

        assert result.success
        assert result.data["structure_score"] > 5


class TestTokenBudget:
    def test_budget_tracking(self):
        from offerflow.harness.engine.token_budget import TokenBudget

        budget = TokenBudget(max_tokens=1000)
        assert budget.remaining == 1000

        assert budget.consume(300)
        assert budget.used == 300
        assert budget.remaining == 700

    def test_budget_exceeded(self):
        from offerflow.harness.engine.token_budget import TokenBudget

        budget = TokenBudget(max_tokens=100)
        budget.consume(80)
        assert not budget.consume(30)
        assert budget.used == 80

    def test_estimate(self):
        from offerflow.harness.engine.token_budget import TokenBudget

        assert TokenBudget.estimate("hello world") > 0
        assert TokenBudget.estimate("你好世界") > 0


class TestResponseCache:
    def test_cache_hit(self):
        from offerflow.harness.engine.token_budget import ResponseCache

        cache = ResponseCache()
        msgs = [{"role": "user", "content": "hello"}]

        assert cache.get(msgs, "gpt-4") is None
        cache.set(msgs, "gpt-4", "world")
        assert cache.get(msgs, "gpt-4") == "world"

    def test_different_model_miss(self):
        from offerflow.harness.engine.token_budget import ResponseCache

        cache = ResponseCache()
        msgs = [{"role": "user", "content": "hello"}]
        cache.set(msgs, "gpt-4", "response")
        assert cache.get(msgs, "gpt-3.5") is None


class TestLLMAnalyzeContent:
    @pytest.mark.asyncio
    async def test_llm_driven_analysis(self):
        """Simulate LLM-driven analysis with a mock client."""
        from offerflow.harness.tools import AnalyzeContentTool

        mock_llm = AsyncMock()
        mock_llm.model = "gpt-4o-mini"
        mock_llm.complete.return_value = """```json
{
  "completeness_score": 7.5,
  "accuracy_score": 8.0,
  "depth_score": 6.5,
  "highlights": ["提到了核心概念"],
  "gaps": [
    {
      "location": "回答后半段",
      "description": "缺少对哈希冲突处理的说明",
      "reference": "应说明不同哈希函数如何降低误判率",
      "suggestion": "补充：布隆过滤器使用多个独立哈希函数，当所有哈希函数都返回1时才判定存在"
    }
  ]
}
```"""

        tool = AnalyzeContentTool(llm=mock_llm)
        result = await tool.execute(
            question="布隆过滤器的原理是什么？",
            answer="布隆过滤器是用多个哈希函数来判断元素是否在集合中的数据结构。",
        )

        assert result.success
        assert result.data["completeness_score"] == 7.5
        assert result.data["accuracy_score"] == 8.0
        assert result.data["depth_score"] == 6.5
        assert len(result.data["highlights"]) == 1
        assert len(result.data["gaps"]) == 1
        mock_llm.complete.assert_called_once()
