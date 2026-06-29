"""Split interview transcript into interview rounds."""

from __future__ import annotations

import re
import time
from typing import Any

from offerflow.harness.models import InterviewRound
from offerflow.harness.tools.protocol import ToolProtocol, ToolResult

_QUESTION_MARKERS = [
    r"面试官[：:]", r"Q[：:]", r"问[：:]", r"提问[：:]", r"Interviewer[：:]",
]
_ANSWER_MARKERS = [
    r"候选人[：:]", r"A[：:]", r"答[：:]", r"回答[：:]", r"Candidate[：:]",
]
_FOLLOWUP_KEYWORDS = [
    "追问", "那", "还有", "另外", "再说说", "展开", "具体", "比如",
    "举个例子", "详细", "继续", "然后呢", "还有呢",
]


class SplitRoundsTool(ToolProtocol):
    name = "split_rounds"
    description = "从面试文字稿中拆分出面试回合（话题 + 追问链）"
    parameters = {
        "type": "object",
        "properties": {
            "transcript": {"type": "string", "description": "完整的面试文字稿文本"},
        },
        "required": ["transcript"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        transcript = kwargs.get("transcript", "").strip()

        if not transcript:
            return self.make_result(
                success=False, error_type="input_error",
                error_message="transcript is empty", duration_ms=0,
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
                success=False, error_type="service_error",
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    # ── main split logic ────────────────────────────────────────────

    def _split(self, transcript: str) -> list[InterviewRound]:
        segments = self._extract_segments(transcript)
        rounds: list[InterviewRound] = []

        for i, seg in enumerate(segments):
            question = seg["question"].strip()
            answer = seg["answer"].strip()

            is_followup = False
            if rounds:
                prev_q = rounds[-1].question
                if len(question) < 30:
                    is_followup = True
                elif any(question.startswith(kw) for kw in _FOLLOWUP_KEYWORDS):
                    is_followup = True
                elif _share_key_terms(question, prev_q):
                    is_followup = True

            rounds.append(InterviewRound(
                index=i, question=question, answer=answer, is_followup=is_followup,
            ))

        # ultimate fallback: if nothing extracted, treat the whole text as
        # one Q&A by splitting at the first question mark
        if not rounds:
            chunks = re.split(r"\n+", transcript)
            chunks = [c.strip() for c in chunks if c.strip()]
            if len(chunks) >= 2:
                # first chunk = question (usually ends with ？), rest = answer
                question = chunks[0]
                answer = "\n".join(chunks[1:])
                rounds = [InterviewRound(index=0, question=question, answer=answer)]

        return rounds

    # ── segment extraction ──────────────────────────────────────────

    def _extract_segments(self, text: str) -> list[dict[str, str]]:
        q_marker = _find_marker(text, _QUESTION_MARKERS)
        a_marker = _find_marker(text, _ANSWER_MARKERS)

        if q_marker:
            return self._split_by_markers(text, q_marker, a_marker)

        return self._heuristic_split(text)

    def _split_by_markers(
        self, text: str, q_marker: str, a_marker: str | None
    ) -> list[dict[str, str]]:
        segments: list[dict[str, str]] = []
        parts = re.split(f"({q_marker})", text)
        buffer: list[str] = []

        for part in parts:
            if re.match(f"^{q_marker}", part):
                if buffer:
                    segments.append(_parse_qa(buffer, q_marker, a_marker))
                buffer = [part]
            else:
                buffer.append(part)

        if buffer:
            segments.append(_parse_qa(buffer, q_marker, a_marker))

        return [s for s in segments if s["question"] and s["answer"]]

    def _heuristic_split(self, text: str) -> list[dict[str, str]]:
        """Split by paragraphs, first trying \\n\\n then \\n."""
        segments: list[dict[str, str]] = []

        # try double-newline first
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paras) <= 1:
            # single \\n line breaks — split by \n and merge non-question lines
            paras = [p.strip() for p in text.split("\n") if p.strip()]
        paras = [p for p in paras if len(p) > 3]

        if len(paras) < 2:
            # last resort: find first question mark and split there
            m = re.search(r"[？?]", text)
            if m:
                idx = m.end()
                return [{"question": text[:idx].strip(), "answer": text[idx:].strip()}]
            return [{"question": text, "answer": ""}]

        i = 0
        while i < len(paras):
            para = paras[i]
            if _looks_like_question(para):
                question = para
                answer = paras[i + 1] if i + 1 < len(paras) else ""
                segments.append({"question": question, "answer": answer})
                i += 2
            else:
                if i + 1 < len(paras):
                    segments.append({"question": paras[i], "answer": paras[i + 1]})
                    i += 2
                else:
                    segments.append({"question": paras[i], "answer": ""})
                    i += 1

        return segments


# ── helpers ────────────────────────────────────────────────────────

def _find_marker(text: str, markers: list[str]) -> str | None:
    for marker in markers:
        if re.search(marker, text):
            return marker
    return None


def _parse_qa(buffer: list[str], q_marker: str, a_marker: str | None) -> dict[str, str]:
    full = "".join(buffer)
    question_text = re.sub(f"^{q_marker}", "", full).strip()

    if a_marker and re.search(a_marker, question_text):
        parts = re.split(a_marker, question_text, maxsplit=1)
        return {"question": parts[0].strip(), "answer": parts[1].strip()}

    return {"question": question_text, "answer": ""}


def _looks_like_question(text: str) -> bool:
    """Heuristic: does this text look like an interview question?"""
    t = text.strip()
    if t.endswith(("?", "？")):
        return True
    if "？" in t or "?" in t:
        return True
    # short lines that are likely questions
    if len(t) < 50 and ("什么" in t or "怎么" in t or "如何" in t or "为什么" in t):
        return True
    return False


def _share_key_terms(q1: str, q2: str) -> bool:
    terms1 = set(re.findall(r"[一-鿿]{2,}|\w{3,}", q1))
    terms2 = set(re.findall(r"[一-鿿]{2,}|\w{3,}", q2))
    if not terms1 or not terms2:
        return False
    return len(terms1 & terms2) >= 2
