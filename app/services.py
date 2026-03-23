from __future__ import annotations

import csv
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from io import StringIO
from pathlib import Path

from fastapi import HTTPException

from app.models import (
    PublishedBuild,
    AutonomyPlan,
    AutonomyPlanStats,
    AutonomyPlanStep,
    ArtifactBundle,
    ArtifactBundleSummary,
    ClassifiedTransaction,
    EventRule,
    ExplanationGuide,
    ExplanationItem,
    GenerateReportRequest,
    HtmlExport,
    IngestionIssue,
    IngestionReadinessReport,
    IngestionReadinessSummary,
    MarkdownExport,
    MultiJurisdictionComparisonRow,
    MultiJurisdictionReport,
    MultiJurisdictionReportRequest,
    AgentManifest,
    JurisdictionReportResult,
    JurisdictionRuleTemplate,
    NormalizedTransaction,
    NormalizationPreviewItem,
    PartnerIntegration,
    ReportLineItem,
    ReportSummary,
    RuleSet,
    RuleTemplateEvent,
    SupportedJurisdiction,
    TaxReport,
    TaxTreatment,
    TransactionRecord,
    WorkflowStep,
)
from app.un_jurisdictions import get_un_jurisdiction_db


RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
PUBLISHED_DIR = Path(__file__).resolve().parent.parent / "published"
COLLABORATION_LOG_PATH = Path(__file__).resolve().parent.parent / "docs" / "collaboration-log.md"
REQUIRED_CSV_COLUMNS = [
    "tx_id",
    "timestamp",
    "asset",
    "quantity",
    "tx_hash",
    "network",
    "wallet_provider",
    "source_app",
    "event_hint",
    "price_usd",
    "proceeds_usd",
    "fee_usd",
    "counter_asset",
    "counter_quantity",
    "description",
]
ETHERSCAN_REQUIRED_COLUMNS = [
    "transaction hash",
    "datetime (utc)",
    "from",
    "to",
    "value_in(eth)",
    "value_out(eth)",
    "txnfee(eth)",
    "txnfee(usd)",
    "historical $price/eth",
    "method",
]
DEFAULT_BASELINE_TAX_YEAR = 2025
GLOBAL_BASELINE_JURISDICTION_LABEL = "UN-ALIGNED BASELINE"
GLOBAL_BASELINE_CITATIONS = [
    {
        "title": "OECD Crypto-Asset Reporting Framework and Amendments to the Common Reporting Standard (2023)",
        "url": "https://www.oecd.org/tax/exchange-of-tax-information/crypto-asset-reporting-framework-and-amendments-to-the-common-reporting-standard.htm",
        "authority": "OECD",
    },
    {
        "title": "UN Handbook on Selected Issues in Taxation of the Extractive Industries by Developing Countries",
        "url": "https://www.un.org/development/desa/financing/publication/handbook-selected-issues-taxation-extractive-industries-developing-countries",
        "authority": "United Nations",
    },
]
PARTNER_INTEGRATIONS = [
    PartnerIntegration(
        id="base",
        name="Base",
        status="active",
        category="network",
        description="EVM network metadata and chain-aware transaction reporting for Base activity.",
        docs_url="https://docs.base.org/",
    ),
    PartnerIntegration(
        id="celo",
        name="Celo",
        status="active",
        category="network",
        description="Additional supported chain metadata and routing for Celo transactions.",
        docs_url="https://docs.celo.org/",
    ),
    PartnerIntegration(
        id="metamask",
        name="MetaMask",
        status="active",
        category="wallet",
        description="Wallet-origin metadata to label imported transactions and prep future wallet connection flows.",
        docs_url="https://docs.metamask.io/",
    ),
    PartnerIntegration(
        id="uniswap",
        name="Uniswap",
        status="active",
        category="protocol",
        description="Protocol-aware swap detection when transaction metadata indicates Uniswap execution.",
        docs_url="https://docs.uniswap.org/",
    ),
    PartnerIntegration(
        id="self",
        name="Self",
        status="planned",
        category="identity",
        description="Identity verification path for compliance-sensitive workflows and gated exports.",
        docs_url="https://docs.self.xyz/frontend-integration/qrcode-sdk",
    ),
]


@dataclass
class Lot:
    quantity: float
    unit_cost_usd: float


def load_rule_set(jurisdiction: str, tax_year: int) -> RuleSet:
    return _load_rule_set_cached(jurisdiction.upper(), tax_year)


@lru_cache(maxsize=64)
def _load_rule_set_cached(jurisdiction: str, tax_year: int) -> RuleSet:
    path = RULES_DIR / f"{jurisdiction.lower()}_{tax_year}.sample.json"
    if not path.exists():
        if _is_open_jurisdiction_code(jurisdiction):
            return _build_global_baseline_ruleset(jurisdiction, tax_year)
        raise HTTPException(
            status_code=404,
            detail=f"No rule set found for {jurisdiction} {tax_year}. Use a 2-3 letter jurisdiction code for UN-aligned baseline rules.",
        )
    with path.open("r", encoding="utf-8") as handle:
        return RuleSet.model_validate(json.load(handle))


def _is_open_jurisdiction_code(jurisdiction: str) -> bool:
    return bool(re.match(r"^[A-Z]{2,3}$", jurisdiction))


def _build_global_baseline_ruleset(jurisdiction: str, tax_year: int) -> RuleSet:
    baseline_treatments: dict[str, TaxTreatment] = {
        "income": "taxable_income",
        "staking": "taxable_income",
        "airdrop": "taxable_income",
        "mining": "taxable_income",
        "swap": "capital_gains",
        "nft_sale": "capital_gains",
        "transfer": "non_taxable",
        "unstaking": "mixed",
        "lp_deposit": "mixed",
        "lp_withdrawal": "mixed",
    }
    event_rules = [
        EventRule(
            eventType=event_type,
            taxTreatment=tax_treatment,
            calculationMethod="baseline_fifo_with_manual_review",
            confidence=0.62 if tax_treatment == "mixed" else 0.68,
            notes=(
                "Generated from UN-aligned public-tax baseline. "
                "Confirm with jurisdiction-specific law before filing."
            ),
            citations=GLOBAL_BASELINE_CITATIONS,
        )
        for event_type, tax_treatment in baseline_treatments.items()
    ]
    return RuleSet(
        jurisdiction=jurisdiction,
        taxYear=tax_year,
        version=f"{GLOBAL_BASELINE_JURISDICTION_LABEL.lower().replace(' ', '-')}-{tax_year}",
        fallbackPolicy={
            "mode": "manual_review_required",
            "description": (
                "Jurisdiction-specific crypto guidance was not found in local packs. "
                "Applied UN-aligned baseline estimates anchored to public international tax references."
            ),
        },
        eventRules=event_rules,
    )


