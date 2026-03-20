from __future__ import annotations

import csv
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from fastapi import HTTPException

from app.models import (
    ArtifactBundle,
    ArtifactBundleSummary,
    ClassifiedTransaction,
    EventRule,
    GenerateReportRequest,
    MarkdownExport,
    NormalizedTransaction,
    NormalizationPreviewItem,
    PartnerIntegration,
    ReportLineItem,
    ReportSummary,
    RuleSet,
    TaxReport,
    TaxTreatment,
    TransactionRecord,
)


RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
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
    path = RULES_DIR / f"{jurisdiction.lower()}_{tax_year}.sample.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No rule set found for {jurisdiction} {tax_year}")
    with path.open("r", encoding="utf-8") as handle:
        return RuleSet.model_validate(json.load(handle))


def parse_transactions_csv(content: bytes) -> list[TransactionRecord]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    rows: list[TransactionRecord] = []
    for index, row in enumerate(reader, start=1):
        normalized = {key.strip().lower(): (value.strip() if isinstance(value, str) else value) for key, value in row.items()}
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


def generate_report(request: GenerateReportRequest) -> TaxReport:
    rule_set = load_rule_set(request.jurisdiction, request.tax_year)
    rule_by_event = {rule.eventType: rule for rule in rule_set.eventRules}
    inventory: dict[str, deque[Lot]] = defaultdict(deque)
    line_items: list[ReportLineItem] = []
    assumptions = [
        "FIFO is used for disposal cost basis in the MVP.",
        "USD values are taken from the transaction CSV when provided; otherwise quantity * price_usd is used.",
        "Swap normalization tracks disposed and acquired sides separately when counter asset data is present.",
        "Liquidity add/remove flows are approximated using single-sided asset records in the MVP unless both legs are supplied.",
        "Fallback-derived results are estimates and should be reviewed by a tax professional.",
    ]

    for transaction in sorted(request.transactions, key=lambda row: row.timestamp):
        classified = classify_transaction(transaction)
        rule = rule_by_event.get(classified.event_type)
        fallback_applied = rule is None
        if fallback_applied:
            rule = _fallback_rule(classified.event_type, rule_set.fallbackPolicy.mode)

        taxable_amount, cost_basis, gain_or_loss, explanation = _apply_rule(classified, rule, inventory)
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
            )
        )

    summary = ReportSummary(
        jurisdiction=rule_set.jurisdiction,
        tax_year=rule_set.taxYear,
        total_taxable_income_usd=round(sum(item.taxable_amount_usd for item in line_items if item.tax_treatment == "taxable_income"), 2),
        total_capital_gains_usd=round(sum(max(item.gain_or_loss_usd, 0) for item in line_items if item.tax_treatment in {"capital_gains", "mixed"}), 2),
        total_capital_losses_usd=round(sum(min(item.gain_or_loss_usd, 0) for item in line_items if item.tax_treatment in {"capital_gains", "mixed"}), 2),
        fallback_count=sum(1 for item in line_items if item.fallback_applied),
        partner_signals=_collect_partner_signals(request.transactions),
    )
    return TaxReport(summary=summary, line_items=line_items, assumptions=assumptions)


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
                f"- Calculation method: {item.calculation_method}",
                f"- Explanation: {item.explanation}",
            ]
        )
        if item.rule_notes:
            lines.append(f"- Rule notes: {item.rule_notes}")
        if item.citations:
            lines.append("- Citations:")
            lines.extend([f"  - {citation.authority}: {citation.title} ({citation.url})" for citation in item.citations])
        lines.append("")

    filename = f"skynet-report-{summary.jurisdiction.lower()}-{summary.tax_year}.md"
    return MarkdownExport(filename=filename, content="\n".join(lines).strip() + "\n")


def save_artifact_bundle(request: GenerateReportRequest) -> ArtifactBundle:
    report = generate_report(request)
    preview = preview_normalization(request)
    markdown_export = export_report_markdown(report)

    bundle_id = _bundle_id(request.jurisdiction, request.tax_year)
    bundle_dir = ARTIFACTS_DIR / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    report_json_path = bundle_dir / "report.json"
    report_markdown_path = bundle_dir / markdown_export.filename
    preview_path = bundle_dir / "normalization-preview.json"

    report_json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    report_markdown_path.write_text(markdown_export.content, encoding="utf-8")
    preview_path.write_text(json.dumps([item.model_dump(mode="json") for item in preview], indent=2), encoding="utf-8")

    return ArtifactBundle(
        bundle_id=bundle_id,
        directory=str(bundle_dir),
        report_json=str(report_json_path),
        report_markdown=str(report_markdown_path),
        normalization_preview=str(preview_path),
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
        bundles.append(
            ArtifactBundleSummary(
                bundle_id=bundle_dir.name,
                directory=str(bundle_dir),
                report_json=str(report_json_path),
                report_markdown=str(report_markdown_path),
                normalization_preview=str(preview_path),
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
        return gross_value, gross_value, 0.0, "Recorded receipt value as taxable basis and added inventory lot."

    if classified.event_type in {"transfer", "unstaking", "lp_deposit"}:
        if classified.event_type == "unstaking" and normalized.acquired_asset:
            inventory[normalized.acquired_asset].append(Lot(quantity=normalized.acquired_quantity, unit_cost_usd=0))
            return 0.0, 0.0, 0.0, "Modeled unstaking as non-taxable principal return and added the returned asset to inventory with placeholder basis."
        if classified.event_type == "lp_deposit":
            acquired_asset = normalized.acquired_asset or "LP_POSITION"
            acquired_quantity = normalized.acquired_quantity or record.quantity
            unit_cost = gross_value / acquired_quantity if acquired_quantity else 0
            inventory[acquired_asset].append(Lot(quantity=acquired_quantity, unit_cost_usd=unit_cost))
            return 0.0, gross_value, 0.0, "Modeled LP deposit as non-taxable position entry and added the LP position token to inventory."
        return 0.0, 0.0, 0.0, "Treated as non-taxable transfer."

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
            return proceeds, cost_basis, gain_or_loss, "Modeled LP withdrawal as a position exit using FIFO for the disposed side and normalized return legs when present."
        return proceeds, cost_basis, gain_or_loss, "Disposed inventory using FIFO and normalized swap legs for clearer audit output."

    return gross_value, 0.0, 0.0, "Unsupported event type fell back to generic taxable treatment."


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


def _bundle_id(jurisdiction: str, tax_year: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", jurisdiction.lower()).strip("-") or "report"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{slug}-{tax_year}-{stamp}"


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
