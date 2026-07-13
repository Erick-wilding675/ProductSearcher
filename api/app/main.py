"""Ponto de entrada da API (monólito modular).

Clientes (web app e extensão) consomem esta mesma API.
Ver docs/architecture.md e ADR-0003.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.catalog.router import router as catalog_router
from app.core.config import settings
from app.core.db import get_session
from app.core.logging import configure_logging, set_request_id
from app.search.router import router as search_router

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="ProductSearcher API", version="0.1.0")

# CORS: web app (origens explícitas) + extensão de browser (via regex). Ver config.py.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Correlação por requisição: fixa o request id (header ou gerado) no contexto
    de log e o devolve em `X-Request-ID`, para o cliente amarrar suas chamadas."""
    rid = set_request_id(request.headers.get("X-Request-ID"))
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


@app.get("/health", tags=["meta"])
def health(session: Annotated[Session, Depends(get_session)]) -> dict:
    """Healthcheck: status do app e conectividade com o banco.

    Sempre responde 200; o campo `db` indica se o Postgres respondeu ("ok"/"down"),
    para a monitoração distinguir "app no ar" de "banco fora".
    """
    try:
        session.execute(text("SELECT 1"))
        db_status = "ok"
    except SQLAlchemyError:
        logger.exception("Healthcheck: falha ao consultar o banco")
        db_status = "down"
    return {"status": "ok", "ai_enabled": settings.ai_enabled, "db": db_status}


app.include_router(catalog_router)
app.include_router(search_router)
