"""Schemas de resposta (contratos da API) do catálogo.

Separados das tabelas (Core) de propósito: aqui vive o formato público da API,
que evolui de forma independente do banco.
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class CategoryOut(BaseModel):
    """Uma categoria coberta pelo catálogo (com ao menos 1 produto)."""

    slug: str
    name: str
    product_count: int


class OfferOut(BaseModel):
    """Uma oferta do produto: onde comprar, por quanto e o link."""

    store: str
    price: Decimal  # serializado como string no JSON, preservando a precisão monetária
    currency: str
    url: str


class ProductDetailOut(BaseModel):
    """Detalhe completo do produto: specs + ofertas (RF-42)."""

    id: str
    slug: str
    name: str
    model: str | None = None
    description: str | None = None
    category: str
    brand: str
    specs: dict[str, Any] = Field(default_factory=dict)
    offers: list[OfferOut] = Field(default_factory=list)
