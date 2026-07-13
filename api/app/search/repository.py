"""Repositório de busca: FTS (PT-BR) + filtros + ordenação + paginação.

Fica atrás de interface (`SearchRepository`), como o catálogo — o router não vê SQL,
e nos testes dá para trocar por um fake.
"""

from typing import Annotated, Protocol

from fastapi import Depends
from sqlalchemy import and_, func, nulls_last, select
from sqlalchemy.orm import Session

from app.catalog.tables import brands, categories, offers, products
from app.core.db import get_session
from app.search.schemas import SearchResponse, SearchResultItem

PAGE_SIZE = 20


class SearchRepository(Protocol):
    def search(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        price_max: float | None = None,
        brand: str | None = None,
        sort: str = "relevance",
        page: int = 1,
    ) -> SearchResponse: ...


class SqlSearchRepository:
    """Busca sobre o Postgres: FTS no `search_vector` + filtros por join/agregação."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        price_max: float | None = None,
        brand: str | None = None,
        sort: str = "relevance",
        page: int = 1,
    ) -> SearchResponse:
        page = max(page, 1)
        min_price = func.min(offers.c.price)
        tsquery = func.plainto_tsquery("portuguese", q) if q else None

        conditions = []
        if tsquery is not None:
            conditions.append(products.c.search_vector.op("@@")(tsquery))
        if category:
            conditions.append(categories.c.slug == category)
        if brand:
            conditions.append(brands.c.slug == brand)

        base = (
            select(
                products.c.id,
                products.c.slug,
                products.c.name,
                categories.c.slug.label("category"),
                brands.c.name.label("brand"),
                min_price.label("min_price"),
            )
            .select_from(products)
            .join(categories, categories.c.id == products.c.category_id)
            .join(brands, brands.c.id == products.c.brand_id)
            .outerjoin(offers, offers.c.product_id == products.c.id)
            .group_by(
                products.c.id,
                products.c.slug,
                products.c.name,
                categories.c.slug,
                brands.c.name,
            )
        )
        if conditions:
            base = base.where(and_(*conditions))
        if price_max is not None:
            base = base.having(min_price <= price_max)

        # total = quantos produtos casam (antes de ordenar/paginar)
        total = self._session.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()

        paged = (
            base.order_by(*_order_by(sort, tsquery, min_price))
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        )
        rows = self._session.execute(paged).all()

        results = [
            SearchResultItem(
                id=str(row.id),
                slug=row.slug,
                name=row.name,
                category=row.category,
                brand=row.brand,
                min_price=row.min_price,
            )
            for row in rows
        ]
        return SearchResponse(page=page, page_size=PAGE_SIZE, total=total, results=results)


def _order_by(sort: str, tsquery, min_price):
    """Traduz o `sort` do request em ORDER BY (default: relevância)."""
    if sort == "price_asc":
        return [nulls_last(min_price.asc())]
    if sort == "price_desc":
        return [nulls_last(min_price.desc())]
    if sort == "name":
        return [products.c.name.asc()]
    if tsquery is not None:  # relevância só faz sentido quando há texto de busca
        return [func.ts_rank(products.c.search_vector, tsquery).desc(), products.c.name.asc()]
    return [products.c.name.asc()]


def get_search_repository(
    session: Annotated[Session, Depends(get_session)],
) -> SearchRepository:
    """Dependency do FastAPI: injeta a implementação SQL da busca."""
    return SqlSearchRepository(session)
