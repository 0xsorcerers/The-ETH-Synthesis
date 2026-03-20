# Skynet by 0xSorcerer

Skynet is an AI tax co-pilot for crypto earners. It estimates tax obligations by jurisdiction, using crypto-specific tax rules when available and falling back to traditional tax treatment when crypto-specific guidance is unavailable.

## Current Status

- Registration completed successfully
- Verification method: email OTP
- Agent harness: `codex-cli`
- Primary model: `gpt-5.2-codex`

## Problem

Crypto users earning, trading, staking, and transacting across jurisdictions struggle to understand taxable events and comply with local rules.

## Solution

Skynet ingests wallet activity or CSV exports, classifies on-chain activity, and applies a jurisdiction-aware tax rule engine to produce a transparent tax summary report.

## MVP Scope

- Upload CSV transaction history (and optional wallet adapter later)
- Normalize transactions into a canonical schema
- Classify events (income, transfer, swap, staking, NFT)
- Select jurisdiction + tax year
- Apply rule engine:
  - crypto-specific rules first
  - fallback to conventional tax logic when unavailable
- Generate report with:
  - taxable event summary
  - gain/loss totals
  - assumptions and confidence indicators
  - operator guidance for humans and AI agents

## Supported Jurisdictions (MVP)

- United States (US)
- United Kingdom (UK)
- Nigeria (NG)
- Kenya (KE)

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md).

## Demo Script

See [DEMO_SCRIPT.md](./DEMO_SCRIPT.md).

## Guided Operation

- Browser demo includes an operator guide for workflow stages, UI sections, report elements, and autonomous-use notes.
- API exposes the same contract through `GET /guide` so agents can consume it without scraping interface text.
- Browser demo includes a CSV readiness inspection step so humans and AI agents can catch malformed or weak transaction files before normalization and tax calculation.
- Browser demo now includes an autonomy run planner that turns CSV readiness and normalization signals into a concrete next-action handoff for human operators and AI agents.

## Data Contracts

- Rule schema: [`RULES_SCHEMA.json`](./RULES_SCHEMA.json)
- Sample rules:
  - [`rules/us_2025.sample.json`](./rules/us_2025.sample.json)
  - [`rules/uk_2025.sample.json`](./rules/uk_2025.sample.json)
  - [`rules/ng_2025.sample.json`](./rules/ng_2025.sample.json)
  - [`rules/ke_2025.sample.json`](./rules/ke_2025.sample.json)

## Setup (Hackathon Baseline)

```bash
# create venv (optional)
python -m venv .venv
source .venv/bin/activate

# install API dependencies (when backend scaffold is added)
pip install fastapi uvicorn pydantic
```

## Submission Notes

- This tool is an estimation and compliance assistant, not legal or tax advice.
- Results should be reviewed by a qualified tax professional before filing.
- Registration transaction: https://basescan.org/tx/0x3be69aa1e843e835e794ed5a7bb1b46e91793c411e50c33e366cabf36970e02c
- Submission procedure and checklist are tracked in [`docs/submission-playbook.md`](./docs/submission-playbook.md).
- Submission metadata must be honest and evidence-backed. Only list skills actually loaded, tools actually used, and URLs actually opened.
- For this solo-team setup, publish readiness should be checked against the single owner wallet that already completed registration and holds the required participation NFT.

## Ops Notes

- Do not commit API keys, OTPs, participant IDs, team IDs, or other secrets
- Do not ask for or store private keys
- Track build decisions, prompts, and collaboration artifacts in this repository
- Keep remote `main` in sync as work progresses

## Roadmap

- Wallet connectors (EVM indexers, exchange APIs)
- Cost basis methods (FIFO/LIFO/HIFO selectable)
- More jurisdictions and yearly rule versioning
- Evidence-backed citation layer for tax references
- Agentic workflow for draft filing assistance
- Source-specific CSV adapters and richer readiness heuristics for exchange export quality scoring
- Autonomous run orchestration that can branch safely between repair, review, and full analysis for new CSV sources

## New Build Improvements (2026-03-20)

- Agent-ready manifest endpoint: `GET /agent/manifest`
- Dynamic supported-jurisdiction discovery: `GET /jurisdictions`
- Structured operator guide endpoint: `GET /guide`
- Guided workflow and operator guide panels in the UI for human + AI operator alignment
- CSV readiness inspection and autonomy run planner for safer autonomous handoff
- Improved visual depth with a 3D-style hero orb and guide cards
- Rule-set in-memory cache for better throughput when reports are repeatedly generated
- Local publication snapshot flow: `POST /publish` (creates a shareable `published/` bundle from docs + latest artifacts)
