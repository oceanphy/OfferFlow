from fastapi import FastAPI, Request

from offerflow.api.routes import (
    create_kb_entry,
    delete_data,
    delete_kb_entry,
    diagnose_transcript,
    get_kb_entry,
    get_report,
    list_kb_entries,
    update_kb_entry,
)

app = FastAPI(title="OfferFlow", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/diagnose")
async def diagnose(request: Request):
    return await diagnose_transcript(request)


@app.get("/api/report/{report_id}")
async def report(report_id: str):
    return await get_report(report_id)


@app.delete("/api/user/data")
async def delete_user():
    return await delete_data()


# Knowledge base CRUD
@app.get("/api/knowledge/entries")
async def kb_list():
    return await list_kb_entries()


@app.post("/api/knowledge/entries")
async def kb_create(request: Request):
    return await create_kb_entry(request)


@app.get("/api/knowledge/entries/{entry_id}")
async def kb_get(entry_id: str):
    return await get_kb_entry(entry_id)


@app.put("/api/knowledge/entries/{entry_id}")
async def kb_update(entry_id: str, request: Request):
    return await update_kb_entry(entry_id, request)


@app.delete("/api/knowledge/entries/{entry_id}")
async def kb_delete(entry_id: str):
    return await delete_kb_entry(entry_id)
