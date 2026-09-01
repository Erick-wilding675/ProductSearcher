"""Definições SQLAlchemy Core das tabelas que a API lê.

Só as colunas usadas na leitura — a migration inicial (`7d5fdc583693`) é a fonte de
verdade do schema. Novos endpoints estendem este módulo com as tabelas que precisarem.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    Computed,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

metadata = MetaData()

# Configuração de busca textual do projeto: `portuguese` + dobra de acento.
# Sempre **qualificada** — o `search_path` do Supabase não é o do Postgres do
# docker, e um nome nu resolveria diferente em cada um. Ver migration
# d2e4f6a8b0c1 para o porquê da dobra.
FTS_CONFIG = "public.portuguese_unaccent"

# Expressão da coluna gerada `search_vector` (espelha a migration d2e4f6a8b0c1).
_SEARCH_VECTOR = Computed(
    f"to_tsvector('{FTS_CONFIG}', "
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

category_attribute_schema = Table(
    "category_attribute_schema",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("category_id", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False),
    Column("attribute_key", Text, nullable=False),
    Column("label", Text, nullable=False),
    Column("data_type", Text, nullable=False),
    Column("allowed_values", JSONB),
    Column("unit", Text),
    Column("required", Boolean, nullable=False),
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
    # Vetor semântico de 768 dimensões (ADR-0005 D2, mantido pelo ADR-010 D3).
    # A coluna e o índice HNSW existem desde a migration inicial — D3 preenche
    # o valor, e por isso **não** tem migration. Nula até a carga offline rodar
    # (`python -m app.search.vector_load`); o retrieval vetorial ignora nulos.
    Column("embedding", Vector(768)),
)

product_specs = Table(
    "product_specs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id"), nullable=False),
    Column("attributes", JSONB, nullable=False),
)

searches = Table(
    "searches",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("query_text", Text, nullable=False),
    Column("parsed_intent", JSONB),
    Column("result_count", Integer, nullable=False),
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
    Column("quality_status", Text, nullable=False),
    Column("quality_reason", Text),
)
