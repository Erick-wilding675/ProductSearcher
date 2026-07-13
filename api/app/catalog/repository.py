"""Repositórios do catálogo (acesso a dados atrás de interface — ADR-0003).

`CatalogRepository` é o contrato; `SqlCatalogRepository` é a implementação Postgres.
O router depende do contrato (via `get_catalog_repository`), então dá para trocar a
fonte ou usar um fake nos testes sem tocar no endpoint.
"""

from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.schemas import CategoryOut, OfferOut, ProductDetailOut
from app.catalog.tables import brands, categories, offers, product_specs, products, stores
from app.core.db import get_session


class CatalogRepository(Protocol):
    def get_categories(self) -> list[CategoryOut]: ...
    def get_product(self, product_id: str) -> ProductDetailOut | None: ...
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

    def get_product(self, product_id: str) -> ProductDetailOut | None:
        """Detalhe do produto: dados base + specs (JSONB) + ofertas com link.

        Retorna None se o id for malformado ou não existir (o router traduz em 404).
        """
        try:
            pid = UUID(product_id)
        except ValueError:
            return None

        base_stmt = (
            select(
                products.c.id,
                products.c.slug,
                products.c.name,
                products.c.model,
                products.c.description,
                categories.c.slug.label("category"),
                brands.c.name.label("brand"),
            )
            .select_from(products)
            .join(categories, categories.c.id == products.c.category_id)
            .join(brands, brands.c.id == products.c.brand_id)
            .where(products.c.id == pid)
        )
        base = self._session.execute(base_stmt).one_or_none()
        if base is None:
            return None

        specs = (
            self._session.execute(
                select(product_specs.c.attributes).where(product_specs.c.product_id == pid)
            ).scalar_one_or_none()
            or {}
        )

        offer_rows = self._session.execute(
            select(
                stores.c.name.label("store"),
                offers.c.price,
                offers.c.currency,
                offers.c.url,
            )
            .join(stores, stores.c.id == offers.c.store_id)
            .where(offers.c.product_id == pid)
            .order_by(offers.c.price)
        ).all()

        return ProductDetailOut(
            id=str(base.id),
            slug=base.slug,
            name=base.name,
            model=base.model,
            description=base.description,
            category=base.category,
            brand=base.brand,
            specs=specs,
            offers=[
                OfferOut(store=o.store, price=o.price, currency=o.currency, url=o.url)
                for o in offer_rows
            ],
        )

    def get_products_by_ids(self, ids: list[str]) -> list[dict]:
        raise NotImplementedError  # TODO Fase 3 — task "POST /compare"


def get_catalog_repository(
    session: Annotated[Session, Depends(get_session)],
) -> CatalogRepository:
    """Dependency do FastAPI: injeta a implementação SQL (uma sessão por request)."""
    return SqlCatalogRepository(session)
