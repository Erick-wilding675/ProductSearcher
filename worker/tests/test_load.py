"""Teste de integração do `load` — idempotência do upsert.

Requer um Postgres com o schema aplicado (migrations). Sem banco alcançável, o
teste é **pulado** (o job de CI do worker não roda pytest; use localmente com
`make up` + `alembic upgrade head`). Usa slugs com prefixo único e limpa tudo ao
final para não poluir o catálogo.
"""

import os
from decimal import Decimal

import pytest
import sqlalchemy as sa

from ingestion import schema
from ingestion.load import load
from ingestion.models import (
    Category,
    NormalizedOffer,
    NormalizedProduct,
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/productsearcher"
)
PREFIX = "pytest-load-"


def _engine_or_skip() -> sa.Engine:
    try:
        engine = sa.create_engine(DATABASE_URL, future=True)
        with engine.connect() as conn:
            conn.execute(sa.select(sa.literal(1)))
            # o schema precisa existir
            conn.execute(sa.select(schema.products.c.id).limit(1))
        return engine
    except Exception as exc:  # noqa: BLE001 — qualquer falha de conexão/schema pula o teste
        pytest.skip(f"Postgres indisponível para teste de integração: {exc}")


def _category() -> Category:
    return Category.model_validate(
        {
            "slug": f"{PREFIX}cat",
            "name": "Categoria de teste",
            "attributes": [
                {"attribute_key": "ram_gb", "label": "RAM", "data_type": "number", "required": True}
            ],
        }
    )


def _product(price: str) -> NormalizedProduct:
    return NormalizedProduct(
        slug=f"{PREFIX}prod",
        name="Produto de teste",
        category_slug=f"{PREFIX}cat",
        brand_slug=f"{PREFIX}marca",
        brand_name="Marca Teste",
        specs={"ram_gb": 16},
        offers=[
            NormalizedOffer(
                store_slug=f"{PREFIX}loja", store_name="Loja Teste", price=Decimal(price)
            )
        ],
    )


def _cleanup(conn: sa.Connection) -> None:
    prod = conn.execute(
        sa.select(schema.products.c.id).where(schema.products.c.slug == f"{PREFIX}prod")
    ).scalar_one_or_none()
    if prod is not None:
        offer_ids = (
            conn.execute(sa.select(schema.offers.c.id).where(schema.offers.c.product_id == prod))
            .scalars()
            .all()
        )
        if offer_ids:
            conn.execute(
                sa.delete(schema.price_history).where(
                    schema.price_history.c.offer_id.in_(offer_ids)
                )
            )
        conn.execute(sa.delete(schema.offers).where(schema.offers.c.product_id == prod))
        conn.execute(
            sa.delete(schema.product_specs).where(schema.product_specs.c.product_id == prod)
        )
        conn.execute(sa.delete(schema.products).where(schema.products.c.id == prod))
    conn.execute(sa.delete(schema.stores).where(schema.stores.c.slug == f"{PREFIX}loja"))
    conn.execute(sa.delete(schema.brands).where(schema.brands.c.slug == f"{PREFIX}marca"))
    cat = conn.execute(
        sa.select(schema.categories.c.id).where(schema.categories.c.slug == f"{PREFIX}cat")
    ).scalar_one_or_none()
    if cat is not None:
        conn.execute(
            sa.delete(schema.category_attribute_schema).where(
                schema.category_attribute_schema.c.category_id == cat
            )
        )
        conn.execute(sa.delete(schema.categories).where(schema.categories.c.id == cat))


def test_load_idempotente_e_price_history():
    engine = _engine_or_skip()
    try:
        with engine.begin() as conn:
            _cleanup(conn)

        # 1ª e 2ª carga com o mesmo preço → idempotente
        with engine.begin() as conn:
            load(conn, [_product("3999.00")], [_category()])
        with engine.begin() as conn:
            load(conn, [_product("3999.00")], [_category()])

        with engine.connect() as conn:
            n_prod = conn.execute(
                sa.select(sa.func.count())
                .select_from(schema.products)
                .where(schema.products.c.slug == f"{PREFIX}prod")
            ).scalar_one()
            n_hist = conn.execute(
                sa.select(sa.func.count()).select_from(schema.price_history)
            ).scalar_one()
            assert n_prod == 1  # não duplicou
            hist_antes = n_hist

        # 3ª carga com preço diferente → +1 ponto de histórico
        with engine.begin() as conn:
            load(conn, [_product("3499.00")], [_category()])
        with engine.connect() as conn:
            n_hist_depois = conn.execute(
                sa.select(sa.func.count()).select_from(schema.price_history)
            ).scalar_one()
            assert n_hist_depois == hist_antes + 1
    finally:
        with engine.begin() as conn:
            _cleanup(conn)
        engine.dispose()
