"""Comparação de produtos: contratos + a lógica pura de alinhamento.

`build_comparison` é uma função pura (sem banco), fácil de testar: recebe os
produtos já validados e devolve os atributos alinhados, marcando as diferenças.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.catalog.schemas import CompareProduct


class CompareRequest(BaseModel):
    """Corpo do POST /compare: 2 a 4 ids de produto (validado pelo Pydantic)."""

    product_ids: list[str] = Field(min_length=2, max_length=4)


class ComparedAttribute(BaseModel):
    """Um atributo alinhado: o valor de cada produto (na ordem) e se eles diferem."""

    key: str
    values: list[Any]
    differ: bool


class CompareProductInfo(BaseModel):
    id: str
    name: str


class CompareOut(BaseModel):
    """Resultado da comparação: categoria, produtos e os atributos alinhados."""

    category: str
    products: list[CompareProductInfo]
    attributes: list[ComparedAttribute]


def build_comparison(produtos: list[CompareProduct]) -> CompareOut:
    """Monta a comparação alinhada.

    Assume produtos já validados (2-4, mesma categoria). Para cada atributo presente
    em algum produto, junta os valores na ordem dos produtos e marca `differ` quando
    nem todos são iguais (ausência conta como valor diferente).
    """
    keys = sorted({key for produto in produtos for key in produto.specs})
    attributes = [
        ComparedAttribute(
            key=key,
            values=[produto.specs.get(key) for produto in produtos],
            differ=len({produto.specs.get(key) for produto in produtos}) > 1,
        )
        for key in keys
    ]
    return CompareOut(
        category=produtos[0].category,
        products=[CompareProductInfo(id=p.id, name=p.name) for p in produtos],
        attributes=attributes,
    )
