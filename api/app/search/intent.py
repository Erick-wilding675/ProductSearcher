"""Parsing de intenção.

Default determinístico (regras/regex) — princípio: o sistema funciona sem IA.
LLM pode reforçar no futuro (RF-16), atrás da mesma interface.
"""

from dataclasses import dataclass, field
import re
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
    """Parser determinístico baseado em regras e expressões regulares."""

    # Mapeia possíveis termos digitados pelo usuário para a categoria
    # utilizada internamente pela aplicação.
    _CATEGORY_KEYWORDS = {
        "notebook": ["notebook", "notebooks"],
        "headphone": ["headphone", "headphones", "fone", "fones"],
    }

    # Procura expressões como:
    # "até 5000"
    # "até R$5000"
    # "até R$ 5.000"
    # "ate R$5.000,99"
    _PRICE_PATTERN = re.compile(
        r"(?:até|ate)\s*r?\$?\s*([\d.,]+)",
        re.IGNORECASE,
    )

    def parse(self, query: str) -> Intent:
        """Extrai categoria, preço máximo e atributos de uma consulta."""

        # Normaliza o texto para tornar a busca por palavras-chave
        # independente de letras maiúsculas/minúsculas.
        normalized = query.lower().strip()

        intent = Intent(raw=query)

        # Procura a primeira categoria conhecida presente na consulta.
        for category, keywords in self._CATEGORY_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                intent.category = category
                break

        # Procura um preço máximo informado após "até" ou "ate".
        match = self._PRICE_PATTERN.search(normalized)

        if match:
            # Remove separador de milhar e converte vírgula decimal
            # para o formato esperado pelo Python.
            value = (
                match.group(1)
                .replace(".", "")
                .replace(",", ".")
            )

            # Caso o valor seja inválido, simplesmente mantém
            # price_max como None.
            try:
                intent.price_max = float(value)
            except ValueError:
                pass

        return intent