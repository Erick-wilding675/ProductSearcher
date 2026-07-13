"""Repositórios do catálogo (acesso a dados atrás de interface — ADR-0003).

`CatalogRepository` é o contrato; `SqlCatalogRepository` é a implementação Postgres.
O router depende do contrato (via `get_catalog_repository`), então dá para trocar a
fonte ou usar um fake nos testes sem tocar no endpoint.
"""

from typing import Annotated, Protocol

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.schemas import CategoryOut
from app.catalog.tables import categories, products
from app.core.db import get_session


class CatalogRepository(Protocol):
    def get_categories(self) -> list[CategoryOut]: ...
    def get_product(self, product_id: str) -> dict | None: ...
    def get_products_by_ids(self, ids: list[str]) -> list[dict]: ...


class SqlCatalogRepository:
    """Implementação do `CatalogRepository` sobre o Postgres."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_categories(self) -> list[CategoryOut]:
        """Categorias COBERTAS: só as que têm ao menos 1 produto (INNER JOIN).

        Uma única query agregada (GROUP BY sobre o FK indexado), ordenada por nome
        para resposta determinística.
        """
        stmt = (
            select(
                categories.c.slug,
                categories.c.name,
                func.count(products.c.id).label("product_count"),
            )
            .join(products, products.c.category_id == categories.c.id)
            .group_by(categories.c.id, categories.c.slug, categories.c.name)
            .order_by(categories.c.name)
        )
        rows = self._session.execute(stmt).all()
        return [
            CategoryOut(slug=row.slug, name=row.name, product_count=row.product_count)
            for row in rows
        ]

    def get_product(self, product_id: str) -> dict | None:
        raise NotImplementedError  # TODO Fase 3 — task "GET /products/{id}"

    def get_products_by_ids(self, ids: list[str]) -> list[dict]:
        raise NotImplementedError  # TODO Fase 3 — task "POST /compare"


def get_catalog_repository(
    session: Annotated[Session, Depends(get_session)],
) -> CatalogRepository:
    """Dependency do FastAPI: injeta a implementação SQL (uma sessão por request)."""
    return SqlCatalogRepository(session)
