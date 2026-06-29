"""FastAPI routes for OfferFlow diagnosis API."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import StreamingResponse

from offerflow.harness.engine.llm_client import LLMClient
from offerflow.harness.engine.token_budget import ResponseCache
from offerflow.harness.skills import DiagnoseTranscriptSkill

# in-memory report storage (Phase 7 will replace with proper persistence)
_report_store: dict[str, dict[str, Any]] = {}

# shared engine instances
_cache = ResponseCache()


def _get_llm() -> LLMClient | None:
    """Create LLM client if API key is configured, else return None (heuristic mode)."""
    import os

    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        return LLMClient()
    return None


async def diagnose_transcript(request: Request):
    """POST /api/diagnose — SSE streaming diagnosis of an interview transcript."""
    body = await request.json()
    transcript = body.get("transcript", "")

    if not transcript:
        return StreamingResponse(
            _error_stream("transcript is required"),
            media_type="text/event-stream",
        )

    report_id = str(uuid.uuid4())[:8]
    llm = _get_llm()

    async def event_stream():
        skill = DiagnoseTranscriptSkill(llm=llm, cache=_cache)
        events: list[dict[str, Any]] = []

        async def on_progress(event: str, data: dict[str, Any]):
            events.append({"event": event, "data": data})

        skill.on_progress(on_progress)

        result = await skill.execute(transcript=transcript)

        # stream accumulated events
        for evt in events:
            yield f"event: {evt['event']}\ndata: {json.dumps(evt['data'], ensure_ascii=False)}\n\n"

        if result.status.value == "completed":
            _report_store[report_id] = result.data
            yield f"event: result\ndata: {json.dumps({'report_id': report_id, 'status': 'completed'}, ensure_ascii=False)}\n\n"
        else:
            yield f"event: error\ndata: {json.dumps({'error': result.error}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def get_report(report_id: str):
    """GET /api/report/{report_id} — retrieve a historical diagnosis report."""
    from fastapi.responses import JSONResponse

    if report_id not in _report_store:
        return JSONResponse({"error": "report not found"}, status_code=404)

    return _report_store[report_id]


async def _error_stream(message: str):
    yield f"event: error\ndata: {json.dumps({'error': message})}\n\n"
