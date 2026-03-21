from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.models import GenerateReportRequest, MultiJurisdictionReportRequest
from app.services import (
    build_agent_manifest,
    build_autonomy_plan,
    export_report_html,
    export_report_markdown,
    generate_report,
    get_explanation_guide,
    inspect_csv_readiness,
    list_artifact_bundles,
    list_partner_integrations,
    list_supported_jurisdictions,
    get_jurisdiction_rule_templates,
    parse_transactions_csv,
    publish_current_work,
    preview_normalization,
    save_artifact_bundle,
    generate_multi_jurisdiction_report,
)
from app.enhanced_api import router as enhanced_router
from app.insights_api import router as insights_router
from app.un_jurisdiction_api import router as un_jurisdiction_router

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Skynet Tax Engine",
    version="2.2.0",
    description="Jurisdiction-aware crypto tax estimation with async processing, agent-first architecture, Moltbook collaboration, and comprehensive UN jurisdiction coverage for all 193 member states.",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include enhanced API routes
app.include_router(enhanced_router)
app.include_router(insights_router)
app.include_router(un_jurisdiction_router)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/partners")
def partners():
    return list_partner_integrations()


@app.get("/jurisdictions")
def jurisdictions():
    return list_supported_jurisdictions()


@app.get("/agent/manifest")
def agent_manifest():
    return build_agent_manifest()


@app.get("/guide")
def guide():
    return get_explanation_guide()


@app.post("/ingestion/readiness-from-csv")
async def ingestion_readiness_from_csv(file: UploadFile = File(...)):
    return inspect_csv_readiness(await file.read())


@app.post("/autonomy/plan-from-csv")
async def autonomy_plan_from_csv(
    jurisdiction: str = Form(...),
    tax_year: int = Form(...),
    file: UploadFile = File(...),
):
    return build_autonomy_plan(await file.read(), jurisdiction, tax_year)


@app.get("/artifacts")
def artifacts():
    return list_artifact_bundles()


@app.post("/publish")
def publish():
    return publish_current_work()


@app.post("/reports/generate")
def create_report(request: GenerateReportRequest):
    return generate_report(request)


@app.post("/reports/generate-multi")
def create_multi_jurisdiction_report(request: MultiJurisdictionReportRequest):
    return generate_multi_jurisdiction_report(request)


@app.post("/normalize/preview")
def normalize_preview(request: GenerateReportRequest):
    return preview_normalization(request)


@app.post("/reports/export-markdown")
def create_report_markdown(request: GenerateReportRequest) -> PlainTextResponse:
    export = export_report_markdown(generate_report(request))
    headers = {"Content-Disposition": f'attachment; filename="{export.filename}"'}
    return PlainTextResponse(export.content, media_type="text/markdown", headers=headers)


@app.post("/reports/export-html")
def create_report_html(request: GenerateReportRequest) -> PlainTextResponse:
    export = export_report_html(generate_report(request))
    headers = {"Content-Disposition": f'attachment; filename="{export.filename}"'}
    return PlainTextResponse(export.content, media_type="text/html", headers=headers)


@app.post("/artifacts/save")
def save_artifacts(request: GenerateReportRequest):
    return save_artifact_bundle(request)


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


@app.post("/reports/generate-multi-from-csv")
async def create_multi_jurisdiction_report_from_csv(
    jurisdictions: str = Form(...),
    tax_year: int = Form(...),
    file: UploadFile = File(...),
):
    transactions = parse_transactions_csv(await file.read())
    jurisdiction_list = [code.strip().upper() for code in jurisdictions.split(",") if code.strip()]
    return generate_multi_jurisdiction_report(
        MultiJurisdictionReportRequest(
            jurisdictions=jurisdiction_list,
            tax_year=tax_year,
            transactions=transactions,
        )
    )


@app.get("/rules/templates")
def jurisdiction_rule_templates(
    jurisdictions: str = Query(..., description="Comma-separated jurisdiction codes."),
    tax_year: int = Query(...),
):
    jurisdiction_list = [code.strip().upper() for code in jurisdictions.split(",") if code.strip()]
    return get_jurisdiction_rule_templates(jurisdiction_list, tax_year)


@app.post("/normalize/preview-from-csv")
async def normalize_preview_from_csv(
    jurisdiction: str = Form(...),
    tax_year: int = Form(...),
    file: UploadFile = File(...),
):
    transactions = parse_transactions_csv(await file.read())
    return preview_normalization(
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


@app.post("/reports/export-html-from-csv")
async def create_report_html_from_csv(
    jurisdiction: str = Form(...),
    tax_year: int = Form(...),
    file: UploadFile = File(...),
) -> PlainTextResponse:
    transactions = parse_transactions_csv(await file.read())
    export = export_report_html(
        generate_report(GenerateReportRequest(jurisdiction=jurisdiction.upper(), tax_year=tax_year, transactions=transactions))
    )
    headers = {"Content-Disposition": f'attachment; filename="{export.filename}"'}
    return PlainTextResponse(export.content, media_type="text/html", headers=headers)


@app.post("/artifacts/save-from-csv")
async def save_artifacts_from_csv(
    jurisdiction: str = Form(...),
    tax_year: int = Form(...),
    file: UploadFile = File(...),
):
    transactions = parse_transactions_csv(await file.read())
    return save_artifact_bundle(
        GenerateReportRequest(jurisdiction=jurisdiction.upper(), tax_year=tax_year, transactions=transactions)
    )
