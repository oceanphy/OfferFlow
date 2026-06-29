from fastapi import FastAPI, Request

from offerflow.api.routes import diagnose_transcript, get_report

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
