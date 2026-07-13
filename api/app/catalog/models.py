"""Camada de modelo do catálogo — ponto único de referência.

Decisão de arquitetura (ver ADR-0003 e `tables.py`): o catálogo usa **SQLAlchemy
Core** (tabelas declaradas em `tables.py`), não ORM declarativo. A migration inicial
(`7d5fdc583693`) é a fonte de verdade do schema; `tables.py` espelha só as colunas que
a API lê. Não há classes ORM mapeadas — evita duplicar o schema e mantém o acoplamento
com o banco explícito e enxuto.

Este módulo reexporta, num só lugar, os dois lados do "modelo" do catálogo:

- **Tabelas (persistência)**: estrutura física lida pelos repositórios.
- **Schemas (contrato público)**: formato de saída da API (Pydantic), que evolui
  independentemente do banco.

Assim, `from app.catalog import models` dá uma visão coesa do domínio sem que o
restante do código precise saber se a persistência é Core, ORM ou outra fonte.
"""

from app.catalog.schemas import (
    CategoryOut,
    CompareProduct,
    OfferOut,
    ProductDetailOut,
)
from app.catalog.tables import (
    brands,
    categories,
    metadata,
    offers,
    product_specs,
    products,
    stores,
)

# Tabelas (SQLAlchemy Core) — persistência.
TABLES = (categories, brands, stores, products, product_specs, offers)

# Schemas (Pydantic) — contrato público da API.
SCHEMAS = (CategoryOut, OfferOut, ProductDetailOut, CompareProduct)

__all__ = [
    # persistência
    "metadata",
    "categories",
    "brands",
    "stores",
    "products",
    "product_specs",
    "offers",
    "TABLES",
    # contrato público
    "CategoryOut",
    "OfferOut",
    "ProductDetailOut",
    "CompareProduct",
    "SCHEMAS",
]
