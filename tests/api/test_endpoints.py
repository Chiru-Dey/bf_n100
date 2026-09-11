"""Integration tests for the remaining API endpoints."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_screener_valid_filter() -> None:
    response = client.get("/api/v1/screener?min_roe=15")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    for company in data:
        assert company["return_on_equity_pct"] >= 15.0


def test_sectors_list() -> None:
    response = client.get("/api/v1/sectors")
    assert response.status_code == 200
    data = response.json()
    # We verified earlier there are exactly 10 broad sectors in the DB
    assert len(data) == 10


def test_sector_companies_not_found() -> None:
    response = client.get("/api/v1/sectors/InvalidSector/companies")
    assert response.status_code == 404


def test_peers_group() -> None:
    response = client.get("/api/v1/peers/IT Services")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0


def test_market_cap() -> None:
    response = client.get("/api/v1/market-cap/TCS")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert "pe_ratio" in data[0]


def test_portfolio_stats() -> None:
    response = client.get("/api/v1/portfolio/stats")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0


def test_documents() -> None:
    # TCS might not have documents in the simulated DB, so we just check it doesn't 500
    response = client.get("/api/v1/companies/TCS/documents")
    assert response.status_code in (200, 404)
