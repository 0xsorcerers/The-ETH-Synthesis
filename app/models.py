from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


EventType = Literal[
    "income",
    "transfer",
    "swap",
    "staking",
    "unstaking",
    "lp_deposit",
    "lp_withdrawal",
    "nft_sale",
    "airdrop",
    "mining",
]
TaxTreatment = Literal["taxable_income", "capital_gains", "non_taxable", "mixed"]


class FallbackPolicy(BaseModel):
    mode: Literal["traditional_tax_law", "manual_review_required"]
    description: str


class RuleCitation(BaseModel):
    title: str
    url: str
    authority: str


class EventRule(BaseModel):
    eventType: EventType
    taxTreatment: TaxTreatment
    calculationMethod: str
    confidence: float = Field(ge=0, le=1)
    notes: str | None = None
    citations: list[RuleCitation] = Field(default_factory=list)


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
    citations: list[RuleCitation] = Field(default_factory=list)
    source_tx_hash: str | None = None
    source_network: str | None = None
    source_app: str | None = None
    source_wallet_provider: str | None = None
    rule_id: str
    formula_inputs: dict[str, float | str | None] = Field(default_factory=dict)
    formula_outputs: dict[str, float | str | None] = Field(default_factory=dict)


class ReportSummary(BaseModel):
    jurisdiction: str
    tax_year: int
    requested_tax_year: int | None = None
    period_start: datetime
    period_end: datetime
    period_label: str
    tax_year_selection_note: str
    total_taxable_income_usd: float
    total_capital_gains_usd: float
    total_capital_losses_usd: float
    fallback_count: int
    partner_signals: dict[str, int] = Field(default_factory=dict)


class WorkflowStep(BaseModel):
    id: str
    label: str
    description: str
    agent_hint: str


class ExplanationItem(BaseModel):
    id: str
    label: str
    audience: list[Literal["human", "agent"]]
    summary: str
    operational_note: str


class ExplanationGuide(BaseModel):
    product_name: str
    version: str
    purpose: str
    workflows: list[WorkflowStep]
    ui_elements: list[ExplanationItem]
    report_elements: list[ExplanationItem]
    autonomous_usage_notes: list[str]
    scalability_notes: list[str]


class TaxReport(BaseModel):
    summary: ReportSummary
    line_items: list[ReportLineItem]
    assumptions: list[str]


class MarkdownExport(BaseModel):
    filename: str
    content: str


class HtmlExport(BaseModel):
    filename: str
    content: str


class ArtifactBundle(BaseModel):
    bundle_id: str
    directory: str
    report_json: str
    report_markdown: str
    report_html: str
    normalization_preview: str
    collaboration_log: str


class ArtifactBundleSummary(BaseModel):
    bundle_id: str
    directory: str
    report_json: str
    report_markdown: str
    report_html: str
    normalization_preview: str
    collaboration_log: str


class PartnerIntegration(BaseModel):
    id: str
    name: str
    status: Literal["active", "planned"]
    category: str
    description: str
    docs_url: str


class NormalizationPreviewItem(BaseModel):
    tx_id: str
    event_type: EventType
    confidence: float
    rationale: str
    normalized: NormalizedTransaction


class SupportedJurisdiction(BaseModel):
    code: str
    label: str
    tax_years: list[int] = Field(default_factory=list)


class RuleTemplateEvent(BaseModel):
    event_type: EventType
    tax_treatment: TaxTreatment
    calculation_method: str
    confidence: float = Field(ge=0, le=1)
    notes: str | None = None


class JurisdictionRuleTemplate(BaseModel):
    jurisdiction: str
    label: str
    tax_year: int
    version: str
    fallback_mode: Literal["traditional_tax_law", "manual_review_required"]
    fallback_description: str
    event_templates: list[RuleTemplateEvent]


class AgentManifest(BaseModel):
    app_name: str
    version: str
    workflow: list[str]
    safety_checks: list[str]
    element_explanations: dict[str, str]
    recommended_endpoints: list[str]


class PublishedBuild(BaseModel):
    publish_id: str
    directory: str
    summary_markdown: str
    included_artifacts: list[str] = Field(default_factory=list)
    included_docs: list[str] = Field(default_factory=list)


class IngestionIssue(BaseModel):
    severity: Literal["info", "warning", "error"]
    scope: Literal["file", "row"]
    row_number: int | None = None
    tx_id: str | None = None
    message: str
    recommendation: str


class IngestionReadinessSummary(BaseModel):
    total_rows: int
    valid_rows: int
    flagged_rows: int
    error_count: int
    warning_count: int
    readiness: Literal["ready", "needs_review", "blocked"]


class IngestionReadinessReport(BaseModel):
    summary: IngestionReadinessSummary
    required_columns: list[str]
    present_columns: list[str]
    missing_columns: list[str]
    issues: list[IngestionIssue]
    agent_notes: list[str]


class AutonomyPlanStats(BaseModel):
    total_transactions: int
    blocked_rows: int
    warning_rows: int
    low_confidence_count: int
    predicted_fallback_count: int


class AutonomyPlanStep(BaseModel):
    id: str
    label: str
    status: Literal["ready", "review", "blocked"]
    detail: str
    endpoint: str | None = None


class AutonomyPlan(BaseModel):
    jurisdiction: str
    tax_year: int
    autonomy_status: Literal["ready", "review", "blocked"]
    recommended_action: Literal["repair_csv", "review_predictions", "generate_report"]
    summary: str
    rationale: list[str]
    stats: AutonomyPlanStats
    next_steps: list[AutonomyPlanStep]
    handoff_notes: list[str]


class GenerateReportRequest(BaseModel):
    jurisdiction: str = Field(min_length=2, max_length=8)
    tax_year: int | None = Field(default=None, ge=2000)
    transactions: list[TransactionRecord]


class MultiJurisdictionReportRequest(BaseModel):
    jurisdictions: list[str] = Field(min_length=1)
    tax_year: int | None = Field(default=None, ge=2000)
    transactions: list[TransactionRecord]


class JurisdictionReportResult(BaseModel):
    jurisdiction: str
    label: str
    report: TaxReport


class MultiJurisdictionComparisonRow(BaseModel):
    jurisdiction: str
    label: str
    taxable_income_usd: float
    capital_gains_usd: float
    capital_losses_usd: float
    fallback_count: int


class MultiJurisdictionReport(BaseModel):
    tax_year: int
    jurisdictions: list[str]
    reports: list[JurisdictionReportResult]
    comparison: list[MultiJurisdictionComparisonRow]
