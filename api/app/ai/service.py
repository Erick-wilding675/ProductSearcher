"""Camada de IA — opcional e plugável. O caminho crítico nunca depende dela.

`explain` põe em português o que o `DeterministicRanking` já calculou: por que
aquele produto ficou naquela posição. O ranking devolve `score` + `factors` por
item e `criteria` por consulta (ADR-0007 D5.1) — números que a UI mostra. Esta
camada é a mesma informação em prosa.

## O contrato de `context` é a garantia de honestidade

`explain` recebe **apenas o que o ranking produziu** e não consulta banco, não
recalcula score e não conhece o catálogo. Isso não é limitação: é o que permite
que a versão por LLM (RF-61, ADR-0010 D6) exista sem risco. Um LLM que recebe o
produto inteiro pode elogiar a bateria; um LLM que recebe só `factors` só pode
narrar os fatores — e a prosa não tem como contradizer o número ao lado dela.

Chaves reconhecidas (todas opcionais menos `item`):

    {
      "query": "notebook gamer até 5000",
      "position": 1,                     # 1-based, como a UI mostra
      "item": {
        "name": "...", "min_price": 4299.0, "score": 0.87,
        "factors": {"relevance": {"score": 1.0, "applicable": True}, ...},
        "specs": {"ram_gb": 16, ...},
      },
      "intent": {
        "price_max": 5000.0,
        "attributes": {"ram_gb": 16},
        "attribute_ranges": {"battery_h": {"min": 30.0}},
      },
    }

O que faltar simplesmente não é dito. Nunca se afirma o que não veio no
`context` — é essa regra que a implementação por LLM terá de herdar.

Com `AI_ENABLED=false` (o default do projeto) usa-se a implementação
determinística, que é completa e não é um degradado: ela diz tudo o que há para
dizer, porque tudo o que há para dizer está nos fatores.
"""

from typing import Protocol

from app.search.ranking import WEIGHTS, attr_matches, range_matches

# Acima disto o fator é dito sem ressalva. Não é 1.0 exato porque `relevance` é
# uma divisão em ponto flutuante (`fts_rank / max_rank`) e o melhor item do
# conjunto pode fechar em 0.9999999.
_TOTAL = 0.999

# Como cada fator é dito ao usuário quando **contribuiu** para a posição. O texto
# fala do produto, não do algoritmo: "custa menos que o teto", não "price=0.86".
_FRASES = {
    "relevance": "o texto do anúncio é o que mais se aproxima do que você buscou",
    "price": "o preço cabe no teto que você pediu",
    "attributes": "atende o que você especificou",
    "preference": "corresponde à preferência que você marcou",
}

# Por que um critério **não** entrou na conta. Dizer isso importa tanto quanto
# dizer o que contou: sem essa frase o usuário atribui ao ranking um cuidado que
# ele não teve naquela consulta.
_AUSENCIAS = {
    "relevance": "relevância textual não entrou (a busca não teve texto)",
    "price": "preço não entrou (você não informou um teto)",
    "attributes": "especificações não entraram (você não pediu nenhuma)",
    "preference": "preferência não entrou (nenhuma foi marcada)",
}


class AIService(Protocol):
    def explain(self, context: dict) -> str: ...


class DeterministicAIService:
    """Explicação sem LLM, derivada dos fatores do ranking.

    Determinística no sentido forte: o mesmo `context` produz sempre o mesmo
    texto, sem rede, sem chave de API e sem custo. É o fallback que a flag
    `ai_enabled=False` sempre prometeu — e, por ora, a única implementação.
    """

    def explain(self, context: dict) -> str:
        item = context.get("item") or {}
        fatores = item.get("factors") or {}

        aplicaveis = {
            nome: f for nome, f in fatores.items() if f.get("applicable") and nome in WEIGHTS
        }

        partes = [_abertura(item, context.get("position"), context.get("query"))]

        contribuicoes = _contribuicoes(aplicaveis)
        pesaram = [(nome, peso) for nome, peso in contribuicoes if peso > 0]

        if pesaram:
            partes.append(_porques(pesaram, item, context.get("intent") or {}))
        elif aplicaveis:
            # Critérios ativos, mas o item pontuou zero em todos: ele está no
            # resultado por casar com o filtro, não por mérito de ranking. Dizer
            # isso é mais útil que uma frase vaga de elogio.
            partes.append(
                "Nenhum dos critérios da busca pesou a favor dele — "
                "ele entra por atender o filtro, não por se destacar."
            )
        else:
            partes.append(
                "Esta consulta não ativou nenhum critério de ranking, "
                "então a ordem é a padrão do catálogo."
            )

        ausentes = [_AUSENCIAS[nome] for nome in WEIGHTS if nome not in aplicaveis]
        if ausentes and aplicaveis:
            partes.append("Fora da conta: " + "; ".join(ausentes) + ".")

        return " ".join(p for p in partes if p)


