"""Pydantic models for API request and response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CompanyBase(BaseModel):
    """Base company schema with ID, name, and sector."""

    id: str = Field(..., description="Company ticker symbol")
    company_name: str = Field(..., description="Full company name")
    broad_sector: str | None = Field(None, description="Broad sector classification")


class CompanyDetail(CompanyBase):
    """Detailed company schema including latest KPIs and valuation metrics."""

    roe: float | None = Field(None, description="Latest Return on Equity (%)")
    roce: float | None = Field(
        None, description="Latest Return on Capital Employed (%)"
    )
    debt_to_equity: float | None = Field(
        None, description="Latest Debt-to-Equity ratio"
    )
    pe_ratio: float | None = Field(None, description="Latest Price-to-Earnings ratio")
    market_cap_crore: float | None = Field(
        None, description="Latest Market Capitalization (INR Crore)"
    )


class CompanyList(BaseModel):
    """Paginated list of companies."""

    count: int = Field(..., description="Total number of companies returned")
    companies: list[CompanyBase] = Field(..., description="List of company objects")
