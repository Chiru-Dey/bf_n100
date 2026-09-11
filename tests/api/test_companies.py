"""Integration tests for the Company API endpoints."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_list_companies_returns_all() -> None:
    response = client.get("/api/v1/companies")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 92
    assert len(data["companies"]) == 92
    assert data["companies"][0]["id"] == "ABB"


def test_list_companies_filters_by_sector() -> None:
    response = client.get("/api/v1/companies?sector=Information Technology")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 5
    for company in data["companies"]:
        assert company["broad_sector"] == "Information Technology"


def test_get_company_success() -> None:
    response = client.get("/api/v1/companies/TCS")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "TCS"
    assert data["company_name"].startswith("Tata Consultancy Services")
    assert data["roe"] is not None


def test_get_company_not_found() -> None:
    response = client.get("/api/v1/companies/INVALID")
    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"


def test_get_tearsheet_success() -> None:
    response = client.get("/api/v1/companies/TCS/tearsheet")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 50000


def test_get_tearsheet_not_found() -> None:
    response = client.get("/api/v1/companies/INVALID/tearsheet")
    assert response.status_code == 404
