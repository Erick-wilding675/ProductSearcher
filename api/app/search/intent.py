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

    # Consulta de **necessidade** ("fone para academia") → rótulo do conjunto
    # fechado `use_case` (ADR-010 D2). O rótulo tem de existir em
    # `worker/seed/categories.json`: o filtro é containment JSONB contra o que a
    # ingestão gravou, então um rótulo inventado aqui vira silenciosamente zero
    # resultado — a mesma armadilha dos slugs de categoria acima.
    #
    # Separado por categoria porque o mesmo termo não significa a mesma coisa nos
    # dois catálogos: "viagem" em fone é ruído de cabine; em notebook é peso, ou
    # seja `portabilidade`.
    #
    # Termos comparados **sem acento** (ver `_sem_acento`), então basta a forma
    # simples aqui.
    _USE_CASES: dict[str, dict[str, tuple[str, ...]]] = {
        "notebooks": {
            "jogos": ("jogos", "jogar", "gamer", "games", "game"),
            "edicao-video": ("edicao de video", "editar video", "edicao de videos"),
            "trabalho": ("trabalho", "trabalhar", "escritorio", "home office"),
            "estudo": ("faculdade", "estudar", "estudos", "estudante", "escola", "aula"),
            "programacao": ("programacao", "programar", "desenvolvimento", "codigo"),
            "portabilidade": ("viagem", "viajar", "carregar", "levar", "mochila"),
        },
        "headphones": {
            "esporte": ("academia", "correr", "corrida", "treino", "treinar", "esporte"),
            "chamadas": ("reuniao", "reunioes", "chamada", "chamadas", "call", "ligacao"),
            "viagem": ("viagem", "viajar", "aviao", "voo"),
            "trabalho": ("trabalho", "trabalhar", "escritorio", "home office"),
            "jogos": ("jogos", "jogar", "gamer", "games", "game"),
        },
    }

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
        intent.attributes = self._parse_attributes(normalized, intent.category)
        intent.text = self._texto_para_fts(normalized, intent.attributes) or query
        return intent

    def _texto_para_fts(self, normalized: str, attributes: dict | None = None) -> str:
        """Texto de busca sem o que já virou filtro nem o que é ruído de intenção.

        Cada termo removido aqui deixa de ser obrigatório no AND do `plainto_tsquery`.
        Se a limpeza consumir a consulta inteira ("melhor custo benefício"), preserva o
        passo anterior — texto demais é melhor que busca vazia.
        """
        sem_preco = " ".join(self._PRICE_PATTERN.sub(" ", normalized).split())
        sem_uso = self._sem_termos_de_uso(sem_preco, attributes or {})
        sem_filler = " ".join(
            token
            for token in sem_uso.split()
            if self._sem_acento(token.strip(".,;:!?")) not in self._INTENT_FILLERS
        )
        return sem_filler or sem_uso or sem_preco

    def _sem_termos_de_uso(self, texto: str, attributes: dict) -> str:
        """Remove do texto os termos que já viraram filtro `use_case`.

        Mesma lógica do preço, e pelo mesmo motivo: o que virou filtro **duro** não
        pode continuar obrigatório no AND do `plainto_tsquery`. Deixar "faculdade"
        no texto exigiria a palavra no anúncio — e ela não está em nenhum dos 235
        produtos do catálogo, então o filtro acertaria e o AND zeraria em seguida.
        """
        rotulos = attributes.get("use_case")
        if not rotulos:
            return texto

        resultado = texto
        for categoria in self._USE_CASES.values():
            for rotulo, termos in categoria.items():
                if rotulo not in rotulos:
                    continue
                for termo in termos:
                    # Termos compostos ("edicao de video") saem inteiros; simples
                    # saem com fronteira de palavra, para "game" não comer "gamer".
                    resultado = re.sub(
                        rf"\b{re.escape(termo)}\b", " ", resultado, flags=re.IGNORECASE
                    )
        return " ".join(resultado.split())

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

    def _parse_attributes(self, normalized: str, category: str | None = None) -> dict:
        """Atributos estruturados citados na consulta (chaves do schema da categoria).

        Cobre os sinais que o usuário costuma digitar; o que não for reconhecido
        continua valendo como texto livre no FTS.
        """
        attributes: dict = {}

        if usos := self._parse_use_cases(normalized, category):
            attributes["use_case"] = usos

        if match := self._RAM_PATTERN.search(normalized):
            attributes["ram_gb"] = int(match.group(1) or match.group(2))

        for termo, valor in self._STORAGE_TYPES.items():
            if re.search(rf"\b{termo}\b", normalized):
                attributes["storage_type"] = valor
                break

        if self._ANC_PATTERN.search(normalized):
            attributes["anc"] = True

        return attributes

    def _parse_use_cases(self, normalized: str, category: str | None) -> list[str]:
        """Rótulos de `use_case` reconhecidos na consulta, para a categoria em questão.

        Sem categoria não rotula: "para viagem" sozinho é ambíguo entre
        `portabilidade` (notebook) e `viagem` (fone), e chutar traria filtro duro
        errado — pior que filtro nenhum.

        Devolve **lista** porque o filtro é containment JSONB: uma lista com dois
        rótulos exige que o produto tenha os dois, que é a leitura certa de
        "notebook para jogos e edição de vídeo".
        """
        vocabulario = self._USE_CASES.get(category or "")
        if not vocabulario:
            return []

        texto = self._sem_acento(normalized)
        encontrados = [
            rotulo
            for rotulo, termos in vocabulario.items()
            if any(re.search(rf"\b{re.escape(t)}\b", texto) for t in termos)
        ]
        # Ordem estável (a do vocabulário) para o filtro e o log não variarem
        # entre execuções — `searches` guarda o `parsed_intent`.
        return encontrados
