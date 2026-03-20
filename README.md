# Skynet by 0xSorcerer

Skynet is an AI tax co-pilot for crypto earners. It estimates tax obligations by jurisdiction, using crypto-specific tax rules when available and falling back to traditional tax treatment when crypto-specific guidance is unavailable.

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

## Supported Jurisdictions (MVP)

- United States (US)
- United Kingdom (UK)
- Nigeria (NG)

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md).

## Demo Script

See [DEMO_SCRIPT.md](./DEMO_SCRIPT.md).

## Data Contracts

- Rule schema: [`RULES_SCHEMA.json`](./RULES_SCHEMA.json)
- Sample rules:
  - [`rules/us_2025.sample.json`](./rules/us_2025.sample.json)
  - [`rules/uk_2025.sample.json`](./rules/uk_2025.sample.json)
  - [`rules/ng_2025.sample.json`](./rules/ng_2025.sample.json)

## Setup (Hackathon Baseline)

```bash
# create venv (optional)
python -m venv .venv
source .venv/bin/activate

# install API dependencies (when backend scaffold is added)
pip install fastapi uvicorn pydantic
```

## Submission Notes

- This tool is an **estimation and compliance assistant**, not legal/tax advice.
- Results should be reviewed by a qualified tax professional before filing.

## Roadmap

- Wallet connectors (EVM indexers, exchange APIs)
- Cost basis methods (FIFO/LIFO/HIFO selectable)
- More jurisdictions and yearly rule versioning
- Evidence-backed citation layer for tax references
- Agentic workflow for draft filing assistance
