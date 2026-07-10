"""Definição das tabelas (SQLAlchemy Core) que o worker escreve.

Espelha a migration do `api` apenas nas colunas usadas pela ingestão. Colunas
derivadas/opcionais (``search_vector`` é gerada; ``embedding`` fica nula até a IA)
ficam de fora de propósito — o worker não as escreve.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData()

categories = sa.Table(
    "categories",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("slug", sa.Text, nullable=False, unique=True),
    sa.Column("name", sa.Text, nullable=False),
)

category_attribute_schema = sa.Table(
    "category_attribute_schema",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("category_id", sa.Uuid, nullable=False),
    sa.Column("attribute_key", sa.Text, nullable=False),
    sa.Column("label", sa.Text, nullable=False),
    sa.Column("data_type", sa.Text, nullable=False),
    sa.Column("allowed_values", JSONB),
    sa.Column("unit", sa.Text),
    sa.Column("required", sa.Boolean, nullable=False),
)

brands = sa.Table(
    "brands",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("slug", sa.Text, nullable=False, unique=True),
    sa.Column("name", sa.Text, nullable=False),
)

products = sa.Table(
    "products",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("category_id", sa.Uuid, nullable=False),
    sa.Column("brand_id", sa.Uuid, nullable=False),
    sa.Column("slug", sa.Text, nullable=False, unique=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("model", sa.Text),
    sa.Column("description", sa.Text),
)

product_specs = sa.Table(
    "product_specs",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("product_id", sa.Uuid, nullable=False, unique=True),
    sa.Column("attributes", JSONB, nullable=False),
)

stores = sa.Table(
    "stores",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("slug", sa.Text, nullable=False, unique=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("url", sa.Text),
)

offers = sa.Table(
    "offers",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("product_id", sa.Uuid, nullable=False),
    sa.Column("store_id", sa.Uuid, nullable=False),
    sa.Column("price", sa.Numeric, nullable=False),
    sa.Column("currency", sa.Text, nullable=False),
    sa.Column("url", sa.Text),
)

price_history = sa.Table(
    "price_history",
    metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("offer_id", sa.Uuid, nullable=False),
    sa.Column("price", sa.Numeric, nullable=False),
)
