"""Interfaces de busca — permitem trocar o datastore sem reescrever o core (ADR-0002).

Camada de **retrieval** do pipeline de busca (ADR-0007):

    query --> IntentParser --> Intent --> SearchProvider.search() --> hits
                                                                   |
                                          RankingService.rank(hits, intent)

O `SearchProvider` recupera *candidatos* (filtros duros + score de relevância textual);
a ordenação final e explicável fica no `RankingService`. Isso mantém retrieval e
ranking desacoplados e testáveis em separado.

MVP: `FtsSearchProvider` (Postgres FTS). Evolução: pgvector/OpenSearch/Qdrant atrás
da mesma interface, sem tocar no core.
"""

from decimal import Decimal
from typing import Annotated, Protocol

from fastapi import Depends
from sqlalchemy import and_, cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.catalog.tables import brands, categories, offers, product_specs, products
from app.core.config import settings
from app.core.db import get_session
from app.search.intent import Intent


class SearchProvider(Protocol):
    def search(
        self,
        intent: Intent,
        filters: dict,
        page: int = 1,
    ) -> list[dict]: ...


class VectorProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...

    def search(
        self,
        vector: list[float],
        k: int = 10,
    ) -> list[str]: ...


class FtsSearchProvider:
    """Retrieval textual via Postgres Full-Text Search (default do MVP, RF-10).

    Aplica os filtros duros (categoria, marca, preço-teto) e devolve candidatos com o
    score bruto de relevância (`fts_rank` = `ts_rank`), que o `RankingService` usa como
    um dos critérios. Não ordena para o usuário final nem pagina — isso é do ranking.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        intent: Intent,
        filters: dict | None = None,
        page: int = 1,
    ) -> list[dict]:
        filters = filters or {}

        # Intent tem prioridade sobre filters explícitos; filters cobre o que o parser
        # não extrai (ex.: marca escolhida na UI).
        category = intent.category or filters.get("category")
        brand = filters.get("brand")

        price_max = (
            intent.price_max
            if intent.price_max is not None
            else filters.get("price_max")
        )

        attributes = intent.attributes or filters.get("attributes")

        # `intent.text` (e não `raw`): o texto já sem as partes que viraram filtro.
        # `plainto_tsquery` combina os termos com AND — "até R$5000" no texto exigiria
        # "ate"/"r"/"5000" no produto e zeraria o resultado.
        texto = intent.text or intent.raw
        tsquery = (
            func.plainto_tsquery("portuguese", texto)
            if texto
            else None
        )

        min_price = func.min(offers.c.price)

        conditions = []

        if tsquery is not None:
            conditions.append(
                products.c.search_vector.op("@@")(tsquery)
            )

        if category:
            conditions.append(
                categories.c.slug == category
            )

        if brand:
            conditions.append(
                brands.c.slug == brand
            )

        # Filtro estruturado por atributos (RF-12): containment JSONB (@>),
        # servido pelo índice GIN jsonb_path_ops.
        if attributes:
            conditions.append(
                product_specs.c.attributes.op("@>")(
                    cast(attributes, JSONB)
                )
            )

        rank_expr = (
            func.ts_rank(
                products.c.search_vector,
                tsquery,
            )
            if tsquery is not None
            else literal(0.0)
        )

        stmt = (
            select(
                products.c.id,
                products.c.slug,
                products.c.name,
                categories.c.slug.label("category"),
                brands.c.name.label("brand"),
                brands.c.slug.label("brand_slug"),
                min_price.label("min_price"),
                rank_expr.label("fts_rank"),
                product_specs.c.attributes.label("attributes"),
            )
            .select_from(products)
            .join(
                categories,
                categories.c.id == products.c.category_id,
            )
            .join(
                brands,
                brands.c.id == products.c.brand_id,
            )
            .outerjoin(
                offers,
                offers.c.product_id == products.c.id,
            )
            # LEFT JOIN: produto sem specs continua sendo candidato.
            # É 1:1 com produto (uq_product_specs_product), então não
            # infla as linhas do agrupamento.
            .outerjoin(
                product_specs,
                product_specs.c.product_id == products.c.id,
            )
            .group_by(
                products.c.id,
                products.c.slug,
                products.c.name,
                categories.c.slug,
                brands.c.name,
                brands.c.slug,
                product_specs.c.attributes,
            )
        )

        if conditions:
            stmt = stmt.where(
                and_(*conditions)
            )

        if price_max is not None:
            stmt = stmt.having(
                min_price <= price_max
            )

        stmt = stmt.order_by(
            func.coalesce(
                rank_expr,
                0.0,
            ).desc()
        ).limit(
            settings.search_candidate_pool
        )

        rows = self._session.execute(stmt).all()

        return [
            _row_to_hit(row)
            for row in rows
        ]


def _row_to_hit(row) -> dict:
    """Converte a linha do retrieval no `hit` que o RankingService consome."""

    min_price = row.min_price

    if isinstance(min_price, Decimal):
        min_price = float(min_price)

    return {
        "id": str(row.id),
        "slug": row.slug,
        "name": row.name,
        "category": row.category,
        "brand": row.brand,
        "brand_slug": row.brand_slug,
        "min_price": min_price,
        "fts_rank": float(row.fts_rank or 0.0),
        # O ranking usa isto para o fator de atributos; sem a chave,
        # o fator ficava sempre com score 0 e só diluía o score final.
        "attributes": row.attributes or {},
    }


def get_fts_search_provider(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
) -> SearchProvider:
    """Dependency do FastAPI: injeta o provider FTS (uma sessão por request)."""

    return FtsSearchProvider(session)