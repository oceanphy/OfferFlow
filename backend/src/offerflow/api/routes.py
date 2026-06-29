"""FastAPI routes for OfferFlow diagnosis API."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from offerflow.harness.engine.llm_client import BaseLLMClient, create_llm_client
from offerflow.harness.engine.token_budget import ResponseCache
from offerflow.harness.memory.store import (
    DiagnosisHistory,
    SessionContext,
    UserProfile,
)
from offerflow.harness.permission.privacy import anonymize_for_model, delete_user_data
from offerflow.harness.skills import DiagnoseTranscriptSkill

_report_store: dict[str, dict[str, Any]] = {}
_cache = ResponseCache()
_kb_entries: list[dict[str, Any]] = []


def _get_llm() -> BaseLLMClient | None:
    return create_llm_client()


async def diagnose_transcript(request: Request):
    """POST /api/diagnose — SSE streaming diagnosis of an interview transcript."""
    body = await request.json()
    transcript = body.get("transcript", "")

    if not transcript:
        return StreamingResponse(
            _error_stream("transcript is required"),
            media_type="text/event-stream",
        )

    # anonymize before sending to model
    safe_transcript = anonymize_for_model(transcript)

    report_id = str(uuid.uuid4())[:8]
    session_id = str(uuid.uuid4())[:8]
    llm = _get_llm()

    # session checkpoint
    session_ctx = SessionContext(
        session_id=session_id,
        transcript=safe_transcript,
        status="pending",
    )
    session_ctx.save()

    async def event_stream():
        skill = DiagnoseTranscriptSkill(llm=llm, cache=_cache)
        events: list[dict[str, Any]] = []

        async def on_progress(event: str, data: dict[str, Any]):
            events.append({"event": event, "data": data})

        skill.on_progress(on_progress)

        session_ctx.status = "diagnosing"
        session_ctx.save()

        result = await skill.execute(transcript=safe_transcript)

        for evt in events:
            yield f"event: {evt['event']}\ndata: {json.dumps(evt['data'], ensure_ascii=False)}\n\n"

        if result.status.value == "completed":
            _report_store[report_id] = result.data
            session_ctx.status = "complete"
            session_ctx.report_id = report_id
            session_ctx.save()

            # update memory
            profile = UserProfile.load()
            profile.update_from_diagnosis(result.data)
            profile.save()

            history = DiagnosisHistory.load()
            summary = result.data.get("report", {}).get("summary", {})
            history.add_session(report_id, summary)
            history.save()

            yield f"event: result\ndata: {json.dumps({'report_id': report_id, 'status': 'completed'}, ensure_ascii=False)}\n\n"
        else:
            session_ctx.status = "failed"
            session_ctx.save()
            yield f"event: error\ndata: {json.dumps({'error': result.error}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def get_report(report_id: str):
    if report_id not in _report_store:
        return JSONResponse({"error": "report not found"}, status_code=404)
    return _report_store[report_id]


async def delete_data():
    """DELETE /api/user/data — delete all stored user data."""
    deleted = delete_user_data()
    _report_store.clear()
    return {"deleted": deleted}


# --- Knowledge Base CRUD (Phase 9) ---

async def list_kb_entries():
    return {"entries": _kb_entries, "total": len(_kb_entries)}


async def create_kb_entry(request: Request):
    body = await request.json()
    entry = {
        "id": str(uuid.uuid4())[:8],
        "topic": body.get("topic", ""),
        "keywords": body.get("keywords", []),
        "model_answer": body.get("model_answer", ""),
        "scoring_criteria": body.get("scoring_criteria", ""),
        "common_pitfalls": body.get("common_pitfalls", []),
    }
    _kb_entries.append(entry)
    return entry


async def get_kb_entry(entry_id: str):
    for e in _kb_entries:
        if e["id"] == entry_id:
            return e
    return JSONResponse({"error": "entry not found"}, status_code=404)


async def update_kb_entry(entry_id: str, request: Request):
    body = await request.json()
    for e in _kb_entries:
        if e["id"] == entry_id:
            e.update({k: v for k, v in body.items() if k != "id"})
            return e
    return JSONResponse({"error": "entry not found"}, status_code=404)


async def delete_kb_entry(entry_id: str):
    global _kb_entries
    _kb_entries = [e for e in _kb_entries if e["id"] != entry_id]
    return {"deleted": True}


async def _error_stream(message: str):
    yield f"event: error\ndata: {json.dumps({'error': message})}\n\n"
