"""Ranking determinístico e explicável (RF-30/31)."""
from typing import Protocol

from app.search.intent import Intent


class RankingService(Protocol):
    def rank(self, hits: list[dict], intent: Intent) -> dict: ...


class DeterministicRanking:
    """Ordenação reproduzível por critérios objetivos; retorna itens + critérios. TODO Fase 3."""

    def rank(self, hits: list[dict], intent: Intent) -> dict:
        raise NotImplementedError