def parse_transactions_csv(content: bytes) -> list[TransactionRecord]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    rows: list[TransactionRecord] = []
    for index, row in enumerate(reader, start=1):
        normalized = {key.strip().lower(): (value.strip() if isinstance(value, str) else value) for key, value in row.items()}
        normalized = _normalize_source_row(normalized, index)
        try:
            rows.append(
                TransactionRecord(
                    tx_id=normalized["tx_id"] or f"row-{index}",
                    timestamp=normalized["timestamp"],
                    asset=normalized["asset"],
                    quantity=float(normalized["quantity"]),
                    tx_hash=normalized.get("tx_hash") or None,
                    network=normalized.get("network") or None,
                    wallet_provider=normalized.get("wallet_provider") or None,
                    source_app=normalized.get("source_app") or None,
                    event_hint=normalized.get("event_hint") or None,
                    price_usd=_optional_float(normalized.get("price_usd")),
                    proceeds_usd=_optional_float(normalized.get("proceeds_usd")),
                    fee_usd=_optional_float(normalized.get("fee_usd")) or 0,
                    counter_asset=normalized.get("counter_asset") or None,
                    counter_quantity=_optional_float(normalized.get("counter_quantity")),
                    description=normalized.get("description") or None,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Missing CSV column: {exc.args[0]}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid CSV value on row {index}: {exc}") from exc
    if not rows:
        raise HTTPException(status_code=400, detail="CSV contained no transactions")
    return rows


def inspect_csv_readiness(content: bytes) -> IngestionReadinessReport:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    present_columns = [header.strip().lower() for header in (reader.fieldnames or []) if isinstance(header, str)]
    is_etherscan_csv = _is_etherscan_schema(present_columns)
    missing_columns = [] if is_etherscan_csv else [column for column in REQUIRED_CSV_COLUMNS if column not in present_columns]
    issues: list[IngestionIssue] = []
    total_rows = 0
    valid_rows = 0
    seen_tx_ids: set[str] = set()

    if missing_columns:
        issues.append(
            IngestionIssue(
                severity="error",
                scope="file",
                message=f"Missing required CSV columns: {', '.join(missing_columns)}.",
                recommendation="Add every required column before running normalization or report generation.",
            )
        )

    for row_number, row in enumerate(reader, start=2):
        total_rows += 1
        normalized = {key.strip().lower(): (value.strip() if isinstance(value, str) else value) for key, value in row.items()}
        normalized = _normalize_source_row(normalized, row_number - 1)
        row_issues = _inspect_csv_row(row_number, normalized, seen_tx_ids)
        issues.extend(row_issues)
        if not any(issue.severity == "error" for issue in row_issues):
            valid_rows += 1

    if total_rows == 0:
        issues.append(
            IngestionIssue(
                severity="error",
                scope="file",
                message="CSV contained no transaction rows.",
                recommendation="Upload a non-empty transaction export or use the demo CSV.",
            )
        )

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    flagged_rows = len({issue.row_number for issue in issues if issue.row_number is not None})
    readiness = "blocked" if error_count else "needs_review" if warning_count else "ready"

    agent_notes = [
        "Run readiness inspection before normalization when a CSV source is new, generated by another agent, or lightly structured.",
        "Treat duplicate transaction IDs, missing timestamps, and non-positive quantities as blockers because downstream audit output becomes unreliable.",
        "Warnings usually mean Skynet can proceed, but confidence and inventory quality may degrade without better price, counter-asset, or event metadata.",
    ]

    return IngestionReadinessReport(
        summary=IngestionReadinessSummary(
            total_rows=total_rows,
            valid_rows=valid_rows,
            flagged_rows=flagged_rows,
            error_count=error_count,
            warning_count=warning_count,
            readiness=readiness,
        ),
        required_columns=REQUIRED_CSV_COLUMNS if not is_etherscan_csv else ETHERSCAN_REQUIRED_COLUMNS,
        present_columns=present_columns,
        missing_columns=missing_columns,
        issues=issues,
        agent_notes=agent_notes,
    )


def _is_etherscan_schema(present_columns: list[str]) -> bool:
    present = set(present_columns)
    return all(column in present for column in ETHERSCAN_REQUIRED_COLUMNS)


def _normalize_source_row(row: dict[str, str | None], index: int) -> dict[str, str | None]:
    if "tx_id" in row:
        return row

    if not _is_etherscan_schema(list(row.keys())):
        return row

    tx_hash = row.get("transaction hash") or ""
    value_in = _optional_float(row.get("value_in(eth)")) or 0.0
    value_out = _optional_float(row.get("value_out(eth)")) or 0.0
    fee_eth = _optional_float(row.get("txnfee(eth)")) or 0.0
    quantity = value_in if value_in > 0 else value_out if value_out > 0 else fee_eth
    direction = "in" if value_in > 0 else "out" if value_out > 0 else "fee_only"
    method = row.get("method") or ""
    tx_fee_usd = _optional_float(row.get("txnfee(usd)")) or 0.0
    historical_price = _optional_float(row.get("historical $price/eth"))
    current_value_usd = _optional_float(row.get("currentvalue @ $2084.3165498016/eth"))
    status = row.get("status") or ""
    err_code = row.get("errcode") or ""

    return {
        "tx_id": tx_hash or f"row-{index}",
        "timestamp": row.get("datetime (utc)") or "",
        "asset": "ETH",
        "quantity": str(quantity),
        "tx_hash": tx_hash or None,
        "network": "ethereum",
        "wallet_provider": "wallet_import",
        "source_app": "etherscan_csv",
        "event_hint": method,
        "price_usd": str(historical_price) if historical_price is not None else None,
        "proceeds_usd": str(current_value_usd) if current_value_usd is not None else None,
        "fee_usd": str(tx_fee_usd),
        "counter_asset": None,
        "counter_quantity": None,
        "description": f"method={method};direction={direction};from={row.get('from')};to={row.get('to')};status={status};err={err_code}",
    }


def classify_transaction(record: TransactionRecord) -> ClassifiedTransaction:
    haystack = " ".join(
        filter(None, [record.event_hint, record.description, record.counter_asset, record.source_app, record.wallet_provider, record.network])
    ).lower()
    event_type = "income"
    confidence = 0.55
    rationale = "Defaulted to income due to missing stronger signal."
    if "transfer" in haystack or "bridge" in haystack:
        event_type, confidence, rationale = "transfer", 0.95, "Detected transfer or bridge language."
    elif "unstake" in haystack or "unstaking" in haystack:
        event_type, confidence, rationale = "unstaking", 0.86, "Detected unstaking or principal return language."
    elif "lp withdraw" in haystack or "remove liquidity" in haystack or "liquidity withdraw" in haystack:
        event_type, confidence, rationale = "lp_withdrawal", 0.88, "Detected LP withdrawal or liquidity removal language."
    elif "lp deposit" in haystack or "add liquidity" in haystack or "provide liquidity" in haystack:
        event_type, confidence, rationale = "lp_deposit", 0.88, "Detected LP deposit or liquidity provisioning language."
    elif "stake" in haystack or "reward" in haystack:
        event_type, confidence, rationale = "staking", 0.88, "Detected staking or reward language."
    elif "airdrop" in haystack:
        event_type, confidence, rationale = "airdrop", 0.9, "Detected airdrop language."
    elif "mine" in haystack:
        event_type, confidence, rationale = "mining", 0.9, "Detected mining language."
    elif "nft" in haystack:
        event_type, confidence, rationale = "nft_sale", 0.82, "Detected NFT language."
    elif "salary" in haystack or "income" in haystack or "payment" in haystack:
        event_type, confidence, rationale = "income", 0.84, "Detected income-like language."
    elif "uniswap" in haystack:
        event_type, confidence, rationale = "swap", 0.92, "Detected Uniswap source metadata, treated as a protocol swap."
    elif record.counter_asset:
        event_type, confidence, rationale = "swap", 0.8, "Counter asset present, treated as asset swap."

    return ClassifiedTransaction(
        transaction=record,
        event_type=event_type,
        confidence=confidence,
        rationale=rationale,
        normalized=_normalize_transaction(record, event_type),
    )


def _available_tax_years_for_jurisdiction(jurisdiction: str) -> list[int]:
    jurisdiction_code = jurisdiction.upper()
    years = sorted(
        {
            int(match.group("year"))
            for path in RULES_DIR.glob(f"{jurisdiction_code.lower()}_*.sample.json")
            if (match := re.match(r"^[a-zA-Z0-9]+_(?P<year>\d{4})\.sample$", path.name))
        },
        reverse=True,
    )
    if years:
        return years
    if _is_open_jurisdiction_code(jurisdiction_code):
        return [DEFAULT_BASELINE_TAX_YEAR]
    return []


def _resolve_tax_year(
    jurisdiction: str,
    requested_tax_year: int | None,
    transactions: list[TransactionRecord],
) -> tuple[int, str]:
    available_years = _available_tax_years_for_jurisdiction(jurisdiction)
    if not available_years:
        raise HTTPException(
            status_code=404,
            detail=f"No tax rules found for jurisdiction {jurisdiction.upper()}.",
        )

    if requested_tax_year is not None and requested_tax_year in available_years:
        return requested_tax_year, f"Used requested tax year {requested_tax_year}."

    transaction_years = sorted({tx.timestamp.year for tx in transactions})
    for year in reversed(transaction_years):
        if year in available_years:
            return year, (
                f"Requested tax year {requested_tax_year} was unavailable. "
                f"Used {year} based on CSV transaction dates."
            )

    resolved_year = available_years[0]
    if requested_tax_year is None:
        return resolved_year, (
            f"No tax year was selected. Used {resolved_year}, the available ruleset version, "
            "while keeping tax calculations across the full CSV date range."
        )
    return resolved_year, (
        f"Requested tax year {requested_tax_year} was unavailable. Used {resolved_year}, "
        "the available ruleset version, while keeping tax calculations across the full CSV date range."
    )


def generate_report(request: GenerateReportRequest) -> TaxReport:
    period_start = min(request.transactions, key=lambda tx: tx.timestamp).timestamp
    period_end = max(request.transactions, key=lambda tx: tx.timestamp).timestamp
    resolved_tax_year, tax_year_note = _resolve_tax_year(request.jurisdiction, request.tax_year, request.transactions)
    rule_set = load_rule_set(request.jurisdiction, resolved_tax_year)
    rule_by_event = {rule.eventType: rule for rule in rule_set.eventRules}
    inventory: dict[str, deque[Lot]] = defaultdict(deque)
    line_items: list[ReportLineItem] = []
    assumptions = [
        "FIFO is used for disposal cost basis in the MVP.",
        "USD values are taken from the transaction CSV when provided; otherwise quantity * price_usd is used.",
        "Swap normalization tracks disposed and acquired sides separately when counter asset data is present.",
        "Liquidity add/remove flows are approximated using single-sided asset records in the MVP unless both legs are supplied.",
        "Fallback-derived results are estimates and should be reviewed by a tax professional.",
        (
            "Tax period defaults to the CSV transaction span "
            f"({period_start.date().isoformat()} to {period_end.date().isoformat()}) "
            "when the requested tax year is missing or unavailable."
        ),
    ]

    for transaction in sorted(request.transactions, key=lambda row: row.timestamp):
        classified = classify_transaction(transaction)
        rule = rule_by_event.get(classified.event_type)
        fallback_applied = rule is None
        if fallback_applied:
            rule = _fallback_rule(classified.event_type, rule_set.fallbackPolicy.mode)

        taxable_amount, cost_basis, gain_or_loss, explanation, formula_inputs, formula_outputs = _apply_rule(classified, rule, inventory)
        line_items.append(
            ReportLineItem(
                tx_id=transaction.tx_id,
                asset=transaction.asset,
                event_type=classified.event_type,
                tax_treatment=rule.taxTreatment,
                taxable_amount_usd=round(taxable_amount, 2),
                cost_basis_usd=round(cost_basis, 2),
                gain_or_loss_usd=round(gain_or_loss, 2),
                confidence=min(rule.confidence, classified.confidence) if fallback_applied else round((rule.confidence + classified.confidence) / 2, 2),
                fallback_applied=fallback_applied,
                explanation=f"{classified.rationale} {explanation}",
                rule_version=rule_set.version,
                calculation_method=rule.calculationMethod,
                disposed_asset=classified.normalized.disposed_asset,
                disposed_quantity=classified.normalized.disposed_quantity,
                acquired_asset=classified.normalized.acquired_asset,
                acquired_quantity=classified.normalized.acquired_quantity,
                rule_notes=rule.notes,
                citations=rule.citations,
                source_tx_hash=transaction.tx_hash,
                source_network=transaction.network,
                source_app=transaction.source_app,
                source_wallet_provider=transaction.wallet_provider,
                rule_id=f"{rule_set.jurisdiction}:{rule_set.taxYear}:{rule.eventType}:{rule.calculationMethod}",
                formula_inputs=formula_inputs,
                formula_outputs=formula_outputs,
            )
        )

    summary = ReportSummary(
        jurisdiction=rule_set.jurisdiction,
        tax_year=rule_set.taxYear,
        requested_tax_year=request.tax_year,
        period_start=period_start,
        period_end=period_end,
        period_label=f"{period_start.date().isoformat()} to {period_end.date().isoformat()}",
        tax_year_selection_note=tax_year_note,
        total_taxable_income_usd=round(sum(item.taxable_amount_usd for item in line_items if item.tax_treatment == "taxable_income"), 2),
        total_capital_gains_usd=round(sum(max(item.gain_or_loss_usd, 0) for item in line_items if item.tax_treatment in {"capital_gains", "mixed"}), 2),
        total_capital_losses_usd=round(sum(min(item.gain_or_loss_usd, 0) for item in line_items if item.tax_treatment in {"capital_gains", "mixed"}), 2),
        fallback_count=sum(1 for item in line_items if item.fallback_applied),
        partner_signals=_collect_partner_signals(request.transactions),
    )
    return TaxReport(summary=summary, line_items=line_items, assumptions=assumptions)


def generate_multi_jurisdiction_report(request: MultiJurisdictionReportRequest) -> MultiJurisdictionReport:
    unique_jurisdictions = list(dict.fromkeys(code.upper() for code in request.jurisdictions if code.strip()))
    if not unique_jurisdictions:
        raise HTTPException(status_code=400, detail="At least one jurisdiction code is required.")

    labels = {item.code: item.label for item in list_supported_jurisdictions()}
    reports: list[JurisdictionReportResult] = []
    comparison: list[MultiJurisdictionComparisonRow] = []

    for jurisdiction in unique_jurisdictions:
        report = generate_report(
            GenerateReportRequest(
                jurisdiction=jurisdiction,
                tax_year=request.tax_year,
                transactions=request.transactions,
            )
        )
        label = labels.get(jurisdiction, jurisdiction)
        reports.append(JurisdictionReportResult(jurisdiction=jurisdiction, label=label, report=report))
        comparison.append(
            MultiJurisdictionComparisonRow(
                jurisdiction=jurisdiction,
                label=label,
                taxable_income_usd=report.summary.total_taxable_income_usd,
                capital_gains_usd=report.summary.total_capital_gains_usd,
                capital_losses_usd=report.summary.total_capital_losses_usd,
                fallback_count=report.summary.fallback_count,
            )
        )

    return MultiJurisdictionReport(
        tax_year=request.tax_year or DEFAULT_BASELINE_TAX_YEAR,
        jurisdictions=unique_jurisdictions,
        reports=reports,
        comparison=comparison,
    )


def preview_normalization(request: GenerateReportRequest) -> list[NormalizationPreviewItem]:
    preview: list[NormalizationPreviewItem] = []
    for transaction in sorted(request.transactions, key=lambda row: row.timestamp):
        classified = classify_transaction(transaction)
        preview.append(
            NormalizationPreviewItem(
                tx_id=transaction.tx_id,
                event_type=classified.event_type,
                confidence=classified.confidence,
                rationale=classified.rationale,
                normalized=classified.normalized,
            )
        )
    return preview


def build_autonomy_plan(content: bytes, jurisdiction: str, tax_year: int | None) -> AutonomyPlan:
    readiness = inspect_csv_readiness(content)
    blocked_rows = sum(1 for issue in readiness.issues if issue.severity == "error" and issue.scope == "row")
    warning_rows = len({issue.row_number for issue in readiness.issues if issue.severity == "warning" and issue.row_number is not None})

    rationale: list[str] = []
    next_steps = [
        AutonomyPlanStep(
            id="inspect",
            label="Inspect CSV readiness",
            status="blocked" if readiness.summary.readiness == "blocked" else "review" if readiness.summary.warning_count else "ready",
            detail=f"{readiness.summary.error_count} blocking issues and {readiness.summary.warning_count} warnings detected in the uploaded CSV.",
            endpoint="/ingestion/readiness-from-csv",
        )
    ]

    if readiness.summary.readiness == "blocked":
        rationale.append("CSV structure or row quality issues block safe autonomous analysis.")
        next_steps.extend(
            [
                AutonomyPlanStep(
                    id="repair",
                    label="Repair CSV contract",
                    status="blocked",
                    detail="Fix missing columns, duplicate IDs, invalid timestamps, or non-positive quantities before any downstream step.",
                ),
                AutonomyPlanStep(
                    id="preview",
                    label="Preview normalization",
                    status="blocked",
                    detail="Normalization is intentionally deferred until the CSV contract is repaired.",
                    endpoint="/normalize/preview-from-csv",
                ),
                AutonomyPlanStep(
                    id="analyze",
                    label="Generate report",
                    status="blocked",
                    detail="Tax calculations stay blocked while readiness errors remain unresolved.",
                    endpoint="/reports/generate-from-csv",
                ),
            ]
        )
        return AutonomyPlan(
            jurisdiction=jurisdiction,
            tax_year=tax_year or DEFAULT_BASELINE_TAX_YEAR,
            autonomy_status="blocked",
            recommended_action="repair_csv",
            summary="Autonomous execution is blocked until the CSV contract is repaired.",
            rationale=rationale,
            stats=AutonomyPlanStats(
                total_transactions=readiness.summary.total_rows,
                blocked_rows=blocked_rows,
                warning_rows=warning_rows,
                low_confidence_count=0,
                predicted_fallback_count=0,
            ),
            next_steps=next_steps,
            handoff_notes=[
                "Use the readiness issue list as the only source of truth for file repairs.",
                "Do not generate a report from a blocked CSV because FIFO ordering and audit references may be wrong.",
            ],
        )

    transactions = parse_transactions_csv(content)
    request = GenerateReportRequest(jurisdiction=jurisdiction.upper(), tax_year=tax_year, transactions=transactions)
    preview = preview_normalization(request)
    resolved_tax_year, _ = _resolve_tax_year(request.jurisdiction, request.tax_year, transactions)
    rule_set = load_rule_set(request.jurisdiction, resolved_tax_year)
    supported_events = {rule.eventType for rule in rule_set.eventRules}

    low_confidence_count = sum(1 for item in preview if item.confidence < 0.75)
    predicted_fallback_count = sum(1 for item in preview if item.event_type not in supported_events)

    if low_confidence_count:
        rationale.append(f"{low_confidence_count} transactions have low-confidence classification results.")
    if predicted_fallback_count:
        rationale.append(
            f"{predicted_fallback_count} transactions are likely to use fallback tax treatment in "
            f"{jurisdiction.upper()} {resolved_tax_year}."
        )
    if readiness.summary.warning_count:
        rationale.append("The CSV is usable, but warning-level data quality gaps still weaken audit confidence.")
    if not rationale:
        rationale.append("The CSV passed readiness and the previewed event mix is suitable for autonomous report generation.")

    review_needed = bool(readiness.summary.warning_count or low_confidence_count or predicted_fallback_count)
    next_steps.extend(
        [
            AutonomyPlanStep(
                id="preview",
                label="Preview normalization",
                status="review" if review_needed else "ready",
                detail=(
                    "Review classification confidence, detected flows, and swap legs before analysis."
                    if review_needed
                    else "Preview confidence and event coverage are strong enough to continue automatically."
                ),
                endpoint="/normalize/preview-from-csv",
            ),
            AutonomyPlanStep(
                id="analyze",
                label="Generate report",
                status="review" if review_needed else "ready",
                detail=(
                    "Generate the report after reviewing flagged rows, low-confidence events, or fallback-prone transactions."
                    if review_needed
                    else "Proceed to report generation and persist an artifact bundle for evidence."
                ),
                endpoint="/reports/generate-from-csv",
            ),
            AutonomyPlanStep(
                id="export",
                label="Save bundle",
                status="review" if review_needed else "ready",
                detail="Export or save the run bundle so downstream reviewers and agents inherit the same evidence package.",
                endpoint="/artifacts/save-from-csv",
            ),
        ]
    )

    return AutonomyPlan(
        jurisdiction=jurisdiction,
        tax_year=resolved_tax_year,
        autonomy_status="review" if review_needed else "ready",
        recommended_action="review_predictions" if review_needed else "generate_report",
        summary=(
            "Autonomous execution can continue, but the run should pause for a quick review checkpoint."
            if review_needed
            else "Autonomous execution is clear to proceed through report generation and evidence capture."
        ),
        rationale=rationale,
        stats=AutonomyPlanStats(
            total_transactions=len(transactions),
            blocked_rows=blocked_rows,
            warning_rows=warning_rows,
            low_confidence_count=low_confidence_count,
            predicted_fallback_count=predicted_fallback_count,
        ),
        next_steps=next_steps,
        handoff_notes=[
            "Use normalization preview as the final gate before any automated filing-style explanation.",
            "When fallback risk is non-zero, cite the affected line items and their rule IDs in any agent handoff.",
            "Save a bundle after successful analysis so repeat runs can compare against a fixed artifact set.",
        ],
    )


def get_explanation_guide() -> ExplanationGuide:
    return ExplanationGuide(
        product_name="Skynet",
        version="0.1.0",
        purpose="Jurisdiction-aware crypto tax estimation with explainable normalization, rule application, and exportable audit artifacts.",
        workflows=[
            WorkflowStep(
                id="inspect",
                label="Inspect CSV readiness",
                description="Run a lightweight readiness check that validates CSV structure and flags risky rows before normalization or tax calculations begin.",
                agent_hint="Use readiness inspection as the first autonomous gate; blocked files should not continue into report generation until the data contract is repaired.",
            ),
            WorkflowStep(
                id="ingest",
                label="Ingest transactions",
                description="Upload CSV data with wallet, protocol, and pricing hints so Skynet can normalize each row into a canonical tax-event flow.",
                agent_hint="Validate required CSV columns first and preserve source metadata because partner signals and explanations depend on it.",
            ),
            WorkflowStep(
                id="preview",
                label="Preview normalization",
                description="Inspect Skynet's event detection before tax calculations to confirm swap, transfer, staking, and LP interpretations.",
                agent_hint="Use the normalization preview as the first checkpoint; if confidence is low or the flow is wrong, stop and ask for better source data.",
            ),
            WorkflowStep(
                id="analyze",
                label="Generate report",
                description="Apply jurisdiction rules, FIFO inventory logic, and fallback policy to create an explainable tax summary with line items.",
                agent_hint="Treat fallback flags as escalation points and surface them prominently in downstream summaries or agent handoffs.",
            ),
            WorkflowStep(
                id="export",
                label="Export or save evidence",
                description="Download Markdown or HTML reports, or persist a full artifact bundle for demo evidence and later review.",
                agent_hint="Prefer saving a bundle when an autonomous agent finishes a run so the report, preview, and collaboration trail stay aligned.",
            ),
        ],
        ui_elements=[
            ExplanationItem(
                id="csv-readiness-panel",
                label="CSV Readiness panel",
                audience=["human", "agent"],
                summary="Preflight inspection of required columns, row-level blockers, and warning counts before normalization starts.",
                operational_note="This is the safest first stop for autonomous workflows because it separates file-shape problems from tax logic problems.",
            ),
            ExplanationItem(
                id="generate-report-form",
                label="Generate Report form",
                audience=["human", "agent"],
                summary="Primary control surface for jurisdiction, tax year, and CSV upload.",
                operational_note="This is the minimum input required for all browser-based flows.",
            ),
            ExplanationItem(
                id="normalization-preview",
                label="Normalization Preview",
                audience=["human", "agent"],
                summary="Shows detected event type, confidence, normalized asset flow, and the rationale used to classify each transaction.",
                operational_note="Use this section to catch ingestion or classification problems before the rule engine runs.",
            ),
            ExplanationItem(
                id="summary-panel",
                label="Summary panel",
                audience=["human", "agent"],
                summary="Aggregates taxable income, capital gains, capital losses, fallback event count, and partner metadata signals.",
                operational_note="This is the fastest high-level signal for judges, operators, and automation monitors.",
            ),
            ExplanationItem(
                id="artifact-history",
                label="Artifact History",
                audience=["human", "agent"],
                summary="Lists saved bundles so prior runs can be revisited without reprocessing the same file.",
                operational_note="This supports repeatability and reduces duplicated work in autonomous loops.",
            ),
        ],
        report_elements=[
            ExplanationItem(
                id="line-item",
                label="Line item",
                audience=["human", "agent"],
                summary="A single transaction outcome with rule, formula, gain/loss, confidence, and source metadata.",
                operational_note="Agents should cite line items rather than summary totals when explaining a specific taxable event.",
            ),
            ExplanationItem(
                id="fallback-flag",
                label="Fallback flag",
                audience=["human", "agent"],
                summary="Marks events where jurisdiction-specific crypto treatment was unavailable and a safer general rule was used instead.",
                operational_note="Fallbacks should trigger review because they are estimates, not jurisdiction-specific certainty.",
            ),
            ExplanationItem(
                id="citations",
                label="Citations",
                audience=["human", "agent"],
                summary="Links to authority material attached to a rule so the estimate can be traced to a source.",
                operational_note="When citations exist, include them in exported evidence or agent summaries to improve trust.",
            ),
            ExplanationItem(
                id="formula-audit",
                label="Formula audit",
                audience=["human", "agent"],
                summary="Structured inputs and outputs that show how Skynet derived a taxable amount, basis, or gain/loss result.",
                operational_note="This is the stable machine-readable interface for agent verification and regression testing.",
            ),
        ],
        autonomous_usage_notes=[
            "Run CSV readiness inspection before normalization when the source file comes from a new exchange, wallet export, or agent-generated transform.",
            "Run normalization preview before report generation when source data is new or untrusted.",
            "Escalate low-confidence rows or fallback-derived rows instead of silently accepting them.",
            "Save artifact bundles for autonomous runs so state is preserved outside the live UI session.",
            "Reference rule_id, citations, and formula audit details in any machine-generated explanation.",
        ],
        scalability_notes=[
            "Readiness inspection is exposed as its own contract so ingestion-quality checks can scale independently from heavier tax calculation workloads.",
            "The guide is returned as structured JSON so future clients and agents can consume the same contract without parsing UI text.",
            "Separating UI element metadata from tax calculations keeps product explanation changes independent from the core rule engine.",
            "Artifact history supports incremental operator workflows and reduces redundant recomputation across repeated sessions.",
        ],
    )


def export_report_markdown(report: TaxReport) -> MarkdownExport:
    summary = report.summary
    lines = [
        "# Skynet Tax Report",
        "",
        f"- Jurisdiction: {summary.jurisdiction}",
        f"- Tax year: {summary.tax_year}",
        f"- Taxable income: ${summary.total_taxable_income_usd:,.2f}",
        f"- Capital gains: ${summary.total_capital_gains_usd:,.2f}",
        f"- Capital losses: ${summary.total_capital_losses_usd:,.2f}",
        f"- Fallback events: {summary.fallback_count}",
        "",
        "## Partner Signals",
        "",
    ]
    if summary.partner_signals:
        lines.extend([f"- {name}: {count}" for name, count in sorted(summary.partner_signals.items())])
    else:
        lines.append("- No partner-specific metadata detected in this report.")
    lines.extend([
        "",
        "## Assumptions",
        "",
    ])
    lines.extend([f"- {assumption}" for assumption in report.assumptions])
    lines.extend(["", "## Line Items", ""])

    for item in report.line_items:
        flow = []
        if item.disposed_asset and item.disposed_quantity:
            flow.append(f"disposed {item.disposed_quantity:g} {item.disposed_asset}")
        if item.acquired_asset and item.acquired_quantity:
            flow.append(f"acquired {item.acquired_quantity:g} {item.acquired_asset}")
        flow_text = "; ".join(flow) if flow else "no asset flow captured"
        lines.extend(
            [
                f"### {item.tx_id}",
                f"- Event: {item.event_type}",
                f"- Treatment: {item.tax_treatment}",
                f"- Flow: {flow_text}",
                f"- Taxable amount: ${item.taxable_amount_usd:,.2f}",
                f"- Cost basis: ${item.cost_basis_usd:,.2f}",
                f"- Gain/loss: ${item.gain_or_loss_usd:,.2f}",
                f"- Confidence: {item.confidence:.0%}",
                f"- Fallback applied: {'yes' if item.fallback_applied else 'no'}",
                f"- Rule version: {item.rule_version}",
                f"- Rule id: {item.rule_id}",
                f"- Calculation method: {item.calculation_method}",
                f"- Explanation: {item.explanation}",
            ]
        )
        if item.formula_inputs:
            lines.append(f"- Formula inputs: {json.dumps(item.formula_inputs, sort_keys=True)}")
        if item.formula_outputs:
            lines.append(f"- Formula outputs: {json.dumps(item.formula_outputs, sort_keys=True)}")
        if item.rule_notes:
            lines.append(f"- Rule notes: {item.rule_notes}")
        if item.citations:
            lines.append("- Citations:")
            lines.extend([f"  - {citation.authority}: {citation.title} ({citation.url})" for citation in item.citations])
        lines.append("")

    filename = f"skynet-report-{summary.jurisdiction.lower()}-{summary.tax_year}.md"
    return MarkdownExport(filename=filename, content="\n".join(lines).strip() + "\n")


def export_report_html(report: TaxReport) -> HtmlExport:
    rows = []
    for item in report.line_items:
        citations = "".join(
            f'<li><a href="{_escape_html(citation.url)}" target="_blank" rel="noreferrer">{_escape_html(citation.authority)}: {_escape_html(citation.title)}</a></li>'
            for citation in item.citations
        ) or "<li>No citations</li>"
        rows.append(
            f"""
            <tr>
              <td>{_escape_html(item.tx_id)}</td>
              <td>{_escape_html(item.event_type)}</td>
              <td>{_escape_html(item.tax_treatment)}</td>
              <td>{item.taxable_amount_usd:.2f}</td>
              <td>{item.gain_or_loss_usd:.2f}</td>
              <td>{_escape_html(item.rule_id)}</td>
              <td><pre>{_escape_html(json.dumps(item.formula_inputs, indent=2, sort_keys=True))}</pre></td>
              <td><pre>{_escape_html(json.dumps(item.formula_outputs, indent=2, sort_keys=True))}</pre></td>
              <td><ul>{citations}</ul></td>
            </tr>
            """
        )

    summary = report.summary
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Skynet Report {summary.jurisdiction} {summary.tax_year}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #111827; }}
    h1, h2 {{ margin-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 10px; vertical-align: top; text-align: left; }}
    th {{ background: #f3f4f6; }}
    pre {{ margin: 0; white-space: pre-wrap; }}
    ul {{ margin: 0; padding-left: 18px; }}
  </style>
</head>
<body>
  <h1>Skynet Tax Report</h1>
  <p>{summary.jurisdiction} {summary.tax_year}</p>
  <h2>Summary</h2>
  <ul>
    <li>Taxable income: ${summary.total_taxable_income_usd:,.2f}</li>
    <li>Capital gains: ${summary.total_capital_gains_usd:,.2f}</li>
    <li>Capital losses: ${summary.total_capital_losses_usd:,.2f}</li>
    <li>Fallback events: {summary.fallback_count}</li>
  </ul>
  <h2>Line Items</h2>
  <table>
    <thead>
      <tr>
        <th>Tx</th>
        <th>Event</th>
        <th>Treatment</th>
        <th>Taxable</th>
        <th>Gain/Loss</th>
        <th>Rule ID</th>
        <th>Formula Inputs</th>
        <th>Formula Outputs</th>
        <th>Citations</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""
    filename = f"skynet-report-{summary.jurisdiction.lower()}-{summary.tax_year}.html"
    return HtmlExport(filename=filename, content=html)


def save_artifact_bundle(request: GenerateReportRequest) -> ArtifactBundle:
    report = generate_report(request)
    preview = preview_normalization(request)
    markdown_export = export_report_markdown(report)
    html_export = export_report_html(report)

    bundle_id = _bundle_id(request.jurisdiction, request.tax_year)
    bundle_dir = ARTIFACTS_DIR / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    report_json_path = bundle_dir / "report.json"
    report_markdown_path = bundle_dir / markdown_export.filename
    report_html_path = bundle_dir / html_export.filename
    preview_path = bundle_dir / "normalization-preview.json"
    collaboration_log_path = bundle_dir / "collaboration-log.md"

    report_json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    report_markdown_path.write_text(markdown_export.content, encoding="utf-8")
    report_html_path.write_text(html_export.content, encoding="utf-8")
    preview_path.write_text(json.dumps([item.model_dump(mode="json") for item in preview], indent=2), encoding="utf-8")
    if COLLABORATION_LOG_PATH.exists():
        collaboration_log_path.write_text(COLLABORATION_LOG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        collaboration_log_path.write_text("# Collaboration Log\n\nNo collaboration log was available.\n", encoding="utf-8")

    return ArtifactBundle(
        bundle_id=bundle_id,
        directory=str(bundle_dir),
        report_json=str(report_json_path),
        report_markdown=str(report_markdown_path),
        report_html=str(report_html_path),
        normalization_preview=str(preview_path),
        collaboration_log=str(collaboration_log_path),
    )


def list_artifact_bundles() -> list[ArtifactBundleSummary]:
    if not ARTIFACTS_DIR.exists():
        return []

    bundles: list[ArtifactBundleSummary] = []
    for bundle_dir in sorted([path for path in ARTIFACTS_DIR.iterdir() if path.is_dir()], reverse=True):
        report_json_path = bundle_dir / "report.json"
        preview_path = bundle_dir / "normalization-preview.json"
        markdown_candidates = sorted(bundle_dir.glob("skynet-report-*.md"))
        report_markdown_path = markdown_candidates[0] if markdown_candidates else bundle_dir / "report.md"
        html_candidates = sorted(bundle_dir.glob("skynet-report-*.html"))
        report_html_path = html_candidates[0] if html_candidates else bundle_dir / "report.html"
        bundles.append(
            ArtifactBundleSummary(
                bundle_id=bundle_dir.name,
                directory=str(bundle_dir),
                report_json=str(report_json_path),
                report_markdown=str(report_markdown_path),
                report_html=str(report_html_path),
                normalization_preview=str(preview_path),
                collaboration_log=str(bundle_dir / "collaboration-log.md"),
            )
        )
    return bundles


def _apply_rule(
    classified: ClassifiedTransaction,
    rule: EventRule,
    inventory: dict[str, deque[Lot]],
) -> tuple[float, float, float, str]:
    record = classified.transaction
    normalized = classified.normalized
    gross_value = record.gross_value_usd

    if classified.event_type in {"income", "staking", "airdrop", "mining"}:
        quantity = normalized.acquired_quantity or record.quantity
        unit_cost = gross_value / quantity if quantity else 0
        inventory[normalized.acquired_asset or record.asset].append(Lot(quantity=quantity, unit_cost_usd=unit_cost))
        return (
            gross_value,
            gross_value,
            0.0,
            "Recorded receipt value as taxable basis and added inventory lot.",
            {"gross_value_usd": gross_value, "quantity": quantity, "unit_cost_usd": unit_cost},
            {"taxable_amount_usd": gross_value, "cost_basis_usd": gross_value, "gain_or_loss_usd": 0.0},
        )

    if classified.event_type in {"transfer", "unstaking", "lp_deposit"}:
        if classified.event_type == "unstaking" and normalized.acquired_asset:
            inventory[normalized.acquired_asset].append(Lot(quantity=normalized.acquired_quantity, unit_cost_usd=0))
            return (
                0.0,
                0.0,
                0.0,
                "Modeled unstaking as non-taxable principal return and added the returned asset to inventory with placeholder basis.",
                {"returned_quantity": normalized.acquired_quantity},
                {"taxable_amount_usd": 0.0, "cost_basis_usd": 0.0, "gain_or_loss_usd": 0.0},
            )
        if classified.event_type == "lp_deposit":
            acquired_asset = normalized.acquired_asset or "LP_POSITION"
            acquired_quantity = normalized.acquired_quantity or record.quantity
            unit_cost = gross_value / acquired_quantity if acquired_quantity else 0
            inventory[acquired_asset].append(Lot(quantity=acquired_quantity, unit_cost_usd=unit_cost))
            return (
                0.0,
                gross_value,
                0.0,
                "Modeled LP deposit as non-taxable position entry and added the LP position token to inventory.",
                {"gross_value_usd": gross_value, "acquired_quantity": acquired_quantity, "unit_cost_usd": unit_cost},
                {"taxable_amount_usd": 0.0, "cost_basis_usd": gross_value, "gain_or_loss_usd": 0.0},
            )
        return (
            0.0,
            0.0,
            0.0,
            "Treated as non-taxable transfer.",
            {"disposed_quantity": normalized.disposed_quantity},
            {"taxable_amount_usd": 0.0, "cost_basis_usd": 0.0, "gain_or_loss_usd": 0.0},
        )

    if classified.event_type in {"swap", "nft_sale", "lp_withdrawal"}:
        disposed_asset = normalized.disposed_asset or record.asset
        disposed_quantity = normalized.disposed_quantity or record.quantity
        cost_basis = _consume_fifo(inventory[disposed_asset], disposed_quantity)
        proceeds = gross_value - record.fee_usd
        gain_or_loss = proceeds - cost_basis
        if classified.event_type in {"swap", "lp_withdrawal"} and normalized.acquired_asset and normalized.acquired_quantity > 0:
            acquired_unit_cost = proceeds / normalized.acquired_quantity
            inventory[normalized.acquired_asset].append(Lot(quantity=normalized.acquired_quantity, unit_cost_usd=acquired_unit_cost))
        if classified.event_type == "lp_withdrawal":
            return (
                proceeds,
                cost_basis,
                gain_or_loss,
                "Modeled LP withdrawal as a position exit using FIFO for the disposed side and normalized return legs when present.",
                {"proceeds_usd": proceeds, "cost_basis_usd": cost_basis, "disposed_quantity": disposed_quantity},
                {"taxable_amount_usd": proceeds, "cost_basis_usd": cost_basis, "gain_or_loss_usd": gain_or_loss},
            )
        return (
            proceeds,
            cost_basis,
            gain_or_loss,
            "Disposed inventory using FIFO and normalized swap legs for clearer audit output.",
            {"proceeds_usd": proceeds, "cost_basis_usd": cost_basis, "disposed_quantity": disposed_quantity},
            {"taxable_amount_usd": proceeds, "cost_basis_usd": cost_basis, "gain_or_loss_usd": gain_or_loss},
        )

    return (
        gross_value,
        0.0,
        0.0,
        "Unsupported event type fell back to generic taxable treatment.",
        {"gross_value_usd": gross_value},
        {"taxable_amount_usd": gross_value, "cost_basis_usd": 0.0, "gain_or_loss_usd": 0.0},
    )


def _consume_fifo(lots: deque[Lot], quantity_needed: float) -> float:
    remaining = quantity_needed
    total_cost = 0.0
    while remaining > 0 and lots:
        lot = lots[0]
        taken = min(lot.quantity, remaining)
        total_cost += taken * lot.unit_cost_usd
        lot.quantity -= taken
        remaining -= taken
        if lot.quantity <= 1e-9:
            lots.popleft()
    if remaining > 1e-9:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient inventory to dispose of {quantity_needed}. Missing quantity: {round(remaining, 8)}",
        )
    return total_cost


def _fallback_rule(event_type: str, fallback_mode: str) -> EventRule:
    if fallback_mode == "manual_review_required":
        raise HTTPException(status_code=422, detail=f"Manual review required for unsupported event type: {event_type}")
    treatment: TaxTreatment = (
        "non_taxable"
        if event_type in {"transfer", "unstaking", "lp_deposit"}
        else "capital_gains"
        if event_type in {"swap", "nft_sale", "lp_withdrawal"}
        else "taxable_income"
    )
    method = "fifo_capital_gain" if treatment == "capital_gains" else "fair_market_value_at_receipt"
    if treatment == "non_taxable":
        method = "non_taxable_transfer"
    return EventRule(
        eventType=event_type,
        taxTreatment=treatment,
        calculationMethod=method,
        confidence=0.55,
        notes="Derived from fallback policy because no jurisdiction-specific crypto rule was present.",
    )


def _optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _inspect_csv_row(row_number: int, row: dict[str, str | None], seen_tx_ids: set[str]) -> list[IngestionIssue]:
    issues: list[IngestionIssue] = []
    tx_id = (row.get("tx_id") or f"row-{row_number}").strip()
    timestamp = (row.get("timestamp") or "").strip()
    asset = (row.get("asset") or "").strip()
    quantity = (row.get("quantity") or "").strip()
    event_hint = (row.get("event_hint") or "").strip().lower()
    counter_asset = (row.get("counter_asset") or "").strip()
    counter_quantity = (row.get("counter_quantity") or "").strip()
    price_usd = (row.get("price_usd") or "").strip()
    proceeds_usd = (row.get("proceeds_usd") or "").strip()

    if not tx_id:
        issues.append(
            IngestionIssue(
                severity="error",
                scope="row",
                row_number=row_number,
                message="Row is missing a transaction ID.",
                recommendation="Provide a stable tx_id so artifact history and audit trails stay consistent.",
            )
        )
    elif tx_id in seen_tx_ids:
        issues.append(
            IngestionIssue(
                severity="error",
                scope="row",
                row_number=row_number,
                tx_id=tx_id,
                message="Duplicate transaction ID detected.",
                recommendation="Deduplicate the file or assign unique tx_id values before analysis.",
            )
        )
    else:
        seen_tx_ids.add(tx_id)

    if not timestamp:
        issues.append(
            IngestionIssue(
                severity="error",
                scope="row",
                row_number=row_number,
                tx_id=tx_id,
                message="Missing timestamp.",
                recommendation="Add an ISO-8601 timestamp so FIFO ordering remains correct.",
            )
        )
    else:
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            issues.append(
                IngestionIssue(
                    severity="error",
                    scope="row",
                    row_number=row_number,
                    tx_id=tx_id,
                    message="Timestamp is not valid ISO-8601.",
                    recommendation="Re-export or normalize timestamps to a machine-readable ISO-8601 format.",
                )
            )

    if not asset:
        issues.append(
            IngestionIssue(
                severity="error",
                scope="row",
                row_number=row_number,
                tx_id=tx_id,
                message="Missing asset symbol.",
                recommendation="Populate the asset column so normalization can determine the disposed or acquired asset.",
            )
        )

    if not quantity:
        issues.append(
            IngestionIssue(
                severity="error",
                scope="row",
                row_number=row_number,
                tx_id=tx_id,
                message="Missing quantity.",
                recommendation="Populate quantity with a positive numeric amount.",
            )
        )
    else:
        try:
            if float(quantity) <= 0:
                raise ValueError
        except ValueError:
            issues.append(
                IngestionIssue(
                    severity="error",
                    scope="row",
                    row_number=row_number,
                    tx_id=tx_id,
                    message="Quantity must be a positive number.",
                    recommendation="Correct the quantity value before continuing.",
                )
            )

    if counter_asset and not counter_quantity:
        issues.append(
            IngestionIssue(
                severity="warning",
                scope="row",
                row_number=row_number,
                tx_id=tx_id,
                message="Counter asset is present without counter quantity.",
                recommendation="Add counter_quantity to preserve the acquisition leg for swaps or LP flows.",
            )
        )

    if event_hint in {"swap", "lp deposit", "lp withdrawal"} and not counter_asset:
        issues.append(
            IngestionIssue(
                severity="warning",
                scope="row",
                row_number=row_number,
                tx_id=tx_id,
                message="Event hint suggests a two-sided flow but counter asset is missing.",
                recommendation="Populate counter_asset and counter_quantity for clearer normalization and inventory tracking.",
            )
        )

    if not price_usd and not proceeds_usd:
        issues.append(
            IngestionIssue(
                severity="warning",
                scope="row",
                row_number=row_number,
                tx_id=tx_id,
                message="No USD valuation metadata found.",
                recommendation="Add price_usd or proceeds_usd so taxable value calculations are not forced to zero.",
            )
        )

    if not event_hint:
        issues.append(
            IngestionIssue(
                severity="info",
                scope="row",
                row_number=row_number,
                tx_id=tx_id,
                message="Event hint is blank.",
                recommendation="Skynet can infer the event, but adding an event hint usually improves confidence.",
            )
        )

    return issues


def _bundle_id(jurisdiction: str, tax_year: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", jurisdiction.lower()).strip("-") or "report"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{slug}-{tax_year}-{stamp}"


def publish_current_work() -> PublishedBuild:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    publish_id = f"skynet-publish-{stamp}"
    publish_dir = PUBLISHED_DIR / publish_id
    publish_dir.mkdir(parents=True, exist_ok=True)

    summary_path = publish_dir / "PUBLISHED_SUMMARY.md"
    docs_to_include = [
        Path("README.md"),
        Path("ARCHITECTURE.md"),
        Path("DEMO_SCRIPT.md"),
        Path("docs/api.md"),
        Path("docs/collaboration-log.md"),
    ]
    copied_docs: list[str] = []
    copied_artifacts: list[str] = []

    for doc in docs_to_include:
        source = Path(__file__).resolve().parent.parent / doc
        if source.exists():
            destination = publish_dir / doc.name
            destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            copied_docs.append(str(destination))

    if ARTIFACTS_DIR.exists():
        latest_bundle = next((path for path in sorted(ARTIFACTS_DIR.iterdir(), reverse=True) if path.is_dir()), None)
        if latest_bundle:
            for asset in ["report.json", "normalization-preview.json", "collaboration-log.md"]:
                source_asset = latest_bundle / asset
                if source_asset.exists():
                    destination = publish_dir / f"latest-{asset}"
                    destination.write_text(source_asset.read_text(encoding="utf-8"), encoding="utf-8")
                    copied_artifacts.append(str(destination))

    summary_lines = [
        "# Published Build Snapshot",
        "",
        f"- Publish ID: `{publish_id}`",
        f"- Published at (UTC): `{datetime.now(UTC).isoformat()}`",
        "- Team mode: solo team (self-custody integration not required for this publication snapshot)",
        "",
        "## Included documentation",
    ]
    if copied_docs:
        summary_lines.extend([f"- `{path}`" for path in copied_docs])
    else:
        summary_lines.append("- No documentation files were available to include.")

    summary_lines.append("")
    summary_lines.append("## Included artifacts")
    if copied_artifacts:
        summary_lines.extend([f"- `{path}`" for path in copied_artifacts])
    else:
        summary_lines.append("- No prior artifact bundle was available.")

    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    return PublishedBuild(
        publish_id=publish_id,
        directory=str(publish_dir),
        summary_markdown=str(summary_path),
        included_artifacts=copied_artifacts,
        included_docs=copied_docs,
    )


def _normalize_transaction(record: TransactionRecord, event_type: str) -> NormalizedTransaction:
    notes: list[str] = []
    disposed_asset: str | None = None
    disposed_quantity = 0.0
    acquired_asset: str | None = None
    acquired_quantity = 0.0

    if event_type in {"income", "staking", "airdrop", "mining"}:
        acquired_asset = record.asset
        acquired_quantity = record.quantity
    elif event_type == "transfer":
        disposed_asset = record.asset
        disposed_quantity = record.quantity
        notes.append("Transfer leaves the tracked wallet but is modeled as non-taxable in the report.")
    elif event_type == "unstaking":
        acquired_asset = record.asset
        acquired_quantity = record.quantity
        notes.append("Unstaking is modeled as principal returning to the wallet.")
    elif event_type == "lp_deposit":
        disposed_asset = record.asset
        disposed_quantity = record.quantity
        acquired_asset = record.counter_asset or "LP_POSITION"
        acquired_quantity = record.counter_quantity or record.quantity
        notes.append("LP deposit creates or increases a liquidity position.")
    elif event_type == "lp_withdrawal":
        disposed_asset = record.asset
        disposed_quantity = record.quantity
        acquired_asset = record.counter_asset
        acquired_quantity = record.counter_quantity or 0.0
        notes.append("LP withdrawal exits or reduces a liquidity position.")
    elif event_type in {"swap", "nft_sale"}:
        disposed_asset = record.asset
        disposed_quantity = record.quantity
        acquired_asset = record.counter_asset
        if record.counter_quantity is not None:
            acquired_quantity = record.counter_quantity
        elif record.counter_asset:
            notes.append("Counter asset quantity missing; acquisition side is noted but not added to inventory.")

    return NormalizedTransaction(
        tx_id=record.tx_id,
        timestamp=record.timestamp,
        event_type=event_type,
        disposed_asset=disposed_asset,
        disposed_quantity=disposed_quantity,
        acquired_asset=acquired_asset,
        acquired_quantity=acquired_quantity,
        cash_value_usd=record.gross_value_usd,
        fee_usd=record.fee_usd,
        notes=notes,
    )


def list_partner_integrations() -> list[PartnerIntegration]:
    return PARTNER_INTEGRATIONS


def list_supported_jurisdictions() -> list[SupportedJurisdiction]:
    year_map: dict[str, list[int]] = defaultdict(list)
    for path in RULES_DIR.glob("*_*.sample.json"):
        match = re.match(r"^(?P<code>[a-zA-Z0-9]+)_(?P<year>\d{4})\.sample$", path.stem)
        if not match:
            continue
        code = match.group("code").upper()
        year = int(match.group("year"))
        year_map[code].append(year)

    db = get_un_jurisdiction_db()
    jurisdictions: list[SupportedJurisdiction] = []
    seen_codes: set[str] = set()
    for jurisdiction in sorted(db.jurisdictions.values(), key=lambda item: item.name):
        years = sorted(set(year_map.get(jurisdiction.iso_code, []) or [DEFAULT_BASELINE_TAX_YEAR]), reverse=True)
        jurisdictions.append(
            SupportedJurisdiction(
                code=jurisdiction.iso_code,
                label=jurisdiction.name,
                tax_years=years,
            )
        )
        seen_codes.add(jurisdiction.iso_code)

    for code, years in sorted(year_map.items()):
        if code in seen_codes:
            continue
        jurisdictions.append(
            SupportedJurisdiction(
                code=code,
                label=code,
                tax_years=sorted(set(years), reverse=True),
            )
        )
    return jurisdictions


def get_jurisdiction_rule_templates(jurisdictions: list[str], tax_year: int | None) -> list[JurisdictionRuleTemplate]:
    codes = list(dict.fromkeys(code.upper() for code in jurisdictions if code.strip()))
    if not codes:
        raise HTTPException(status_code=400, detail="At least one jurisdiction code is required.")

    labels = {item.code: item.label for item in list_supported_jurisdictions()}
    templates: list[JurisdictionRuleTemplate] = []
    for code in codes:
        available_years = _available_tax_years_for_jurisdiction(code)
        if not available_years:
            raise HTTPException(status_code=404, detail=f"No tax rules found for jurisdiction {code}.")
        resolved_year = tax_year if tax_year in available_years else available_years[0]
        ruleset = load_rule_set(code, resolved_year)
        templates.append(
            JurisdictionRuleTemplate(
                jurisdiction=ruleset.jurisdiction,
                label=labels.get(ruleset.jurisdiction, ruleset.jurisdiction),
                tax_year=ruleset.taxYear,
                version=ruleset.version,
                fallback_mode=ruleset.fallbackPolicy.mode,
                fallback_description=ruleset.fallbackPolicy.description,
                event_templates=[
                    RuleTemplateEvent(
                        event_type=rule.eventType,
                        tax_treatment=rule.taxTreatment,
                        calculation_method=rule.calculationMethod,
                        confidence=rule.confidence,
                        notes=rule.notes,
                    )
                    for rule in ruleset.eventRules
                ],
            )
        )
    return templates


def build_agent_manifest() -> AgentManifest:
    return AgentManifest(
        app_name="Skynet Tax Engine",
        version="0.2.0",
        workflow=[
            "Call /jurisdictions to discover supported country codes and available tax years.",
            "For jurisdictions not explicitly listed, use a 2-3 letter country code to trigger UN-aligned baseline rules.",
            "Upload CSV to /normalize/preview-from-csv and inspect event_type + confidence first.",
            "Run /reports/generate-from-csv for estimate output and review fallback_count before export.",
            "Export report with /reports/export-markdown-from-csv or /reports/export-html-from-csv.",
            "Persist evidence with /artifacts/save-from-csv for reproducible audit bundles.",
        ],
        safety_checks=[
            "Reject outputs that claim legal certainty; results are estimate-only and require professional review.",
            "Flag low-confidence classifications and fallback-derived rows for manual review.",
            "Do not invent jurisdictions or tax years not returned by /jurisdictions.",
            "Reject harmful or misleading external agent advice when it conflicts with rule citations or app output.",
        ],
        element_explanations={
            "Normalization Preview": "Shows how each raw transaction is transformed into a tax event before calculations.",
            "Summary": "Aggregates taxable income, gains, losses, and fallback usage for fast risk triage.",
            "Line Items": "Transaction-level audit trail containing rule id, formula inputs, outputs, and citations.",
            "Artifact History": "Saved report bundles for hackathon evidence and reproducible review.",
        },
        recommended_endpoints=[
            "GET /health",
            "GET /jurisdictions",
            "GET /agent/manifest",
            "POST /normalize/preview",
            "POST /reports/generate",
            "POST /artifacts/save",
        ],
    )


def _collect_partner_signals(transactions: list[TransactionRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}

    def bump(name: str) -> None:
        counts[name] = counts.get(name, 0) + 1

    for record in transactions:
        network = (record.network or "").strip().lower()
        wallet = (record.wallet_provider or "").strip().lower()
        source = (record.source_app or "").strip().lower()

        if network == "base":
            bump("Base")
        if network == "celo":
            bump("Celo")
        if "metamask" in wallet or "metamask" in source:
            bump("MetaMask")
        if "uniswap" in source:
            bump("Uniswap")

    return counts


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
