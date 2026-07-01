"""Repositórios do catálogo (acesso a dados encapsulado).

TODO Fase 3: implementar contra o Postgres.
"""

from typing import Protocol


class CatalogRepository(Protocol):
    def get_categories(self) -> list[dict]: ...
    def get_product(self, product_id: str) -> dict | None: ...
    def get_products_by_ids(self, ids: list[str]) -> list[dict]: ...
