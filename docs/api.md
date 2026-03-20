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

### `GET /artifacts`

Returns the saved artifact bundle history from the local `artifacts/` directory.

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
- fallback indicators when no jurisdiction-specific rule exists
- assumptions used by the MVP engine
- normalized asset flow details for disposals and acquisitions
- partner-signal counts for Base, Celo, MetaMask, and Uniswap metadata
- protocol-aware handling for LP deposit, LP withdrawal, and unstaking events in the MVP

## Markdown Export

- `POST /reports/export-markdown`
- `POST /reports/export-markdown-from-csv`

These return a judge-friendly Markdown report attachment.
The Markdown export includes rule citations when they exist in the applied rule set.

## Saved Artifacts

- `POST /artifacts/save`
- `POST /artifacts/save-from-csv`

These persist a run bundle under `artifacts/` containing:

- `report.json`
- `skynet-report-<jurisdiction>-<taxYear>.md`
- `normalization-preview.json`

## Collaboration Trail

Hackathon progress notes are tracked in `docs/collaboration-log.md`.
