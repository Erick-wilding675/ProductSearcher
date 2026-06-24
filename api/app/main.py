"""Ponto de entrada da API (monólito modular).

Clientes (web app e extensão) consomem esta mesma API.
Ver docs/architecture.md e ADR-0003.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.catalog.router import router as catalog_router
from app.search.router import router as search_router

configure_logging()

app = FastAPI(title="ProductSearcher API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Healthcheck (GET /health)."""
    return {"status": "ok", "ai_enabled": settings.ai_enabled}


app.include_router(catalog_router)
app.include_router(search_router)
