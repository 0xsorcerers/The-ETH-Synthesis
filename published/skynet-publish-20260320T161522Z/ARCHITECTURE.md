# Skynet Architecture

## Goals

1. Produce explainable tax estimates for crypto users.
2. Prioritize jurisdiction-specific crypto tax treatment.
3. Fall back safely to traditional tax handling when crypto-specific rules are absent.

## High-Level Components

1. **Frontend (Web UI)**
   - Upload CSV / provide wallet address
   - Select jurisdiction and tax year
   - Display report + audit trail

2. **API Layer**
   - Receives ingestion and report generation requests
   - Orchestrates classification, rule resolution, and calculation
   - Exposes an `agent manifest` and supported-jurisdiction discovery for autonomous client orchestration

3. **Ingestion Service**
   - Parses transaction inputs
   - Normalizes into canonical transaction schema
   - Runs a CSV readiness inspection contract before full parsing so structural blockers and weak metadata are surfaced early

4. **Classification Service**
   - Rule-based first pass
   - LLM fallback for ambiguous labels

5. **Rule Engine**
   - Loads rules by `jurisdiction` + `taxYear`
   - Caches hot rule sets in memory to reduce repeated file I/O under frequent requests
   - Applies fallback hierarchy when local crypto rules are missing

6. **Calculation Engine**
   - Computes gains/losses and taxable income
   - Uses FIFO for MVP cost basis

7. **Reporting Service**
   - Produces summary, assumptions, confidence, and audit log
   - Exports markdown/PDF/JSON

8. **Operator Guide Layer**
   - Exposes a structured explanation contract for UI surfaces and report elements
   - Helps human operators and AI agents follow the same safe workflow
   - Keeps explanation metadata separate from tax-calculation logic

9. **Autonomy Planner**
   - Combines readiness inspection, normalization-preview confidence, and rule coverage into a single machine-readable run decision
   - Tells agents whether to repair CSV inputs, pause for review, or continue into full analysis
   - Reduces orchestration logic duplicated across UI clients and autonomous workers

## Data Flow

1. User uploads transactions.
2. Readiness inspection flags missing columns, duplicate transaction IDs, and weak pricing or counter-asset metadata.
3. Ingestion normalizes to canonical schema.
4. Classifier tags each event type.
5. Rule engine resolves applicable rule set.
6. Calculation engine computes tax-relevant totals.
7. Report generator returns explainable output and export artifacts.
8. Operator guide exposes machine-readable workflow and element descriptions for UI clients and agents.
9. Autonomy planner emits the recommended next action and handoff steps before a fully autonomous run proceeds.

## Fallback Strategy

When crypto-specific jurisdiction rules are unavailable:

1. Apply defined fallback in rule set (`fallbackPolicy`).
2. Mark affected sections as **fallback-derived**.
3. Include assumptions and confidence adjustments.

## Explainability / Auditability

Each computed event should include:

- source transaction id
- classification decision
- applied rule id/version
- calculation formula inputs/outputs
- confidence and fallback flags

## Agent-First Interface Layer

Skynet now includes lightweight agent affordances:

- `GET /jurisdictions` for machine-readable support discovery.
- `GET /agent/manifest` for workflow steps, UI element semantics, and safety checks.
- UI-level guided workflow cards so both humans and AI operators use the same execution path.

The product should also expose:

- a stable ingestion-readiness contract for preflight file validation
- a stable guide to major UI elements
- a stable autonomy-plan contract for branching autonomous workflows
- operational notes for autonomous agents
- report-field explanations that can be consumed without scraping the UI

## Suggested Tech Stack

- Frontend: Next.js / React
- API: FastAPI (Python)
- Rule storage: JSON files in `rules/`
- Optional DB: SQLite/Postgres
- LLM provider: OpenAI-compatible API abstraction
