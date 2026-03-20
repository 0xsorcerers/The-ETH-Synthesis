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
                    "network": "Base",
                    "wallet_provider": "MetaMask",
                    "source_app": "Payroll App",
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
                    "network": "Base",
                    "wallet_provider": "MetaMask",
                    "source_app": "Uniswap",
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
    assert body["summary"]["partner_signals"]["Base"] == 2
    assert body["summary"]["partner_signals"]["MetaMask"] == 2
    assert body["summary"]["partner_signals"]["Uniswap"] == 1
    assert body["line_items"][1]["disposed_asset"] == "ETH"
    assert body["line_items"][1]["acquired_asset"] == "SOL"
    assert body["line_items"][1]["acquired_quantity"] == 8
    assert body["line_items"][0]["citations"][0]["authority"] == "IRS"


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
    assert body["summary"]["fallback_count"] >= 1
    assert body["summary"]["partner_signals"]["Base"] == 6
    assert body["summary"]["partner_signals"]["Celo"] == 1
    assert body["summary"]["partner_signals"]["MetaMask"] == 7
    assert body["summary"]["partner_signals"]["Uniswap"] == 4
    assert len(body["line_items"]) == 7
    assert any(item["event_type"] == "lp_deposit" for item in body["line_items"])
    assert any(item["event_type"] == "lp_withdrawal" for item in body["line_items"])
    assert any(item["event_type"] == "unstaking" for item in body["line_items"])


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
    assert "IRS: Digital Assets" in response.text


def test_export_html_from_json():
    response = client.post(
        "/reports/export-html",
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
    assert response.headers["content-type"].startswith("text/html")
    assert "Rule ID" in response.text
    assert "taxable_amount_usd" in response.text


def test_partner_catalog_endpoint():
    response = client.get("/partners")

    assert response.status_code == 200
    body = response.json()
    assert any(item["id"] == "base" and item["status"] == "active" for item in body)
    assert any(item["id"] == "self" and item["status"] == "planned" for item in body)


def test_normalization_preview_endpoint():
    response = client.post(
        "/normalize/preview",
        json={
            "jurisdiction": "US",
            "tax_year": 2025,
            "transactions": [
                {
                    "tx_id": "tx-lp",
                    "timestamp": "2025-03-20T16:00:00Z",
                    "asset": "ETH",
                    "quantity": 0.3,
                    "network": "Base",
                    "wallet_provider": "MetaMask",
                    "source_app": "Uniswap LP",
                    "event_hint": "lp deposit",
                    "proceeds_usd": 950,
                    "fee_usd": 5,
                    "counter_asset": "UNI-V2-ETH-USDC",
                    "counter_quantity": 1.2,
                    "description": "add liquidity to pool",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["event_type"] == "lp_deposit"
    assert body[0]["normalized"]["disposed_asset"] == "ETH"
    assert body[0]["normalized"]["acquired_asset"] == "UNI-V2-ETH-USDC"


def test_save_artifact_bundle(tmp_path, monkeypatch):
    from app import services

    monkeypatch.setattr(services, "ARTIFACTS_DIR", tmp_path)
    response = client.post(
        "/artifacts/save",
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
    body = response.json()
    assert tmp_path.joinpath(body["bundle_id"]).exists()
    assert tmp_path.joinpath(body["bundle_id"], "report.json").exists()
    assert any(path.suffix == ".html" for path in tmp_path.joinpath(body["bundle_id"]).iterdir())
    assert tmp_path.joinpath(body["bundle_id"], "normalization-preview.json").exists()
    assert tmp_path.joinpath(body["bundle_id"], "collaboration-log.md").exists()


def test_list_artifact_bundles(tmp_path, monkeypatch):
    from app import services

    monkeypatch.setattr(services, "ARTIFACTS_DIR", tmp_path)
    bundle_dir = tmp_path / "us-2025-20260320T000000Z"
    bundle_dir.mkdir(parents=True)
    bundle_dir.joinpath("report.json").write_text("{}", encoding="utf-8")
    bundle_dir.joinpath("normalization-preview.json").write_text("[]", encoding="utf-8")
    bundle_dir.joinpath("skynet-report-us-2025.md").write_text("# report", encoding="utf-8")

    response = client.get("/artifacts")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["bundle_id"] == "us-2025-20260320T000000Z"
    assert body[0]["report_html"].endswith(".html")
    assert body[0]["collaboration_log"].endswith("collaboration-log.md")
