"""Definições SQLAlchemy Core das tabelas que a API lê.

Só as colunas usadas na leitura — a migration inicial (`7d5fdc583693`) é a fonte de
verdade do schema. Novos endpoints estendem este módulo com as tabelas que precisarem.
"""

from sqlalchemy import Column, Computed, ForeignKey, MetaData, Numeric, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

metadata = MetaData()

# Expressão da coluna gerada `search_vector` (espelha a migration c1a2b3d4e5f6).
_SEARCH_VECTOR = Computed(
    "to_tsvector('portuguese', "
    "coalesce(name, '') || ' ' || coalesce(model, '') || ' ' || coalesce(description, ''))",
    persisted=True,
)

categories = Table(
    "categories",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("slug", Text, nullable=False),
    Column("name", Text, nullable=False),
)

brands = Table(
    "brands",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("slug", Text, nullable=False),
    Column("name", Text, nullable=False),
)

stores = Table(
    "stores",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("slug", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("url", Text),
)

products = Table(
    "products",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("category_id", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False),
    Column("brand_id", UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False),
    Column("slug", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("model", Text),
    Column("description", Text),
    Column("search_vector", TSVECTOR, _SEARCH_VECTOR),
)

product_specs = Table(
    "product_specs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id"), nullable=False),
    Column("attributes", JSONB, nullable=False),
)

offers = Table(
    "offers",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id"), nullable=False),
    Column("store_id", UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False),
    Column("price", Numeric, nullable=False),
    Column("currency", Text, nullable=False),
    Column("url", Text, nullable=False),
)
