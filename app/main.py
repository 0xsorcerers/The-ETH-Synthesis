from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.models import GenerateReportRequest
from app.services import export_report_markdown, generate_report, parse_transactions_csv

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Skynet Tax Engine",
    version="0.1.0",
    description="Jurisdiction-aware crypto tax estimation MVP for The Synthesis hackathon.",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/reports/generate")
def create_report(request: GenerateReportRequest):
    return generate_report(request)


@app.post("/reports/export-markdown")
def create_report_markdown(request: GenerateReportRequest) -> PlainTextResponse:
    export = export_report_markdown(generate_report(request))
    headers = {"Content-Disposition": f'attachment; filename="{export.filename}"'}
    return PlainTextResponse(export.content, media_type="text/markdown", headers=headers)


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


@app.post("/reports/export-markdown-from-csv")
async def create_report_markdown_from_csv(
    jurisdiction: str = Form(...),
    tax_year: int = Form(...),
    file: UploadFile = File(...),
) -> PlainTextResponse:
    transactions = parse_transactions_csv(await file.read())
    export = export_report_markdown(
        generate_report(GenerateReportRequest(jurisdiction=jurisdiction.upper(), tax_year=tax_year, transactions=transactions))
    )
    headers = {"Content-Disposition": f'attachment; filename="{export.filename}"'}
    return PlainTextResponse(export.content, media_type="text/markdown", headers=headers)
