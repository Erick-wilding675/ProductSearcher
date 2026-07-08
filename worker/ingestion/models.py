"""Modelos crus da ingestão — o produto como a fonte entrega, antes da normalização.

Ver ADR-0001 (aquisição de dados) e ADR-0005 (decisões da Fase 2).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    """Uma regra do category_attribute_schema (ADR-005 D4)."""

    attribute_key: str
    label: str
    data_type: str  # "text" | "number" | "boolean" | "enum"
    unit: str | None = None
    required: bool = False
    allowed_values: list[str] | None = None  # só para enum
