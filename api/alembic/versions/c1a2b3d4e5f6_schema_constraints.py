"""schema constraints, fk indexes and generated search_vector

Correções da Fase 2 (ver ADR-0005): unicidade que habilita upsert idempotente,
índices nas FKs, URLs opcionais e ``search_vector`` como coluna GERADA (FTS PT-BR).

Revision ID: c1a2b3d4e5f6
Revises: 71ab0046068d
Create Date: 2026-07-08 16:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: str | Sequence[str] | None = "71ab0046068d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEARCH_VECTOR_SQL = (
    "ALTER TABLE products ADD COLUMN search_vector tsvector "
    "GENERATED ALWAYS AS ("
    "to_tsvector('portuguese', "
    "coalesce(name, '') || ' ' || coalesce(model, '') || ' ' || coalesce(description, '')"
    ")) STORED"
)


def upgrade() -> None:
    # Unicidade das chaves naturais → habilita ON CONFLICT DO UPDATE (ADR-0005 D3).
    op.create_unique_constraint(
        "uq_category_attribute_schema_key",
        "category_attribute_schema",
        ["category_id", "attribute_key"],
    )
    op.create_unique_constraint("uq_product_specs_product", "product_specs", ["product_id"])
    op.create_unique_constraint("uq_offers_product_store", "offers", ["product_id", "store_id"])

    # URLs opcionais: nem toda loja/oferta do seed traz URL canônica.
    op.alter_column("stores", "url", existing_type=sa.Text(), nullable=True)
    op.alter_column("offers", "url", existing_type=sa.Text(), nullable=True)

    # Índices nas FKs (o Postgres não os cria automaticamente).
    op.create_index(
        "ix_category_attribute_schema_category_id",
        "category_attribute_schema",
        ["category_id"],
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_brand_id", "products", ["brand_id"])
    op.create_index("ix_offers_store_id", "offers", ["store_id"])
    op.create_index("ix_price_history_offer_id", "price_history", ["offer_id"])
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"])

    # search_vector: coluna GERADA e sempre coerente com name/model/description.
    op.drop_index("ix_products_search_vector", table_name="products")
    op.drop_column("products", "search_vector")
    op.execute(_SEARCH_VECTOR_SQL)
    op.create_index(
        "ix_products_search_vector",
        "products",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_products_search_vector", table_name="products")
    op.drop_column("products", "search_vector")
    op.add_column("products", sa.Column("search_vector", TSVECTOR()))
    op.create_index(
        "ix_products_search_vector",
        "products",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_index("ix_price_history_offer_id", table_name="price_history")
    op.drop_index("ix_offers_store_id", table_name="offers")
    op.drop_index("ix_products_brand_id", table_name="products")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_index(
        "ix_category_attribute_schema_category_id",
        table_name="category_attribute_schema",
    )

    op.alter_column("offers", "url", existing_type=sa.Text(), nullable=False)
    op.alter_column("stores", "url", existing_type=sa.Text(), nullable=False)

    op.drop_constraint("uq_offers_product_store", "offers", type_="unique")
    op.drop_constraint("uq_product_specs_product", "product_specs", type_="unique")
    op.drop_constraint(
        "uq_category_attribute_schema_key",
        "category_attribute_schema",
        type_="unique",
    )
