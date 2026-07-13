"""Comparação de produtos: contratos + a lógica pura de alinhamento.

`build_comparison` é uma função pura (sem banco), fácil de testar: recebe os
produtos já validados e devolve os atributos alinhados, marcando as diferenças.
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.catalog.schemas import CompareProduct


class CompareRequest(BaseModel):
    """Corpo do POST /compare: 2 a 4 ids de produto (validado pelo Pydantic)."""

    product_ids: list[str] = Field(min_length=2, max_length=4)

    @field_validator("product_ids")
    @classmethod
    def _sem_duplicados(cls, ids: list[str]) -> list[str]:
        if len(set(ids)) != len(ids):
            raise ValueError("product_ids não pode ter ids repetidos")
        return ids


class ComparedAttribute(BaseModel):
    """Um atributo alinhado: o valor de cada produto (na ordem) e se eles diferem."""

    key: str
    values: list[Any]
    differ: bool


class CompareProductInfo(BaseModel):
    id: str
    name: str
    min_price: Decimal | None = None  # menor preço entre as ofertas


class CompareOut(BaseModel):
    """Resultado da comparação: categoria, produtos, melhor valor e atributos alinhados."""

    category: str
    products: list[CompareProductInfo]
    best_value_id: str | None = None  # id do mais barato (RF-21); None em empate/sem preço
    attributes: list[ComparedAttribute]


def build_comparison(produtos: list[CompareProduct]) -> CompareOut:
    """Monta a comparação alinhada.

    Assume produtos já validados (2-4, mesma categoria). Para cada atributo presente
    em algum produto, junta os valores na ordem dos produtos e marca `differ` quando
    nem todos são iguais (ausência conta como valor diferente).

    A comparação de `differ` é feita por igualdade ao primeiro valor (não por `set`),
    para tolerar valores não-hasháveis que o JSONB permite (listas/dicts), sem quebrar.
    """
    keys = sorted({key for produto in produtos for key in produto.specs})
    attributes = []
    for key in keys:
        values = [produto.specs.get(key) for produto in produtos]
        attributes.append(
            ComparedAttribute(
                key=key,
                values=values,
                differ=any(value != values[0] for value in values[1:]),
            )
        )
    return CompareOut(
        category=produtos[0].category,
        products=[
            CompareProductInfo(id=p.id, name=p.name, min_price=p.min_price) for p in produtos
        ],
        best_value_id=_best_value_id(produtos),
        attributes=attributes,
    )


def _best_value_id(produtos: list[CompareProduct]) -> str | None:
    """Id do produto de menor preço (RF-21). None se ninguém tem preço ou há empate
    no menor — evita eleger um "melhor valor" arbitrário."""
    precificados = [(p.id, p.min_price) for p in produtos if p.min_price is not None]
    if not precificados:
        return None
    menor = min(preco for _, preco in precificados)
    mais_baratos = [pid for pid, preco in precificados if preco == menor]
    return mais_baratos[0] if len(mais_baratos) == 1 else None
