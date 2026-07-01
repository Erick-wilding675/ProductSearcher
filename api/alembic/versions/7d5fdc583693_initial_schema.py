"""initial_schema

Revision ID: 7d5fdc583693
Revises: 
Create Date: 2026-06-30 22:44:10.811088

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '7d5fdc583693'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Habilita as extensôes do pgcrypto e pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Cria a tabela categories
    op.create_table(
        "categories",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )

    op.create_table(
        "category_attribute_schema",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column(
            "category_id",
            sa.UUID(),
            sa.ForeignKey("categories.id"),
            nullable=False,
        ),
        sa.Column("attribute_key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("data_type", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
    )
    
    op.create_table(
        "brands",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_brands_slug"),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),

        sa.Column(
            "category_id",
            sa.UUID(),
            sa.ForeignKey("categories.id"),
            nullable=False,
        ),

        sa.Column(
            "brand_id",
            sa.UUID(),
            sa.ForeignKey("brands.id"),
            nullable=False,
        ),

        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),

        sa.Column("search_vector", TSVECTOR()),

        sa.Column("embedding", Vector(768)),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.UniqueConstraint("slug", name="uq_products_slug"),
    )

    op.create_table(
        "product_specs",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),

        sa.Column(
            "product_id",
            sa.UUID(),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),

        sa.Column("attributes", JSONB(), nullable=False),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
    ),
    )

    op.create_table(
        "stores",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),

        sa.UniqueConstraint("slug", name="uq_stores_slug"),
    )

    op.create_table(
        "offers",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),

        sa.Column(
            "product_id",
            sa.UUID(),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),

        sa.Column(
            "store_id",
            sa.UUID(),
            sa.ForeignKey("stores.id"),
            nullable=False,
        ),

        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),

        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "price_history",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),

        sa.Column(
            "offer_id",
            sa.UUID(),
            sa.ForeignKey("offers.id"),
            nullable=False,
        ),

        sa.Column("price", sa.Numeric(), nullable=False),

        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),

        sa.Column(
            "product_id",
            sa.UUID(),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),

        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("rating", sa.Numeric(), nullable=False),
        sa.Column("rating_count", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
    )

    op.create_table(
        "searches",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("parsed_intent", JSONB(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("searches")
    op.drop_table("reviews")
    op.drop_table("price_history")
    op.drop_table("offers")
    op.drop_table("stores")
    op.drop_table("product_specs")
    op.drop_table("products")
    op.drop_table("brands")
    op.drop_table("category_attribute_schema")
    op.drop_table("categories")
