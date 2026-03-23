# skill.md — Skynet Tax Agent Skill Guide

Scope: This guide helps AI agents and operators use the Skynet Smart Tax Tool for crypto taxes and financial reporting.

## 1) What Skynet does

Skynet converts on-chain or wallet-export CSV data into an explainable, jurisdiction-aware crypto tax estimate.

Core problem framing:
- Crypto users across jurisdictions struggle to produce compliant, auditable tax records.
- Skynet addresses this by classifying on-chain/CSV activity and applying jurisdiction-aware tax logic with transparent assumptions.

## 2) Recommended operating workflow

Use this order for every run:
1. **Inspect CSV readiness** (`/ingestion/readiness-from-csv`)
2. **Preview normalization** (`/normalize/preview-from-csv`)
3. **Generate report** (`/reports/generate-from-csv`)
4. **Export or save evidence** (`/reports/export-markdown-from-csv`, `/reports/export-html-from-csv`, `/artifacts/save-from-csv`)
5. **Publish snapshot** (`/publish`) when a reviewable package is needed

## 3) Jurisdiction + year behavior

- Use `/jurisdictions` to discover country codes and labels.
- Skynet supports a per-country selection model from the UN coverage dataset.
- `tax_year` is optional in CSV/form flows.
- Year resolution strategy:
  1. Use selected/requested year if rules exist.
  2. Else, infer from years present in CSV transactions where possible.
  3. Else, use the latest available ruleset year for that jurisdiction code.
- Even when ruleset year falls back, tax calculations still run across the **full CSV time span**.
- Report summary includes:
  - `period_start`
  - `period_end`
  - `period_label`
  - `tax_year_selection_note`

## 4) CSV contract essentials

Preferred columns:
- `tx_id`, `timestamp`, `asset`, `quantity`
- `tx_hash`, `network`, `wallet_provider`, `source_app`
- `event_hint`, `price_usd`, `proceeds_usd`, `fee_usd`
- `counter_asset`, `counter_quantity`, `description`

Minimum quality checks for agents:
- No duplicate transaction IDs.
- Valid timestamps and positive quantities.
- Preserve source metadata for explainability and partner signal tracking.

## 5) Event normalization expectations

Skynet classifies common crypto actions such as:
- income
- transfer
- swap
- staking / unstaking
- LP deposit / LP withdrawal
- NFT sale
- airdrop
- mining

Agent policy:
- Treat low-confidence classifications as review points.
- Treat fallback-applied lines as escalation points for manual verification.

## 6) Report interpretation

Key summary values:
- Total taxable income (USD)
- Total capital gains (USD)
- Total capital losses (USD)
- Fallback count
- Partner signals (e.g., Base, MetaMask, Uniswap)

Line items contain rule IDs, confidence, formulas, and citations.
Use these fields directly in audit notes and handoffs.

## 7) Safe output policy for AI agents

Agents using this tool should:
- Present outputs as **tax estimates**, not legal/tax advice.
- Surface assumptions and fallback warnings clearly.
- Recommend local professional review before filing.
- Never fabricate jurisdiction rules that are unavailable in the system.

## 8) Security + secret handling

Never expose or commit:
- API keys
- private keys
- OTP/2FA secrets
- transfer tokens or session secrets

Store non-sensitive run context in local env files if needed for workflow continuity.

## 9) Suggested prompt template for agents

> You are operating Skynet Tax Engine.
> 1) Run readiness check on uploaded CSV.
> 2) Show normalization preview and flag low-confidence items.
> 3) Generate jurisdiction report with selected country and optional year.
> 4) If year is missing/unavailable, explain year fallback and keep CSV span coverage.
> 5) Return summary metrics, fallback count, and top review actions.

## 10) Human handoff checklist

Before handoff, include:
- Jurisdiction code + label used
- Requested vs resolved tax year
- CSV period span
- Count of low-confidence and fallback items
- Exported artifact locations (Markdown/HTML/bundle)

---

Maintainers can extend this skill as Skynet adds new jurisdictions, rulesets, integrations, and filing workflows.
