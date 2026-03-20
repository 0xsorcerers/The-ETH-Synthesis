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

### `POST /reports/generate`

Accepts JSON with:

- `jurisdiction`
- `tax_year`
- `transactions`

### `POST /reports/generate-from-csv`

Multipart form fields:

- `jurisdiction`
- `tax_year`
- `file`

Expected CSV columns:

- `tx_id`
- `timestamp`
- `asset`
- `quantity`
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
- fallback indicators when no jurisdiction-specific rule exists
- assumptions used by the MVP engine
- normalized asset flow details for disposals and acquisitions

## Markdown Export

- `POST /reports/export-markdown`
- `POST /reports/export-markdown-from-csv`

These return a judge-friendly Markdown report attachment.

## Collaboration Trail

Hackathon progress notes are tracked in `docs/collaboration-log.md`.
