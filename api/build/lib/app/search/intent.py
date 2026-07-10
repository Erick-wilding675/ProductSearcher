"""Parsing de intenção.

Default determinístico (regras/regex) — princípio: o sistema funciona sem IA.
LLM pode reforçar no futuro (RF-16), atrás da mesma interface.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Intent:
    raw: str
    category: str | None = None
    price_max: float | None = None
    attributes: dict = field(default_factory=dict)


class IntentParser(Protocol):
    def parse(self, query: str) -> Intent: ...


class RuleBasedIntentParser:
    """Implementação determinística por regras. TODO Fase 3 (RF-11)."""

    def parse(self, query: str) -> Intent:
        raise NotImplementedError
