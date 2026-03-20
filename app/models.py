from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


EventType = Literal["income", "transfer", "swap", "staking", "nft_sale", "airdrop", "mining"]
TaxTreatment = Literal["taxable_income", "capital_gains", "non_taxable", "mixed"]


class FallbackPolicy(BaseModel):
    mode: Literal["traditional_tax_law", "manual_review_required"]
    description: str


class EventRule(BaseModel):
    eventType: EventType
    taxTreatment: TaxTreatment
    calculationMethod: str
    confidence: float = Field(ge=0, le=1)
    notes: str | None = None


class RuleSet(BaseModel):
    jurisdiction: str
    taxYear: int
    version: str
    fallbackPolicy: FallbackPolicy
    eventRules: list[EventRule]


class TransactionRecord(BaseModel):
    tx_id: str
    timestamp: datetime
    asset: str
    quantity: float = Field(gt=0)
    tx_hash: str | None = None
    network: str | None = None
    wallet_provider: str | None = None
    source_app: str | None = None
    event_hint: str | None = None
    price_usd: float | None = Field(default=None, ge=0)
    proceeds_usd: float | None = Field(default=None, ge=0)
    fee_usd: float = Field(default=0, ge=0)
    counter_asset: str | None = None
    counter_quantity: float | None = Field(default=None, ge=0)
    description: str | None = None

    @computed_field
    @property
    def gross_value_usd(self) -> float:
        if self.proceeds_usd is not None:
            return self.proceeds_usd
        if self.price_usd is None:
            return 0.0
        return round(self.quantity * self.price_usd, 2)


class NormalizedTransaction(BaseModel):
    tx_id: str
    timestamp: datetime
    event_type: EventType
    disposed_asset: str | None = None
    disposed_quantity: float = 0
    acquired_asset: str | None = None
    acquired_quantity: float = 0
    cash_value_usd: float = 0
    fee_usd: float = 0
    notes: list[str] = Field(default_factory=list)


class ClassifiedTransaction(BaseModel):
    transaction: TransactionRecord
    event_type: EventType
    confidence: float = Field(ge=0, le=1)
    rationale: str
    normalized: NormalizedTransaction


class ReportLineItem(BaseModel):
    tx_id: str
    asset: str
    event_type: EventType
    tax_treatment: TaxTreatment
    taxable_amount_usd: float
    cost_basis_usd: float
    gain_or_loss_usd: float
    confidence: float
    fallback_applied: bool
    explanation: str
    rule_version: str
    calculation_method: str
    disposed_asset: str | None = None
    disposed_quantity: float = 0
    acquired_asset: str | None = None
    acquired_quantity: float = 0
    rule_notes: str | None = None


class ReportSummary(BaseModel):
    jurisdiction: str
    tax_year: int
    total_taxable_income_usd: float
    total_capital_gains_usd: float
    total_capital_losses_usd: float
    fallback_count: int
    partner_signals: dict[str, int] = Field(default_factory=dict)


class TaxReport(BaseModel):
    summary: ReportSummary
    line_items: list[ReportLineItem]
    assumptions: list[str]


class MarkdownExport(BaseModel):
    filename: str
    content: str


class PartnerIntegration(BaseModel):
    id: str
    name: str
    status: Literal["active", "planned"]
    category: str
    description: str
    docs_url: str


class GenerateReportRequest(BaseModel):
    jurisdiction: str = Field(min_length=2, max_length=8)
    tax_year: int = Field(ge=2000)
    transactions: list[TransactionRecord]
