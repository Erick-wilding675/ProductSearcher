"""Adiciona classificação de qualidade às ofertas.

Ofertas suspeitas são preservadas para auditoria, mas podem ser excluídas das
consultas de preço, ranking e comparação.

Revision ID: e4f6a8b0c2d3
Revises: d2e4f6a8b0c1
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f6a8b0c2d3"
down_revision: str | Sequence[str] | None = "d2e4f6a8b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "offers",
        sa.Column(
            "quality_status",
            sa.Text(),
            nullable=False,
            server_default="valid",
        ),
    )

    op.add_column(
        "offers",
        sa.Column(
            "quality_reason",
            sa.Text(),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_offers_quality_status",
        "offers",
        "quality_status IN ('valid', 'rejected')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_offers_quality_status",
        "offers",
        type_="check",
    )
    op.drop_column("offers", "quality_reason")
    op.drop_column("offers", "quality_status")