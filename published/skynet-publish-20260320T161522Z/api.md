# Skynet API

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/` for the browser demo UI.

## Endpoints

### `GET /health`

Simple health check.

### `GET /`

Serves the browser-based demo interface for CSV upload and report review.

### `GET /partners`

Returns the current partner integration catalog and status.

### `GET /jurisdictions`

Returns the currently supported jurisdiction codes and available tax years discovered from the local rule packs.

### `GET /agent/manifest`

Returns an agent-oriented manifest describing recommended workflow, safety checks, endpoint affordances, and key app element explanations.

### `GET /guide`

Returns a structured operator guide for both humans and AI agents, including:

- product purpose and version
- recommended workflow steps
- workflow steps including CSV readiness inspection
- explanations for major UI surfaces
- explanations for major report fields
- autonomous-use notes
- scalability notes

### `POST /autonomy/plan-from-csv`

Accepts multipart form fields:

- `jurisdiction`
- `tax_year`
- `file`

Returns a machine-readable autonomy run decision with:

- overall autonomy status (`ready`, `review`, `blocked`)
- recommended action for the next branch (`generate_report`, `review_predictions`, `repair_csv`)
- stats covering warning rows, low-confidence classifications, and predicted fallback usage
- ordered next steps and endpoint hints for agent handoff
- rationale and handoff notes for human or AI operators

### `POST /ingestion/readiness-from-csv`

Accepts multipart form fields:

- `file`

Returns a lightweight readiness report with:

- required/present/missing CSV columns
- row counts and readiness state (`ready`, `needs_review`, `blocked`)
- row-level and file-level issues
- agent notes for autonomous workflow gating

### `GET /artifacts`

Returns the saved artifact bundle history from the local `artifacts/` directory.

### `POST /publish`

Creates a local publish snapshot under `published/` using the latest docs and most recent artifact evidence bundle.

### `POST /reports/generate`

Accepts JSON with:

- `jurisdiction`
- `tax_year`
- `transactions`

### `POST /normalize/preview`

Accepts the same JSON payload as `/reports/generate` and returns the detected event type plus normalized asset flow before tax calculations are applied.

### `POST /reports/generate-from-csv`

Multipart form fields:

- `jurisdiction`
- `tax_year`
- `file`

### `POST /normalize/preview-from-csv`

Accepts the same multipart form fields as `/reports/generate-from-csv` and returns the normalization preview.

Expected CSV columns:

- `tx_id`
- `timestamp`
- `asset`
- `quantity`
- `tx_hash`
- `network`
- `wallet_provider`
- `source_app`
- `event_hint`
- `price_usd`
- `proceeds_usd`
- `fee_usd`
- `counter_asset`
- `counter_quantity`
- `description`

## Output

The generated report includes:

- summary totals for income and capital gains/losses
- line-by-line explainability data
- rule citation links when available in the rule pack
- structured formula inputs and outputs for each line item
- fallback indicators when no jurisdiction-specific rule exists
- assumptions used by the MVP engine
- normalized asset flow details for disposals and acquisitions
- partner-signal counts for Base, Celo, MetaMask, and Uniswap metadata
- protocol-aware handling for LP deposit, LP withdrawal, and unstaking events in the MVP

The readiness report includes:

- required/present/missing column visibility
- blocker and warning counts before normalization
- row-level recommendations for duplicate IDs, missing timestamps, weak valuation data, and incomplete swap legs
- agent-oriented next-step decisions through the autonomy planner

## Markdown Export

- `POST /reports/export-markdown`
- `POST /reports/export-markdown-from-csv`

These return a judge-friendly Markdown report attachment.
The Markdown export includes rule citations when they exist in the applied rule set.

## HTML Export

- `POST /reports/export-html`
- `POST /reports/export-html-from-csv`

These return an HTML report with an audit-oriented table including rule IDs and formula details.

## Saved Artifacts

- `POST /artifacts/save`
- `POST /artifacts/save-from-csv`

These persist a run bundle under `artifacts/` containing:

- `report.json`
- `skynet-report-<jurisdiction>-<taxYear>.md`
- `skynet-report-<jurisdiction>-<taxYear>.html`
- `normalization-preview.json`
- `collaboration-log.md`

## Collaboration Trail

Hackathon progress notes are tracked in `docs/collaboration-log.md`.
