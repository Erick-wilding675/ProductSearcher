"""Camada de IA — opcional e plugável. O caminho crítico nunca depende dela.

Com AI_ENABLED=false, usa-se a implementação determinística.
"""

from typing import Protocol


class AIService(Protocol):
    def explain(self, context: dict) -> str: ...


class DeterministicAIService:
    """Fallback sem LLM: explicação a partir de regras/template. TODO Fase 3."""

    def explain(self, context: dict) -> str:
        raise NotImplementedError


class LLMAIService:
    """Explicação via LLM (opcional, requer chave de API). TODO Fase 6 (RF-61)."""

    def explain(self, context: dict) -> str:
        raise NotImplementedError
