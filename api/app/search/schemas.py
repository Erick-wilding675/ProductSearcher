"""Schemas de resposta da busca (contratos da API)."""

from decimal import Decimal

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    """Um produto no resultado da busca (com o menor preço entre as ofertas)."""

    id: str
    slug: str
    name: str
    category: str
    brand: str
    min_price: Decimal | None = None


class SearchResponse(BaseModel):
    """Página de resultados: itens + metadados de paginação."""

    page: int
    page_size: int
    total: int
    results: list[SearchResultItem]
