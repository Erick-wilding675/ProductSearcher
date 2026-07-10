"""Carga idempotente no Postgres (RF-72, ADR-0005 D3).

Estratégia: upsert por chave natural (``slug`` em products/brands/categories/stores;
``product_id`` em specs; ``(product_id, store_id)`` em offers) via
``INSERT ... ON CONFLICT DO UPDATE``. Os UUIDs são gerados na aplicação, então uma
inserção sempre traz um ``id`` novo, mas em conflito o registro existente é
preservado. `price_history` só ganha um ponto quando o preço realmente muda —
rodar o seed N vezes converge ao mesmo estado.
"""

import logging
from collections.abc import Iterable, Sequence
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from ingestion import schema
from ingestion.models import Category, NormalizedProduct

logger = logging.getLogger(__name__)


def _upsert(
    conn: Connection,
    table: sa.Table,
    values: dict,
    conflict_cols: Sequence[str],
    update_cols: Sequence[str],
) -> UUID:
    """Upsert de uma linha; devolve o ``id`` (novo ou já existente)."""
    stmt = pg_insert(table).values(id=uuid4(), **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=list(conflict_cols),
        set_={col: stmt.excluded[col] for col in update_cols},
    ).returning(table.c.id)
    return conn.execute(stmt).scalar_one()


def _load_categories(conn: Connection, categories: Iterable[Category]) -> dict[str, UUID]:
    """Upsert das categorias e do seu `category_attribute_schema`."""
    ids: dict[str, UUID] = {}
    for category in categories:
        category_id = _upsert(
            conn,
            schema.categories,
            {"slug": category.slug, "name": category.name},
            ["slug"],
            ["name"],
        )
        ids[category.slug] = category_id
        for attr in category.attributes:
            _upsert(
                conn,
                schema.category_attribute_schema,
                {
                    "category_id": category_id,
                    "attribute_key": attr.attribute_key,
                    "label": attr.label,
                    "data_type": attr.data_type,
                    "allowed_values": attr.allowed_values,
                    "unit": attr.unit,
                    "required": attr.required,
                },
                ["category_id", "attribute_key"],
                ["label", "data_type", "allowed_values", "unit", "required"],
            )
    return ids


def _load_offers(conn: Connection, product_id: UUID, product: NormalizedProduct) -> tuple[int, int]:
    """Upsert das ofertas de um produto; registra histórico só em mudança de preço."""
    store_cache: dict[str, UUID] = {}
    offers_count = price_points = 0

    for offer in product.offers:
        store_id = store_cache.get(offer.store_slug)
        if store_id is None:
            store_id = _upsert(
                conn,
                schema.stores,
                {"slug": offer.store_slug, "name": offer.store_name, "url": None},
                ["slug"],
                ["name"],
            )
            store_cache[offer.store_slug] = store_id

        previous = conn.execute(
            sa.select(schema.offers.c.price).where(
                schema.offers.c.product_id == product_id,
                schema.offers.c.store_id == store_id,
            )
        ).scalar_one_or_none()

        offer_id = _upsert(
            conn,
            schema.offers,
            {
                "product_id": product_id,
                "store_id": store_id,
                "price": offer.price,
                "currency": offer.currency,
                "url": offer.url,
            },
            ["product_id", "store_id"],
            ["price", "currency", "url"],
        )
        offers_count += 1

        if previous is None or Decimal(previous) != offer.price:
            conn.execute(
                pg_insert(schema.price_history).values(
                    id=uuid4(), offer_id=offer_id, price=offer.price
                )
            )
            price_points += 1

    return offers_count, price_points


def load(
    conn: Connection,
    products: Iterable[NormalizedProduct],
    categories: Iterable[Category],
) -> dict[str, int]:
    """Persiste categorias e produtos (com specs e ofertas) de forma idempotente."""
    category_ids = _load_categories(conn, categories)

    brand_ids: dict[str, UUID] = {}
    counts = {"categories": len(category_ids), "products": 0, "offers": 0, "price_points": 0}

    for product in products:
        brand_id = brand_ids.get(product.brand_slug)
        if brand_id is None:
            brand_id = _upsert(
                conn,
                schema.brands,
                {"slug": product.brand_slug, "name": product.brand_name},
                ["slug"],
                ["name"],
            )
            brand_ids[product.brand_slug] = brand_id

        category_id = category_ids.get(product.category_slug)
        if category_id is None:  # defensivo: validate() já garante categoria conhecida
            logger.warning("Categoria sem id para %s: %s", product.name, product.category_slug)
            continue

        product_id = _upsert(
            conn,
            schema.products,
            {
                "category_id": category_id,
                "brand_id": brand_id,
                "slug": product.slug,
                "name": product.name,
                "model": product.model,
                "description": product.description,
            },
            ["slug"],
            ["category_id", "brand_id", "name", "model", "description"],
        )
        _upsert(
            conn,
            schema.product_specs,
            {"product_id": product_id, "attributes": product.specs},
            ["product_id"],
            ["attributes"],
        )
        counts["products"] += 1

        offers_count, price_points = _load_offers(conn, product_id, product)
        counts["offers"] += offers_count
        counts["price_points"] += price_points

    return counts
