# Skynet API

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

## Endpoints

### `GET /health`

Simple health check.

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
- `description`

## Output

The generated report includes:

- summary totals for income and capital gains/losses
- line-by-line explainability data
- fallback indicators when no jurisdiction-specific rule exists
- assumptions used by the MVP engine
