"""L4: Context manager — layered injection with token budgets and auto-compression."""

from __future__ import annotations

import json
from typing import Any

from offerflow.harness.engine.llm_client import BaseLLMClient
from offerflow.harness.engine.token_budget import TokenBudget

COMPRESSION_PROMPT = """Summarize these completed interview round diagnoses into a compact form.

For each completed round, keep only:
- Question topic (one line)
- Key finding (what went well, what went wrong — one line each)
- Score summary

Be extremely concise. Every token matters.

Diagnoses to compress:
{diagnoses}"""


class ContextLayer:
    """A single layer in the hierarchical context."""

    def __init__(self, name: str, max_tokens: int) -> None:
        self.name = name
        self.max_tokens = max_tokens
        self._content = ""

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        self._content = value

    @property
    def tokens(self) -> int:
        return TokenBudget.estimate(self._content)

    @property
    def is_over_limit(self) -> bool:
        return self.tokens > self.max_tokens

    def truncate(self) -> None:
        """Brute-force truncation to stay within token limit."""
        if not self._content or self.tokens <= self.max_tokens:
            return
        ratio = self.max_tokens / self.tokens * 0.9
        cutoff = int(len(self._content) * ratio)
        self._content = self._content[:cutoff] + "\n...[truncated]"


class DiagnosisContext:
    """Manages the 4-layer context for interview diagnosis.

    Layers:
        system_prompt  — diagnosis criteria, scoring dimensions (< 2000 tokens, fixed)
        current_task   — current round Q&A being diagnosed (< 2000 tokens)
        reference      — knowledge base entries for this question (< 3000 tokens)
        history        — compressed summaries of completed rounds (< 2000 tokens)
        output         — reserved for model output (>= 4000 tokens)
    """

    _OUTPUT_RESERVE = 4000

    def __init__(self, llm: BaseLLMClient | None = None) -> None:
        self._llm = llm
        self.system_prompt = ContextLayer("system_prompt", 2000)
        self.current_task = ContextLayer("current_task", 2000)
        self.reference = ContextLayer("reference", 3000)
        self.history = ContextLayer("history", 2000)
        self._completed_diagnoses: list[str] = []

    def set_system_prompt(self, text: str) -> None:
        self.system_prompt.content = text
        if self.system_prompt.is_over_limit:
            self.system_prompt.truncate()

    def set_current_task(self, question: str, answer: str) -> None:
        content = f"## 当前问题\n{question}\n\n## 候选人回答\n{answer}"
        self.current_task.content = content
        if self.current_task.is_over_limit:
            self.current_task.truncate()

    def set_reference(self, text: str) -> None:
        self.reference.content = text
        if self.reference.is_over_limit:
            self.reference.truncate()

    def add_completed_diagnosis(self, round_index: int, summary: str) -> None:
        self._completed_diagnoses.append(
            f"## 第{round_index + 1}回合\n{summary}"
        )
        self._rebuild_history()

    async def compress_history(self) -> None:
        """Use LLM to compress the completed diagnoses into a tight summary."""
        if not self._completed_diagnoses or self.history.tokens <= self.history.max_tokens:
            return

        if self._llm:
            full_text = "\n".join(self._completed_diagnoses)
            prompt = COMPRESSION_PROMPT.format(diagnoses=full_text)
            try:
                compressed = await self._llm.complete(
                    [{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=1000,
                )
                self._completed_diagnoses = [compressed]
            except Exception:
                pass  # fallback: keep original, will be truncated

        self._rebuild_history()

    def _rebuild_history(self) -> None:
        self.history.content = "\n".join(self._completed_diagnoses)
        if self.history.is_over_limit:
            self.history.truncate()

    def build_messages(
        self, task_prompt: str
    ) -> list[dict[str, str]]:
        """Build the final messages array for LLM invocation."""
        messages: list[dict[str, str]] = []

        if self.system_prompt.content:
            messages.append({"role": "system", "content": self.system_prompt.content})

        context_parts: list[str] = []
        if self.reference.content:
            context_parts.append(f"## 参考资料\n{self.reference.content}")
        if self.history.content:
            context_parts.append(f"## 已完成回合摘要\n{self.history.content}")

        if context_parts:
            context_block = "\n\n".join(context_parts)
            messages.append({"role": "system", "content": context_block})

        task_content = self.current_task.content
        if task_content:
            task_content = f"{task_content}\n\n{task_prompt}"
        else:
            task_content = task_prompt
        messages.append({"role": "user", "content": task_content})

        return messages

    @property
    def total_tokens(self) -> int:
        return (
            self.system_prompt.tokens
            + self.current_task.tokens
            + self.reference.tokens
            + self.history.tokens
            + self._OUTPUT_RESERVE
        )

    @property
    def budget_report(self) -> dict[str, Any]:
        """Token budget snapshot for monitoring."""
        return {
            "system_prompt": self.system_prompt.tokens,
            "current_task": self.current_task.tokens,
            "reference": self.reference.tokens,
            "history": self.history.tokens,
            "output_reserve": self._OUTPUT_RESERVE,
            "total": self.total_tokens,
            "completed_rounds": len(self._completed_diagnoses),
        }
