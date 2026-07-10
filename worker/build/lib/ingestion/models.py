"""Modelos da ingestão.

Fluxo: a fonte entrega `RawProduct` (cru) → `normalize` produz `NormalizedProduct`
(canônico) → `validate` confere specs → `load` persiste. Ver ADR-0001 e ADR-0005.
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Cru (como a fonte entrega)                                                   #
# --------------------------------------------------------------------------- #


class RawOffer(BaseModel):
    """Oferta como vem da fonte, ainda não normalizada."""

    model_config = ConfigDict(extra="allow")

    store: str | None = None
    price: str | float | None = None  # cru: pode chegar "R$ 3.999,00"
    currency: str | None = None
    url: str | None = None


class RawProduct(BaseModel):
    """Produto cru de qualquer fonte, antes da normalização (ADR-0001)."""

    model_config = ConfigDict(extra="allow")

    source: str  # procedência: "seed" (hoje), "apify" (futuro)
    external_id: str | None = None  # id na fonte → idempotência futura
    name: str
    brand: str | None = None
    category: str  # slug/nome cru da categoria
    model: str | None = None
    description: str | None = None
    specs: dict[str, Any] = Field(default_factory=dict)  # atributos crus, sem validar
    offers: list[RawOffer] = Field(default_factory=list)


class AttributeSpec(BaseModel):
    """Uma regra do category_attribute_schema (ADR-0005 D4)."""

    attribute_key: str
    label: str
    data_type: str  # "text" | "number" | "boolean" | "enum"
    unit: str | None = None
    required: bool = False
    allowed_values: list[str] | None = None  # só para enum


class Category(BaseModel):
    """Categoria + seu schema de atributos, como definido no seed."""

    slug: str
    name: str
    attributes: list[AttributeSpec] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Canônico (pós-normalização)                                                  #
# --------------------------------------------------------------------------- #


class NormalizedOffer(BaseModel):
    """Oferta pronta para persistir (preço já parseado)."""

    store_slug: str
    store_name: str
    price: Decimal
    currency: str = "BRL"
    url: str | None = None


class NormalizedProduct(BaseModel):
    """Produto canônico, pronto para validação de specs e carga."""

    slug: str  # chave natural de upsert (ADR-0005 D3)
    name: str
    category_slug: str
    brand_slug: str
    brand_name: str
    model: str | None = None
    description: str | None = None
    specs: dict[str, Any] = Field(default_factory=dict)
    offers: list[NormalizedOffer] = Field(default_factory=list)


class Rejection(BaseModel):
    """Um produto que não entrou no catálogo, com o(s) motivo(s) (ADR-0005 D6)."""

    name: str
    reasons: list[str]
