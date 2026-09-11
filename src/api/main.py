"""FastAPI application entry point with middleware and router registration."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import (
    companies,
    documents,
    health,
    peers,
    portfolio,
    screener,
    sectors,
    valuation,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log server startup and shutdown."""
    logger.info("Starting Nifty 100 API Server")
    yield
    logger.info("Shutting down Nifty 100 API Server")


app = FastAPI(
    title="Nifty 100 Financial Intelligence API",
    description="REST API for the Nifty 100 Financial Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log method, path, status, and response time for every request."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        "method=%s path=%s status=%s time=%.3fs",
        request.method,
        request.url.path,
        response.status_code,
        process_time,
    )
    return response


app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(companies.router, prefix="/api/v1", tags=["Companies"])
app.include_router(screener.router, prefix="/api/v1", tags=["Screener"])
app.include_router(sectors.router, prefix="/api/v1", tags=["Sectors"])
app.include_router(peers.router, prefix="/api/v1", tags=["Peers"])
app.include_router(valuation.router, prefix="/api/v1", tags=["Valuation"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["Portfolio"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
