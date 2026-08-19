"""Parsing de intenção.

Default determinístico (regras/regex) — princípio: o sistema funciona sem IA.
LLM pode reforçar no futuro (RF-16), atrás da mesma interface.

Três coisas saem daqui, e a diferença entre elas é o que decide a consulta SQL:

- **categoria e preço** — filtros que o pipeline já tinha;
- **atributo exato** (`attributes`) — vira containment JSONB (`@>`), igualdade;
- **faixa numérica** (`attribute_ranges`) — vira comparação (`>=`/`<=`).

A terceira existe porque a segunda não a expressa: `@>` é igualdade, e um fone
de 40h não "contém" 30h. Sem ela, "fone com bateria para o dia todo" não tinha
como virar filtro e caía inteira no texto livre (ADR-0010, D2).
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
    attribute_ranges: dict[str, dict[str, float]] = field(default_factory=dict)
    """Faixas numéricas por chave: `{"battery_h": {"min": 30.0}}`.

    Separado de `attributes` porque o operador SQL é outro — `>=`/`<=` contra o
    `@>` de igualdade. Misturar os dois num dicionário só faria o provider
    adivinhar qual é qual pelo formato do valor.
    """
    text: str = ""

    def __post_init__(self) -> None:
        # Sem parser (ex.: Intent montado à mão nos testes), o texto é a query crua.
        if not self.text:
            self.text = self.raw


class IntentParser(Protocol):
    def parse(self, query: str) -> Intent: ...


# --- faixas numéricas -------------------------------------------------------
#
# Unidade como o usuário a digita, por chave do `category_attribute_schema`
# (worker/seed/categories.json). A chave tem de casar com o que a ingestão
# gravou: inventar uma aqui vira filtro que nunca casa — o mesmo modo de falha
# silenciosa do slug de categoria.
#
# "gb" sozinho é ambíguo entre memória e armazenamento, então essas duas exigem
# a palavra ao lado. As outras três não têm com o que se confundir.
_UNIDADE_DO_ATRIBUTO = {
    "battery_h": r"h|hs|hrs?|horas?",
    "weight_kg": r"kg|quilos?",
    "screen_in": r"pol|polegadas?",
    "ram_gb": r"gb\s*(?:de\s+)?ram",
    "storage_gb": r"gb\s*(?:de\s+)?(?:ssd|hdd?|emmc|armazenamento)",
}

# Sem separador de milhar: as medidas do catálogo são números pequenos (30 h,
# 16 GB, 1,6 kg), então "." e "," são ambos decimais aqui. É o oposto da regra
# do preço, onde "5.000" é cinco mil — e é por isso que são conversões separadas.
_NUMERO = r"(?P<valor>\d{1,4}(?:[.,]\d{1,2})?)"

_ABRE_MINIMO = (
    r"(?:pelo\s+menos|ao\s+menos|no\s+m[ií]nimo|a\s+partir\s+de"
    r"|acima\s+de|mais\s+de|maior\s+que)"
)
_ABRE_MAXIMO = r"(?:no\s+m[áa]ximo|at[ée]|menos\s+de|abaixo\s+de|menor\s+que)"
_FECHA_MINIMO = r"(?:ou\s+mais|ou\s+superior|pra\s+cima|para\s+cima)"


def _padroes_de_faixa() -> tuple[tuple[str, str, re.Pattern], ...]:
    """(chave, limite, regex) para cada atributo numérico e cada forma de dizer.

    Duas posições do comparador, porque as duas aparecem na consulta real: antes
    do número ("pelo menos 30 horas") e depois dele ("30 horas ou mais").
    """
    padroes: list[tuple[str, str, str]] = []
    for chave, unidade in _UNIDADE_DO_ATRIBUTO.items():
        unidade_apos = rf"\s*(?:{unidade})\b"
        padroes += [
            (chave, "min", rf"{_ABRE_MINIMO}\s*(?:de\s+)?{_NUMERO}{unidade_apos}"),
            (chave, "max", rf"{_ABRE_MAXIMO}\s*(?:de\s+)?{_NUMERO}{unidade_apos}"),
            (chave, "min", rf"{_NUMERO}{unidade_apos}\s*{_FECHA_MINIMO}"),
        ]
    return tuple((c, lim, re.compile(pad, re.IGNORECASE)) for c, lim, pad in padroes)


def _para_medida(texto: str) -> float | None:
    """ "1,6" e "1.6" viram 1.6 — em medida, os dois separadores são decimais."""
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def _remove_trechos(texto: str, trechos: list[tuple[int, int]]) -> str:
    """Apaga do texto os trechos que já viraram filtro, preservando o resto.

    Por posição, e não por `sub`: os padrões se sobrepõem (o de preço e o de
    faixa disputam "até"), e apagar por posição não depende da ordem em que
    foram encontrados.
    """
    restante = list(texto)
    for inicio, fim in trechos:
        restante[inicio:fim] = " " * (fim - inicio)
    return " ".join("".join(restante).split())


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

    # Unidade colada no número: o sinal de que aquele "até N" **não** é preço.
    # Sem esta guarda, "fone até 20 horas de bateria" virava teto de R$ 20 e a
    # busca voltava vazia — nenhum fone custa isso. Pior em "notebook até 1.5kg",
    # que virava R$ 15, porque a conversão de preço trata "." como milhar.
    _UNIDADE_APOS_NUMERO = re.compile(
        r"\s*(?:gb|tb|mb|kg|quilos?|hs?|hrs?|horas?|pol|polegadas?)\b",
        re.IGNORECASE,
    )

    _PADROES_DE_FAIXA = _padroes_de_faixa()

    # Necessidade dita por extenso, sem número. Não é "caso de uso" — o rótulo
    # do LLM da D2 responde "para que serve", e isto aqui é quantidade. O parser
    # determinístico resolve, e é mais barato e mais explicável que um rótulo.
    #
    # Exige a categoria porque a chave é **inferida**, não digitada: aplicar
    # `battery_h` a uma consulta de notebook zeraria o resultado, já que a
    # categoria nem tem esse atributo no schema. Quando o usuário escreve o
    # número, ele assume a consequência; quando o parser adivinha, não pode.
    #
    # 30h é decisão de produto, não medição: a autonomia de uma jornada mais
    # margem. No catálogo de hoje o corte deixa 26 dos 117 fones (22%), dentro
    # da faixa de acaso que a D1 calibrou — filtro seletivo sem esvaziar.
    _FAIXAS_POR_EXPRESSAO = (
        (
            re.compile(r"(?:o\s+)?dia\s+(?:todo|inteiro)|24\s*h(?:oras)?\b", re.IGNORECASE),
            "headphones",
            "battery_h",
            {"min": 30.0},
        ),
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
        """Extrai categoria, preço, faixas numéricas e atributos de uma consulta."""

        # Normaliza o texto para tornar a busca por palavras-chave
        # independente de letras maiúsculas/minúsculas.
        normalized = query.lower().strip()

        intent = Intent(raw=query)
        intent.category = self._parse_category(normalized)

        # Cada extração devolve também o trecho que consumiu: o que virou filtro
        # sai do texto do FTS, ou volta como termo obrigatório no AND e zera a
        # busca. Vale para "até R$5000" e igualmente para "pelo menos 30 horas".
        intent.price_max, trecho_preco = self._parse_price_max(normalized)
        intent.attribute_ranges, trechos_faixa = self._parse_ranges(normalized, intent.category)
        intent.attributes = self._parse_attributes(normalized, intent.attribute_ranges)
        intent.text = self._texto_para_fts(normalized, trecho_preco + trechos_faixa) or query
        return intent

    def _texto_para_fts(self, normalized: str, consumidos: list[tuple[int, int]]) -> str:
        """Texto de busca sem o que já virou filtro nem o que é ruído de intenção.

        Cada termo removido aqui deixa de ser obrigatório no AND do `plainto_tsquery`.
        Se a limpeza consumir a consulta inteira ("melhor custo benefício"), preserva o
        passo anterior — texto demais é melhor que busca vazia.
        """
        sem_estruturado = _remove_trechos(normalized, consumidos)
        sem_filler = " ".join(
            token
            for token in sem_estruturado.split()
            if self._sem_acento(token.strip(".,;:!?")) not in self._INTENT_FILLERS
        )
        return sem_filler or sem_estruturado

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

    def _parse_price_max(self, normalized: str) -> tuple[float | None, list[tuple[int, int]]]:
        """Teto informado após "até"/"ate", e o trecho consumido.

        Pula o "até N" seguido de unidade: ali o número é medida e quem responde
        é `_parse_ranges`. Continua procurando em vez de desistir, porque as duas
        coisas cabem na mesma consulta ("fone até R$300 e até 20 horas").
        """
        for match in self._PRICE_PATTERN.finditer(normalized):
            if self._UNIDADE_APOS_NUMERO.match(normalized, match.end()):
                continue
            # Remove separador de milhar e converte vírgula decimal (pt-BR) para float.
            value = match.group(1).replace(".", "").replace(",", ".")
            try:
                return float(value), [match.span()]
            except ValueError:
                return None, []
        return None, []

    def _parse_ranges(
        self, normalized: str, categoria: str | None
    ) -> tuple[dict[str, dict[str, float]], list[tuple[int, int]]]:
        """Faixas numéricas pedidas, e os trechos consumidos.

        Duas fontes, nesta ordem: o número que o usuário escreveu vence sempre, e
        a expressão por extenso ("o dia todo") só preenche o limite que ficou
        vazio. Adivinhar por cima de um número dito é o que não pode acontecer.
        """
        faixas: dict[str, dict[str, float]] = {}
        consumidos: list[tuple[int, int]] = []

        for chave, limite, padrao in self._PADROES_DE_FAIXA:
            for match in padrao.finditer(normalized):
                valor = _para_medida(match.group("valor"))
                if valor is None:
                    continue
                faixas.setdefault(chave, {})[limite] = valor
                consumidos.append(match.span())

        for padrao, categoria_exigida, chave, faixa in self._FAIXAS_POR_EXPRESSAO:
            if categoria != categoria_exigida:
                continue
            if match := padrao.search(normalized):
                ja_dito = faixas.setdefault(chave, {})
                ja_dito.update({k: v for k, v in faixa.items() if k not in ja_dito})
                consumidos.append(match.span())

        return {chave: faixa for chave, faixa in faixas.items() if faixa}, consumidos

    def _parse_attributes(self, normalized: str, faixas: dict | None = None) -> dict:
        """Atributos estruturados citados na consulta (chaves do schema da categoria).

        Cobre os sinais que o usuário costuma digitar; o que não for reconhecido
        continua valendo como texto livre no FTS.

        Chave já reivindicada por uma faixa não vira atributo exato: em "no mínimo
        16GB de RAM", somar `ram_gb = 16` ao `ram_gb >= 16` deixaria de fora
        justamente as máquinas de 32GB que o usuário aceitaria.
        """
        attributes: dict = {}
        faixas = faixas or {}

        if "ram_gb" not in faixas and (match := self._RAM_PATTERN.search(normalized)):
            attributes["ram_gb"] = int(match.group(1) or match.group(2))

        for termo, valor in self._STORAGE_TYPES.items():
            if re.search(rf"\b{termo}\b", normalized):
                attributes["storage_type"] = valor
                break

        if self._ANC_PATTERN.search(normalized):
            attributes["anc"] = True

        return attributes
