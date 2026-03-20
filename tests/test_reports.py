from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


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
