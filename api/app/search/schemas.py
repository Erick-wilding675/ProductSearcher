"""Schemas de resposta da busca (contratos da API)."""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class RankingFactor(BaseModel):
    """Contribuição de um fator para o score de um item (RF-31).

    `applicable=False` quando o fator não faz sentido para a consulta (ex.: preço
    sem teto pedido) — nesse caso ele sai da média e o peso é redistribuído.
    """

    score: float = Field(ge=0.0, le=1.0)
    applicable: bool


class RankingCriterion(BaseModel):
    """Critério que o ranking usou, com peso e rótulo para a UI (RF-31)."""

    factor: str
    weight: float
    active: bool
    description: str


class SearchResultItem(BaseModel):
    """Um produto no resultado da busca (com o menor preço entre as ofertas)."""

    id: str
    slug: str
    name: str
    category: str
    brand: str
    min_price: Decimal | None = None
    specs: dict = Field(default_factory=dict)
    # Explicabilidade (RF-30/31): a posição do item e o porquê dela.
    score: float = 0.0
    factors: dict[str, RankingFactor] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Página de resultados: critérios do ranking + itens + metadados de paginação."""

    page: int
    page_size: int
    # Candidatos considerados (limitado por `search_candidate_pool`), não o total de
    # produtos que casam no banco: só o que entrou no pool é ranqueável e paginável.
    total: int
    criteria: list[RankingCriterion] = Field(default_factory=list)
    results: list[SearchResultItem]

class SpecOptionValue(BaseModel):
    """Um valor disponível para uma spec no pool atual de candidatos."""

    value: str | int | float | bool
    count: int = Field(ge=1)


class SpecOption(BaseModel):
    """Uma spec disponível para priorização."""

    key: str
    label: str
    values: list[SpecOptionValue]


class SpecOptionsResponse(BaseModel):
    """Specs e valores encontrados no pool atual da busca."""

    specs: list[SpecOption] = Field(default_factory=list)

class RankByOption(Enum):
    """Critério de priorização do ranking."""

    relevance = "relevance"
    price = "price"
    brand = "brand"
    spec = "spec"

class SortOption(Enum):
    """Ordenações válidas do /search (contrato explícito no OpenAPI)."""

    relevance = "relevance"
    price_asc = "price_asc"
    price_desc = "price_desc"
    name = "name"
