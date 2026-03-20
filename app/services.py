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
    if "transfer" in haystack or "bridge" in haystack:
        return ClassifiedTransaction(transaction=record, event_type="transfer", confidence=0.95, rationale="Detected transfer or bridge language.")
    if "stake" in haystack or "reward" in haystack:
        return ClassifiedTransaction(transaction=record, event_type="staking", confidence=0.88, rationale="Detected staking or reward language.")
    if "airdrop" in haystack:
        return ClassifiedTransaction(transaction=record, event_type="airdrop", confidence=0.9, rationale="Detected airdrop language.")
    if "mine" in haystack:
        return ClassifiedTransaction(transaction=record, event_type="mining", confidence=0.9, rationale="Detected mining language.")
    if "nft" in haystack:
        return ClassifiedTransaction(transaction=record, event_type="nft_sale", confidence=0.82, rationale="Detected NFT language.")
    if "salary" in haystack or "income" in haystack or "payment" in haystack:
        return ClassifiedTransaction(transaction=record, event_type="income", confidence=0.84, rationale="Detected income-like language.")
    if record.counter_asset:
        return ClassifiedTransaction(transaction=record, event_type="swap", confidence=0.8, rationale="Counter asset present, treated as asset swap.")
    return ClassifiedTransaction(transaction=record, event_type="income", confidence=0.55, rationale="Defaulted to income due to missing stronger signal.")


def generate_report(request: GenerateReportRequest) -> TaxReport:
    rule_set = load_rule_set(request.jurisdiction, request.tax_year)
    rule_by_event = {rule.eventType: rule for rule in rule_set.eventRules}
    inventory: dict[str, deque[Lot]] = defaultdict(deque)
    line_items: list[ReportLineItem] = []
    assumptions = [
        "FIFO is used for disposal cost basis in the MVP.",
        "USD values are taken from the transaction CSV when provided; otherwise quantity * price_usd is used.",
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


def _apply_rule(
    classified: ClassifiedTransaction,
    rule: EventRule,
    inventory: dict[str, deque[Lot]],
) -> tuple[float, float, float, str]:
    record = classified.transaction
    gross_value = record.gross_value_usd

    if classified.event_type in {"income", "staking", "airdrop", "mining"}:
        unit_cost = gross_value / record.quantity if record.quantity else 0
        inventory[record.asset].append(Lot(quantity=record.quantity, unit_cost_usd=unit_cost))
        return gross_value, gross_value, 0.0, "Recorded receipt value as taxable basis and added inventory lot."

    if classified.event_type == "transfer":
        return 0.0, 0.0, 0.0, "Treated as non-taxable transfer."

    if classified.event_type in {"swap", "nft_sale"}:
        cost_basis = _consume_fifo(inventory[record.asset], record.quantity)
        proceeds = gross_value - record.fee_usd
        gain_or_loss = proceeds - cost_basis
        if classified.event_type == "swap" and record.counter_asset and record.proceeds_usd is not None and record.quantity > 0:
            acquired_unit_cost = proceeds / record.quantity
            inventory[record.counter_asset].append(Lot(quantity=record.quantity, unit_cost_usd=acquired_unit_cost))
        return proceeds, cost_basis, gain_or_loss, "Disposed inventory using FIFO to estimate gain/loss."

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

