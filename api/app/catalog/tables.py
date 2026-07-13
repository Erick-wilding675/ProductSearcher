"""Definições SQLAlchemy Core das tabelas que a API lê.

Só as colunas usadas na leitura — a migration inicial (`7d5fdc583693`) é a fonte de
verdade do schema. Novos endpoints estendem este módulo com as tabelas que precisarem.
"""

from sqlalchemy import Column, ForeignKey, MetaData, Table, Text
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData()

categories = Table(
    "categories",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("slug", Text, nullable=False),
    Column("name", Text, nullable=False),
)

products = Table(
    "products",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("category_id", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False),
)
