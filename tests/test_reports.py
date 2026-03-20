from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_index_serves_demo_ui():
    response = client.get("/")

    assert response.status_code == 200
    assert "Skynet" in response.text
    assert "Generate Report" in response.text


def test_generate_report_from_json():
    response = client.post(
        "/reports/generate",
        json={
            "jurisdiction": "US",
            "tax_year": 2025,
            "transactions": [
                {
                    "tx_id": "tx-001",
                    "timestamp": "2025-01-10T09:00:00Z",
                    "asset": "ETH",
                    "quantity": 1.5,
                    "event_hint": "income",
                    "price_usd": 2400,
                    "fee_usd": 0,
                    "description": "salary payment in ETH",
                },
                {
                    "tx_id": "tx-002",
                    "timestamp": "2025-03-02T15:30:00Z",
                    "asset": "ETH",
                    "quantity": 0.5,
                    "event_hint": "swap",
                    "proceeds_usd": 1600,
                    "fee_usd": 25,
                    "counter_asset": "SOL",
                    "counter_quantity": 8,
                    "description": "swap ETH into SOL",
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["jurisdiction"] == "US"
    assert body["summary"]["total_taxable_income_usd"] == 3600.0
    assert body["summary"]["total_capital_gains_usd"] == 375.0
    assert body["line_items"][1]["event_type"] == "swap"
    assert body["line_items"][1]["fallback_applied"] is False
    assert body["line_items"][1]["disposed_asset"] == "ETH"
    assert body["line_items"][1]["acquired_asset"] == "SOL"
    assert body["line_items"][1]["acquired_quantity"] == 8


def test_generate_report_from_csv_upload():
    with open("samples/demo_transactions.csv", "rb") as handle:
        response = client.post(
            "/reports/generate-from-csv",
            data={"jurisdiction": "NG", "tax_year": "2025"},
            files={"file": ("demo_transactions.csv", handle, "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["jurisdiction"] == "NG"
    assert body["summary"]["fallback_count"] >= 2
    assert len(body["line_items"]) == 5


def test_export_markdown_from_json():
    response = client.post(
        "/reports/export-markdown",
        json={
            "jurisdiction": "US",
            "tax_year": 2025,
            "transactions": [
                {
                    "tx_id": "tx-001",
                    "timestamp": "2025-01-10T09:00:00Z",
                    "asset": "ETH",
                    "quantity": 1,
                    "event_hint": "income",
                    "price_usd": 2000,
                    "fee_usd": 0,
                    "description": "income payment",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "Skynet Tax Report" in response.text
    assert "Taxable income: $2,000.00" in response.text
