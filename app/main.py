from __future__ import annotations

from fastapi import FastAPI, File, Form, UploadFile

from app.models import GenerateReportRequest
from app.services import generate_report, parse_transactions_csv


app = FastAPI(
    title="Skynet Tax Engine",
    version="0.1.0",
    description="Jurisdiction-aware crypto tax estimation MVP for The Synthesis hackathon.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/reports/generate")
def create_report(request: GenerateReportRequest):
    return generate_report(request)


@app.post("/reports/generate-from-csv")
async def create_report_from_csv(
    jurisdiction: str = Form(...),
    tax_year: int = Form(...),
    file: UploadFile = File(...),
):
    transactions = parse_transactions_csv(await file.read())
    return generate_report(
        GenerateReportRequest(jurisdiction=jurisdiction.upper(), tax_year=tax_year, transactions=transactions)
    )

