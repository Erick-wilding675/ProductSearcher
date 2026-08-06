"""Parsing de intenção.

Default determinístico (regras/regex) — princípio: o sistema funciona sem IA.
LLM pode reforçar no futuro (RF-16), atrás da mesma interface.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Intent:
    """Consulta interpretada: o texto que sobra para o FTS + os filtros estruturados.

    `raw` é o que o usuário digitou (preservado para log/UI); `text` é o resíduo
    **depois** de extrair as partes estruturadas, e é ele que alimenta o FTS.

    A distinção não é cosmética: `plainto_tsquery` combina os termos com **AND**, então
    deixar "até R$5000" no texto exige que "ate", "r" e "5000" apareçam no produto —
    e a busca devolve zero. O preço vira filtro; o texto segue sem ele.
    """

    raw: str
    category: str | None = None
    price_max: float | None = None
    attributes: dict = field(default_factory=dict)
    text: str = ""

    def __post_init__(self) -> None:
        # Sem parser (ex.: Intent montado à mão nos testes), o texto é a query crua.
        if not self.text:
            self.text = self.raw


class IntentParser(Protocol):
    def parse(self, query: str) -> Intent: ...


class RuleBasedIntentParser:
    """Parser determinístico baseado em regras e expressões regulares."""

    # Mapeia os termos digitados pelo usuário para o **slug de categoria do
    # catálogo** (`categories.slug`). Precisa bater exatamente com o seed: o
    # `SearchProvider` filtra por `categories.slug == intent.category`, então um
    # slug inventado aqui vira silenciosamente zero resultado.
    _CATEGORY_KEYWORDS = {
        "notebooks": ["notebook", "notebooks", "laptop", "laptops", "ultrabook"],
        "headphones": [
            "headphone",
            "headphones",
            "headset",
            "fone",
            "fones",
            "earbud",
            "earbuds",
        ],
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

    # RAM só é reconhecida quando o número está adjacente à palavra "ram" — sem isso,
    # "512gb ssd" seria lido como memória.
    _RAM_PATTERN = re.compile(
        r"(?:(\d{1,3})\s*gb\s*(?:de\s+)?ram|ram\s*(?:de\s+)?(\d{1,3})\s*gb)",
        re.IGNORECASE,
    )

    # Atributos booleanos/enum reconhecidos por palavra-chave. As chaves são as do
    # `category_attribute_schema` (ver worker/seed/categories.json) — o valor cai
    # direto no filtro JSONB, então precisa casar com o que a ingestão gravou.
    _STORAGE_TYPES = {"ssd": "SSD", "hdd": "HDD", "emmc": "eMMC"}
    _ANC_PATTERN = re.compile(r"\banc\b|cancelamento\s+de\s+ru[ií]do", re.IGNORECASE)

    # Palavras que expressam **intenção de compra**, não característica de produto.
    # O dicionário `portuguese` do Postgres só descarta stopword gramatical ("para",
    # "com", "qual"); "melhor"/"barato"/"quero" sobrevivem e viram termo obrigatório
    # no AND do `plainto_tsquery` — como não aparecem nos títulos, zeram a busca.
    # Descartá-las é justamente o papel do parser de intenção (RF-11).
    # Comparadas sem acento, então basta a forma simples aqui.
    _INTENT_FILLERS = frozenset(
        {
            "melhor", "melhores", "bom", "bons", "boa", "boas",
            "otimo", "otima", "otimos", "otimas", "excelente", "excelentes",
            "barato", "barata", "baratos", "baratas", "economico", "economica",
            "recomende", "recomenda", "recomendacao", "recomendacoes",
            "indicacao", "indicacoes", "indique", "sugestao", "sugestoes",
            "quero", "queria", "preciso", "procuro", "busco", "buscando",
            "dica", "dicas", "top", "custo", "beneficio", "vale", "pena",
        }
    )  # fmt: skip

    def parse(self, query: str) -> Intent:
        """Extrai categoria, preço máximo e atributos de uma consulta."""

        # Normaliza o texto para tornar a busca por palavras-chave
        # independente de letras maiúsculas/minúsculas.
        normalized = query.lower().strip()

        intent = Intent(raw=query)
        intent.category = self._parse_category(normalized)
        intent.price_max = self._parse_price_max(normalized)
        intent.attributes = self._parse_attributes(normalized)
        intent.text = self._texto_para_fts(normalized) or query
        return intent

    def _texto_para_fts(self, normalized: str) -> str:
        """Texto de busca sem o que já virou filtro nem o que é ruído de intenção.

        Cada termo removido aqui deixa de ser obrigatório no AND do `plainto_tsquery`.
        Se a limpeza consumir a consulta inteira ("melhor custo benefício"), preserva o
        passo anterior — texto demais é melhor que busca vazia.
        """
        sem_preco = " ".join(self._PRICE_PATTERN.sub(" ", normalized).split())
        sem_filler = " ".join(
            token
            for token in sem_preco.split()
            if self._sem_acento(token.strip(".,;:!?")) not in self._INTENT_FILLERS
        )
        return sem_filler or sem_preco

    @staticmethod
    def _sem_acento(token: str) -> str:
        """ "ótimo" -> "otimo": compara filler independente de acentuação."""
        decomposto = unicodedata.normalize("NFD", token)
        return "".join(c for c in decomposto if not unicodedata.combining(c))

    def _parse_category(self, normalized: str) -> str | None:
        """Slug da categoria mencionada, ou None fora das categorias cobertas.

        Vence o termo que aparece **primeiro** na consulta, não a ordem do dicionário:
        em "fone bluetooth para notebook" o assunto é o fone.
        """
        posicoes = {
            categoria: min(
                (pos for kw in keywords if (pos := normalized.find(kw)) >= 0),
                default=-1,
            )
            for categoria, keywords in self._CATEGORY_KEYWORDS.items()
        }
        encontrados = {cat: pos for cat, pos in posicoes.items() if pos >= 0}
        return min(encontrados, key=encontrados.get) if encontrados else None

    def _parse_price_max(self, normalized: str) -> float | None:
        """Teto de preço informado após "até"/"ate". None quando não há ou é inválido."""
        match = self._PRICE_PATTERN.search(normalized)
        if not match:
            return None
        # Remove separador de milhar e converte vírgula decimal (pt-BR) para float.
        value = match.group(1).replace(".", "").replace(",", ".")
        try:
            return float(value)
        except ValueError:
            return None

    def _parse_attributes(self, normalized: str) -> dict:
        """Atributos estruturados citados na consulta (chaves do schema da categoria).

        Cobre os sinais que o usuário costuma digitar; o que não for reconhecido
        continua valendo como texto livre no FTS.
        """
        attributes: dict = {}

        if match := self._RAM_PATTERN.search(normalized):
            attributes["ram_gb"] = int(match.group(1) or match.group(2))

        for termo, valor in self._STORAGE_TYPES.items():
            if re.search(rf"\b{termo}\b", normalized):
                attributes["storage_type"] = valor
                break

        if self._ANC_PATTERN.search(normalized):
            attributes["anc"] = True

        return attributes
