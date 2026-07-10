"""add search indexes

Revision ID: 71ab0046068d
Revises: 7d5fdc583693
Create Date: 2026-07-08 15:37:03.701667

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "71ab0046068d"
down_revision: str | Sequence[str] | None = "7d5fdc583693"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create search indexes."""

    # Full Text Search (tsvector)
    op.create_index(
        "ix_products_search_vector",
        "products",
        ["search_vector"],
        postgresql_using="gin",
    )

    # JSONB
    op.create_index(
        "ix_product_specs_attributes",
        "product_specs",
        ["attributes"],
        postgresql_using="gin",
        postgresql_ops={
            "attributes": "jsonb_path_ops",
        },
    )

    # Vector similarity (pgvector)
    op.execute("""
        CREATE INDEX ix_products_embedding
        ON products
        USING hnsw (embedding vector_cosine_ops);
    """)


def downgrade() -> None:
    """Drop search indexes."""

    op.drop_index(
        "ix_products_embedding",
        table_name="products",
    )

    op.drop_index(
        "ix_product_specs_attributes",
        table_name="product_specs",
    )

    op.drop_index(
        "ix_products_search_vector",
        table_name="products",
    )
