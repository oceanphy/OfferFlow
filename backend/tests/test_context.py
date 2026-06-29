"""Tests for L4 Context layer."""

import pytest
from offerflow.harness.context import DiagnosisContext, ContextLayer


class TestContextLayer:
    def test_basic_properties(self):
        layer = ContextLayer("test", 500)
        assert layer.name == "test"
        assert layer.max_tokens == 500
        assert layer.tokens == 0
        assert not layer.is_over_limit

    def test_content_setting(self):
        layer = ContextLayer("test", 1000)
        layer.content = "Hello world"
        assert layer.tokens > 0

    def test_truncate(self):
        layer = ContextLayer("test", 10)
        long_text = "a" * 5000
        layer.content = long_text
        assert layer.is_over_limit

        layer.truncate()
        assert len(layer.content) < len(long_text)


class TestDiagnosisContext:
    def test_initial_state(self):
        ctx = DiagnosisContext()
        assert ctx.system_prompt.tokens == 0
        assert ctx.current_task.tokens == 0
        assert ctx.reference.tokens == 0
        assert ctx.history.tokens == 0

    def test_set_layers(self):
        ctx = DiagnosisContext()
        ctx.set_system_prompt("You are an interview coach. Score answers carefully.")
        ctx.set_current_task("什么是闭包？", "闭包就是函数能够访问外部作用域变量。")
        ctx.set_reference("闭包参考：词法作用域 + 外部变量保留")

        assert ctx.system_prompt.tokens > 0
        assert ctx.current_task.tokens > 0
        assert ctx.reference.tokens > 0

    def test_build_messages(self):
        ctx = DiagnosisContext()
        ctx.set_system_prompt("System instructions")
        ctx.set_current_task("Q1", "A1")
        ctx.set_reference("Reference text")

        messages = ctx.build_messages("Please analyze the answer.")

        assert len(messages) >= 2
        # first message should be system prompt
        assert messages[0]["role"] == "system"
        assert "System instructions" in messages[0]["content"]
        # last message should be user with task
        assert messages[-1]["role"] == "user"
        assert "Please analyze" in messages[-1]["content"]

    def test_add_completed_diagnosis(self):
        ctx = DiagnosisContext()
        ctx.add_completed_diagnosis(0, "回答良好，缺少深度")
        ctx.add_completed_diagnosis(1, "表达混乱，但内容准确")

        assert len(ctx._completed_diagnoses) == 2
        assert ctx.history.tokens > 0

    def test_budget_report(self):
        ctx = DiagnosisContext()
        ctx.set_system_prompt("System")
        ctx.set_current_task("Q", "A")

        report = ctx.budget_report
        assert "system_prompt" in report
        assert "current_task" in report
        assert "total" in report
        assert "completed_rounds" in report

    def test_task_truncation(self):
        ctx = DiagnosisContext()
        # set a very small max for current_task to force truncation
        ctx.current_task.max_tokens = 5
        long_q = "a" * 5000
        long_a = "b" * 5000
        ctx.set_current_task(long_q, long_a)

        # content should be truncated
        assert len(ctx.current_task.content) < len(long_q) + len(long_a)
        assert "...[truncated]" in ctx.current_task.content

    def test_total_tokens_includes_output_reserve(self):
        ctx = DiagnosisContext()
        minimal = ctx.total_tokens
        assert minimal >= ctx._OUTPUT_RESERVE