class LLMAIService:
    """Explicação via LLM (RF-61) — **não implementada**, e condicional (ADR-0010 D6).

    O desenho está fechado e é restritivo de propósito: recebe o mesmo `context`
    do `DeterministicAIService` — fatores já calculados, nada do catálogo — com
    instrução de narrar sem introduzir fato novo. Prosa que contradiz os
    `factors` exibidos ao lado é pior que prosa nenhuma.

    Só é construída se, ao fim de D2/D4, a explicação determinística se mostrar
    insuficiente. Até lá, `ai_enabled=True` não tem o que ligar aqui.
    """

    def explain(self, context: dict) -> str:
        raise NotImplementedError(
            "RF-61 é condicional (ADR-0010 D6): use DeterministicAIService. "
            "Quando for construída, deve receber este mesmo context e narrar "
            "apenas os fatores já calculados."
        )


def _contribuicoes(aplicaveis: dict) -> list[tuple[str, float]]:
    """Quanto cada fator aplicável empurrou o score, em fração do total.

    Mesma renormalização do `_weighted_score` do ranking: fator não aplicável sai
    da conta e os pesos dos demais são redistribuídos. Sem isso a explicação
    citaria pesos que não foram os usados naquela consulta.
    """
    total = sum(WEIGHTS[nome] for nome in aplicaveis)
    if not total:
        return []

    pares = [
        (nome, WEIGHTS[nome] * float(f.get("score") or 0.0) / total)
        for nome, f in aplicaveis.items()
    ]
    return sorted(pares, key=lambda par: (-par[1], par[0]))


def _abertura(item: dict, posicao, query) -> str:
    """Primeira frase: onde o item ficou e em resposta a quê."""
    nome = str(item.get("name") or "Este produto").strip()
    if posicao:
        inicio = f"{nome} ficou em {int(posicao)}º"
    else:
        inicio = f"{nome} aparece no resultado"

    if query:
        inicio += f' para "{str(query).strip()}"'
    return inicio + "."


def _porques(pesaram: list[tuple[str, float]], item: dict, intent: dict) -> str:
    """Os fatores que contribuíram, do que mais pesou para o que menos pesou.

    A ordem **é** a informação — por isso não há uma frase extra dizendo qual foi
    o principal: ele é o primeiro da lista.
    """
    ditos = "; ".join(_detalhe(nome, item, intent) for nome, _ in pesaram)
    return f"Pesou a favor, do que mais contou para o que menos: {ditos}."


def _detalhe(nome: str, item: dict, intent: dict) -> str:
    """A frase do fator, enriquecida com o número concreto quando ele veio.

    Quando o `context` traz preço e teto, diz-se a folga em reais em vez do
    score — "R$ 700,00 abaixo do teto" é verificável pelo usuário; "0,86" não é.
    Sem o número, cai na frase genérica de `_FRASES`, que continua verdadeira.

    **Score parcial não pode virar frase absoluta.** `relevance` é normalizada
    pelo maior `fts_rank` do conjunto: 1.0 é o melhor casamento da busca, 0.62
    não é. Dizer "é o que mais se aproxima" a 0.62 seria afirmar o que o número
    não diz — o tipo de erro que a versão por LLM tende a cometer, e por isso
    está travado aqui.
    """
    score = _score(item, nome)

    if nome == "price":
        preco = item.get("min_price")
        teto = intent.get("price_max")
        if preco is not None and teto is not None and float(teto) >= float(preco):
            folga = float(teto) - float(preco)
            return f"custa {_reais(preco)}, {_reais(folga)} abaixo do teto de {_reais(teto)}"

    elif nome == "relevance" and score < _TOTAL:
        return (
            "o texto do anúncio casa com o que você buscou "
            f"({score:.0%} do melhor casamento desta busca)"
        )

    elif nome == "attributes":
        pedidos = intent.get("attributes") or {}
        faixas = intent.get("attribute_ranges") or {}
        specs = item.get("specs") or {}
        # Mesma regra do ranking (`attr_matches` / `range_matches`): chave
        # presente com valor divergente **não** é atributo atendido, e não pode
        # ser citada como se fosse. Só o que casa de fato entra na frase.
        casados = sorted(
            chave for chave, valor in pedidos.items() if attr_matches(specs.get(chave), valor)
        )
        casados += sorted(
            chave for chave, faixa in faixas.items() if range_matches(specs.get(chave), faixa)
        )
        if casados:
            lista = ", ".join(f"{chave} = {specs[chave]}" for chave in casados)
            prefixo = "tem o que você pediu" if score >= _TOTAL else "tem parte do que você pediu"
            return f"{prefixo} ({lista})"

    return _FRASES[nome]


def _score(item: dict, nome: str) -> float:
    return float(((item.get("factors") or {}).get(nome) or {}).get("score") or 0.0)


def _reais(valor) -> str:
    """Formata em pt-BR: 5000 -> 'R$ 5.000,00'."""
    texto = f"{float(valor):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"R$ {texto}"
