"""Generate a structured diagnosis report from round diagnoses."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from offerflow.harness.tools.protocol import ToolProtocol, ToolResult


class GenerateReportTool(ToolProtocol):
    name = "generate_report"
    description = "汇总所有诊断，生成完整的结构化诊断报告（Markdown 格式）"
    parameters = {
        "type": "object",
        "properties": {
            "rounds": {
                "type": "array",
                "description": "所有面试回合的诊断数据",
                "items": {"type": "object"},
            },
        },
        "required": ["rounds"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        rounds = kwargs.get("rounds", [])

        if not rounds:
            return self.make_result(
                success=False,
                error_type="input_error",
                error_message="rounds is empty",
                duration_ms=0,
            )

        try:
            report_md = self._generate(rounds)
            summary_data = self._summarize(rounds)
            return self.make_result(
                success=True,
                data={
                    "markdown": report_md,
                    "summary": summary_data,
                },
                duration_ms=(time.perf_counter() - start) * 1000,
                params={"round_count": len(rounds)},
            )
        except Exception as e:
            return self.make_result(
                success=False,
                error_type="service_error",
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def _generate(self, rounds: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        lines.append("# 面试诊断报告")
        lines.append(f"\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

        # overall summary
        overall = self._calc_overall(rounds)
        lines.append("## 总体评分\n")
        lines.append(f"**综合得分：{overall['total']:.1f} / 10**\n")
        lines.append("| 维度 | 得分 |")
        lines.append("|---|---|")
        for dim, score in overall["dimensions"].items():
            lines.append(f"| {dim} | {score:.1f} / 10 |")

        # per-round details
        lines.append("\n---\n")
        lines.append("## 逐题诊断\n")
        for i, rd in enumerate(rounds):
            lines.append(f"### 第 {i + 1} 回合\n")
            lines.append(f"**问题：** {rd.get('question', '')}\n")
            lines.append(f"**回答：** {rd.get('answer', '')}\n")

            content = rd.get("content", {})
            if content:
                lines.append(f"**内容评分：** 完整性 {content.get('completeness_score', '-')} | "
                             f"准确性 {content.get('accuracy_score', '-')} | "
                             f"深度 {content.get('depth_score', '-')}\n")
                if content.get("highlights"):
                    lines.append("\n**亮点：**\n")
                    for h in content["highlights"]:
                        lines.append(f"- {h}")
                if content.get("gaps"):
                    lines.append("\n**差距：**\n")
                    for g in content["gaps"]:
                        if not isinstance(g, dict):
                            g = vars(g)
                        lines.append(f"- {g.get('description', '')}")
                        if g.get("suggestion"):
                            lines.append(f"  > 建议：{g['suggestion']}")
                lines.append("")

            expression = rd.get("expression", {})
            if expression:
                lines.append(f"**表达评分：** 连贯性 {expression.get('coherence_score', '-')} | "
                             f"结构性 {expression.get('structure_score', '-')} | "
                             f"措辞 {expression.get('precision_score', '-')}\n")

            lines.append("---\n")

        return "\n".join(lines)

    def _calc_overall(self, rounds: list[dict[str, Any]]) -> dict[str, Any]:
        content_scores: list[float] = []
        expression_scores: list[float] = []

        for rd in rounds:
            c = rd.get("content", {})
            if c:
                content_scores.append(
                    (c.get("completeness_score", 0)
                     + c.get("accuracy_score", 0)
                     + c.get("depth_score", 0))
                    / 3
                )
            e = rd.get("expression", {})
            if e:
                expression_scores.append(
                    (e.get("coherence_score", 0)
                     + e.get("structure_score", 0)
                     + e.get("precision_score", 0))
                    / 3
                )

        avg_content = sum(content_scores) / len(content_scores) if content_scores else 0
        avg_expression = (
            sum(expression_scores) / len(expression_scores) if expression_scores else 0
        )
        total = avg_content * 0.6 + avg_expression * 0.4

        return {
            "total": round(total, 1),
            "dimensions": {
                "内容维度 (60%)": round(avg_content, 1),
                "表达维度 (40%)": round(avg_expression, 1),
            },
        }

    @staticmethod
    def _summarize(rounds: list[dict[str, Any]]) -> dict[str, Any]:
        """Extract structured summary from rounds."""
        all_gaps: list[str] = []
        all_highlights: list[str] = []

        for rd in rounds:
            c = rd.get("content", {})
            if c:
                for g in c.get("gaps", []):
                    if not isinstance(g, dict):
                        g = vars(g)
                    all_gaps.append(g.get("description", ""))
                all_highlights.extend(c.get("highlights", []))

        return {
            "total_rounds": len(rounds),
            "total_gaps": len(all_gaps),
            "total_highlights": len(all_highlights),
            "top_gaps": all_gaps[:5],
            "top_highlights": all_highlights[:5],
        }
