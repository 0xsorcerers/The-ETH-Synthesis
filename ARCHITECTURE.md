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

3. **Ingestion Service**
   - Parses transaction inputs
   - Normalizes into canonical transaction schema

4. **Classification Service**
   - Rule-based first pass
   - LLM fallback for ambiguous labels

5. **Rule Engine**
   - Loads rules by `jurisdiction` + `taxYear`
   - Applies fallback hierarchy when local crypto rules are missing

6. **Calculation Engine**
   - Computes gains/losses and taxable income
   - Uses FIFO for MVP cost basis

7. **Reporting Service**
   - Produces summary, assumptions, confidence, and audit log
   - Exports markdown/PDF/JSON

## Data Flow

1. User uploads transactions.
2. Ingestion normalizes to canonical schema.
3. Classifier tags each event type.
4. Rule engine resolves applicable rule set.
5. Calculation engine computes tax-relevant totals.
6. Report generator returns explainable output and export artifacts.

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

## Suggested Tech Stack

- Frontend: Next.js / React
- API: FastAPI (Python)
- Rule storage: JSON files in `rules/`
- Optional DB: SQLite/Postgres
- LLM provider: OpenAI-compatible API abstraction
