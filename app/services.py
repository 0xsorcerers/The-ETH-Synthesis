from __future__ import annotations

import csv
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from fastapi import HTTPException

from app.models import (
    ClassifiedTransaction,
    EventRule,
    GenerateReportRequest,
    MarkdownExport,
    NormalizedTransaction,
    ReportLineItem,
    ReportSummary,
    RuleSet,
    TaxReport,
    TaxTreatment,
    TransactionRecord,
)


RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


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
    haystack = " ".join(filter(None, [record.event_hint, record.description, record.counter_asset])).lower()
    event_type = "income"
    confidence = 0.55
    rationale = "Defaulted to income due to missing stronger signal."
    if "transfer" in haystack or "bridge" in haystack:
        event_type, confidence, rationale = "transfer", 0.95, "Detected transfer or bridge language."
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
            )
        )

    summary = ReportSummary(
        jurisdiction=rule_set.jurisdiction,
        tax_year=rule_set.taxYear,
        total_taxable_income_usd=round(sum(item.taxable_amount_usd for item in line_items if item.tax_treatment == "taxable_income"), 2),
        total_capital_gains_usd=round(sum(max(item.gain_or_loss_usd, 0) for item in line_items if item.tax_treatment in {"capital_gains", "mixed"}), 2),
        total_capital_losses_usd=round(sum(min(item.gain_or_loss_usd, 0) for item in line_items if item.tax_treatment in {"capital_gains", "mixed"}), 2),
        fallback_count=sum(1 for item in line_items if item.fallback_applied),
    )
    return TaxReport(summary=summary, line_items=line_items, assumptions=assumptions)


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
        "## Assumptions",
        "",
    ]
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
        lines.append("")

    filename = f"skynet-report-{summary.jurisdiction.lower()}-{summary.tax_year}.md"
    return MarkdownExport(filename=filename, content="\n".join(lines).strip() + "\n")


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

    if classified.event_type == "transfer":
        return 0.0, 0.0, 0.0, "Treated as non-taxable transfer."

    if classified.event_type in {"swap", "nft_sale"}:
        disposed_asset = normalized.disposed_asset or record.asset
        disposed_quantity = normalized.disposed_quantity or record.quantity
        cost_basis = _consume_fifo(inventory[disposed_asset], disposed_quantity)
        proceeds = gross_value - record.fee_usd
        gain_or_loss = proceeds - cost_basis
        if classified.event_type == "swap" and normalized.acquired_asset and normalized.acquired_quantity > 0:
            acquired_unit_cost = proceeds / normalized.acquired_quantity
            inventory[normalized.acquired_asset].append(Lot(quantity=normalized.acquired_quantity, unit_cost_usd=acquired_unit_cost))
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
    treatment: TaxTreatment = "non_taxable" if event_type == "transfer" else "capital_gains" if event_type in {"swap", "nft_sale"} else "taxable_income"
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
