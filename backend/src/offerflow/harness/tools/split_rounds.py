"""Split interview transcript into interview rounds."""

from __future__ import annotations

import re
import time
from typing import Any

from offerflow.harness.models import InterviewRound
from offerflow.harness.tools.protocol import ToolProtocol, ToolResult


class SplitRoundsTool(ToolProtocol):
    name = "split_rounds"
    description = "从面试文字稿中拆分出面试回合（话题 + 追问链）"
    parameters = {
        "type": "object",
        "properties": {
            "transcript": {
                "type": "string",
                "description": "完整的面试文字稿文本",
            },
        },
        "required": ["transcript"],
    }

    _QUESTION_MARKERS = [
        r"面试官[：:]",
        r"Q[：:]",
        r"问[：:]",
        r"提问[：:]",
        r"Interviewer[：:]",
    ]
    _ANSWER_MARKERS = [
        r"候选人[：:]",
        r"A[：:]",
        r"答[：:]",
        r"回答[：:]",
        r"Candidate[：:]",
    ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        transcript = kwargs.get("transcript", "")

        if not transcript or not transcript.strip():
            return self.make_result(
                success=False,
                error_type="input_error",
                error_message="transcript is empty",
                duration_ms=0,
            )

        try:
            rounds = self._split(transcript)
            return self.make_result(
                success=True,
                data=[r.__dict__ for r in rounds],
                duration_ms=(time.perf_counter() - start) * 1000,
                params={"transcript_length": len(transcript)},
            )
        except Exception as e:
            return self.make_result(
                success=False,
                error_type="service_error",
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def _split(self, transcript: str) -> list[InterviewRound]:
        segments = self._extract_segments(transcript)
        rounds: list[InterviewRound] = []
        followup_keywords = [
            "追问", "那", "还有", "另外", "再说说", "展开", "具体", "比如",
            "举个例子", "详细", "继续", "然后呢", "还有呢",
        ]

        for i, seg in enumerate(segments):
            question = seg["question"]
            answer = seg["answer"]

            is_followup = False
            if rounds:
                prev_question = rounds[-1].question
                # detect short follow-up questions
                if len(question) < 30:
                    is_followup = True
                # detect follow-up keywords
                elif any(question.strip().startswith(kw) for kw in followup_keywords):
                    is_followup = True
                # detect shared topic keywords with previous question
                elif self._share_key_terms(question, prev_question):
                    is_followup = True

            rounds.append(
                InterviewRound(
                    index=i,
                    question=question,
                    answer=answer,
                    is_followup=is_followup,
                )
            )

        return rounds

    def _extract_segments(self, text: str) -> list[dict[str, str]]:
        """Extract question-answer pairs from transcript."""
        # try marker-based splitting first
        q_marker = self._find_marker(text, self._QUESTION_MARKERS)
        a_marker = self._find_marker(text, self._ANSWER_MARKERS)

        if q_marker:
            return self._split_by_markers(text, q_marker, a_marker)

        # fallback: split by natural paragraph breaks heuristically
        return self._heuristic_split(text)

    def _find_marker(self, text: str, markers: list[str]) -> str | None:
        for marker in markers:
            if re.search(marker, text):
                return marker
        return None

    def _split_by_markers(
        self, text: str, q_marker: str, a_marker: str | None
    ) -> list[dict[str, str]]:
        segments: list[dict[str, str]] = []
        # split by question marker
        parts = re.split(f"({q_marker})", text)
        buffer: list[str] = []

        i = 0
        while i < len(parts):
            part = parts[i]
            if re.match(f"^{q_marker}", part):
                if buffer:
                    segments.append(self._parse_qa(buffer, q_marker, a_marker))
                buffer = [part]
            else:
                buffer.append(part)
            i += 1

        if buffer:
            segments.append(self._parse_qa(buffer, q_marker, a_marker))

        return [s for s in segments if s["question"] and s["answer"]]

    def _parse_qa(
        self, buffer: list[str], q_marker: str, a_marker: str | None
    ) -> dict[str, str]:
        full = "".join(buffer)
        # remove the question marker from the text
        question_text = re.sub(f"^{q_marker}", "", full).strip()

        if a_marker and re.search(a_marker, question_text):
            parts = re.split(a_marker, question_text, maxsplit=1)
            return {"question": parts[0].strip(), "answer": parts[1].strip()}

        return {"question": question_text, "answer": ""}

    def _heuristic_split(self, text: str) -> list[dict[str, str]]:
        """Fallback: treat alternating paragraphs as Q&A pairs."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        paragraphs = [p for p in paragraphs if len(p) > 5]
        segments: list[dict[str, str]] = []

        # detect if text has explicit question marks or is Q&A format
        i = 0
        while i < len(paragraphs):
            para = paragraphs[i]
            # if paragraph ends with ? or contains ？, treat as question
            if para.rstrip().endswith(("?", "？")) or "？" in para or "?" in para:
                question = para
                answer = paragraphs[i + 1] if i + 1 < len(paragraphs) else ""
                segments.append({"question": question, "answer": answer})
                i += 2
            else:
                # alternate Q&A pairs (odd = question, even = answer)
                if i + 1 < len(paragraphs):
                    segments.append(
                        {"question": paragraphs[i], "answer": paragraphs[i + 1]}
                    )
                    i += 2
                else:
                    segments.append({"question": paragraphs[i], "answer": ""})
                    i += 1

        return segments

    @staticmethod
    def _share_key_terms(q1: str, q2: str, min_chars: int = 4) -> bool:
        """Check if two questions share key terms (suggesting same topic)."""
        # extract meaningful Chinese/English words
        terms1 = set(re.findall(r"[一-鿿]{2,}|\w{3,}", q1))
        terms2 = set(re.findall(r"[一-鿿]{2,}|\w{3,}", q2))
        if not terms1 or not terms2:
            return False
        overlap = terms1 & terms2
        return len(overlap) >= 2
