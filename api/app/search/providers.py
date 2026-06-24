"""Interfaces de busca — permitem trocar o datastore sem reescrever o core (ADR-0002).

MVP: FtsSearchProvider (Postgres FTS) + pgvector via VectorProvider.
Evolução: OpenSearch / Qdrant atrás das mesmas interfaces.
"""

from typing import Protocol

from app.search.intent import Intent


class SearchProvider(Protocol):
    def search(self, intent: Intent, filters: dict, page: int = 1) -> list[dict]: ...


class VectorProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def search(self, vector: list[float], k: int = 10) -> list[str]: ...


class FtsSearchProvider:
    """Busca textual via Postgres Full-Text Search (default do MVP). TODO Fase 3 (RF-10)."""

    def search(self, intent: Intent, filters: dict, page: int = 1) -> list[dict]:
        raise NotImplementedError
