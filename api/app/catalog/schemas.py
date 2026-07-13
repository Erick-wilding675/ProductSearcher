"""Schemas de resposta (contratos da API) do catálogo.

Separados das tabelas (Core) de propósito: aqui vive o formato público da API,
que evolui de forma independente do banco.
"""

from pydantic import BaseModel


class CategoryOut(BaseModel):
    """Uma categoria coberta pelo catálogo (com ao menos 1 produto)."""

    slug: str
    name: str
    product_count: int
