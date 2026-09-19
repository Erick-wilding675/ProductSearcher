"""Suíte de relevância por **caso de uso** — a lacuna que a Fase 6 ataca.

`test_relevance.py` mede consultas de **produto conhecido** ("acer predator
helios"): o usuário já sabe o que quer e só precisa que a busca ache. Essa é a
metade fácil, e o FTS resolve — os termos da consulta estão literalmente no
título.

Esta suíte mede a outra metade: consultas de **necessidade** ("notebook para
edição de vídeo"). Aqui o usuário descreve o que vai fazer, não o produto; nada
garante que a palavra "edição" apareça no título de quem serve. É o passo 1 do
plano da Fase 6 (ADR-010, D1) e é ela que dá o número de antes/depois do
enriquecimento semântico do passo 2 — sem baseline medido, "melhorou" é opinião.

## Como a verdade é definida

Não há um produto certo por consulta: há um **conjunto aceitável**. Um notebook
serve para jogos se tem GPU dedicada — vários servem. Então cada caso traz um
predicado sobre `specs` (e preço), não um nome esperado.

O predicado é sobre **specs, nunca sobre o nome**. Usar o nome como gabarito
seria circular: `search_vector` é `to_tsvector(name || model || description)`,
ou seja, exatamente o texto que o FTS indexa. Um gabarito textual mediria se a
busca acha o que a busca indexa, e daria nota alta sem que o usuário fosse mais
bem servido. Spec é fato do produto, independente de como o anúncio foi escrito.

## O que é medido

- **precisão@5**: quantos dos 5 primeiros satisfazem o caso de uso.
- **cobertura@5**: se ao menos um dos 5 satisfaz (o usuário sai com algo útil).
- **acaso**: fração do catálogo da categoria que satisfaz o predicado. É a régua
  honesta — um caso em que 85% do catálogo qualifica não mede nada, porque
  devolver qualquer coisa acerta. Por isso os predicados foram calibrados contra
  o seed para ficar entre ~15% e ~45% (ver ADR-010, D1).

## Os agregados saíram do xfail em 21/08/2026

O alvo (`META`) é o do PRD para relevância: 80%. Os dois agregados nasceram em
`xfail`: antes do passo 2 o documento FTS não tinha vocabulário de uso confiável
— parte dos títulos traz "gamer" ou "para trabalho" porque a copy do marketplace
resolveu escrever, não porque o produto seja isso.

O passo 2 fechou (ADR-010 D2, rótulos offline + filtro no parser) e o vermelho
virou verde: cobertura@5 27% → 55% (acento, D8) → 60% (faixa numérica) → **100%**,
precisão média@5 16% → 34% → 37% → **68%**, com zero consulta devolvendo vazio.
Os `xfail` saíram junto: daqui para a frente estes dois testes são **guarda de
regressão**, não previsão de fracasso. Quem baixar o placar tem de justificar.

Ao trocar o seed, recalibre: um predicado que passou a valer para 80% do
catálogo virou decorativo.

## Quando um caso sai do agregado

"fone com bateria para o dia todo" nasceu aqui como caso semântico e virou
**controle** quando o parser passou a extrair `battery_h >= 30`. A razão é a
mesma que proíbe gabarito textual: com o filtro no ar, o predicado do gabarito
e a condição do SQL são a **mesma regra**, e a precisão dá 100% por construção,
não por acerto. Deixá-lo no agregado creditaria ao enriquecimento semântico um
ganho que é do `RuleBasedIntentParser` — a conta errada que a D1 existe para
impedir. Como controle ele continua valendo, e é o que fica vermelho se a faixa
numérica quebrar.

Vale a regra geral: **um caso que o parser passa a resolver com filtro duro sai
do agregado e vira controle.**
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.search.schemas import SearchResultItem
from app.search.service import SearchService
from tests.conftest import pula_sem_rotulo_de_uso

TOP_N = 5
META = 0.80


@dataclass(frozen=True)
class CasoDeUso:
    """Uma consulta de necessidade e a regra que diz quem a atende.

    `aceita` recebe o item **inteiro** (e não só `specs`) porque parte dos casos
    depende do preço — "para faculdade" sem teto de preço é outra pergunta.
    """

    query: str
    rotulo: str
    categoria: str
    aceita: Callable[[SearchResultItem], bool]
    porque: str
    controle: bool = False
    """Caso que o pipeline atual **já** deveria acertar.

    Serve de sanity check: se um controle falha, o problema é o arreio (seed
    trocado, banco desatualizado), não a busca semântica que ainda não existe.
    """


def _spec(item: SearchResultItem, chave: str, default=None):
    return (item.specs or {}).get(chave, default)


def _num(valor, default: float) -> float:
    """Spec numérica vinda do JSONB pode chegar como str; ausente vira `default`."""
    if valor is None:
        return default
    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


def _preco(item: SearchResultItem) -> float:
    preco = item.min_price
    if preco is None:
        return float("inf")
    return float(preco) if isinstance(preco, Decimal) else float(preco)


CASOS: list[CasoDeUso] = [
    # ---- notebooks -------------------------------------------------------
    CasoDeUso(
        query="notebook para jogos",
        rotulo="jogos",
        categoria="notebooks",
        aceita=lambda i: bool(_spec(i, "gpu")),
        porque="jogo moderno depende de GPU dedicada; vídeo integrado não entrega",
    ),
    CasoDeUso(
        query="notebook para edicao de video",
        rotulo="edição de vídeo",
        categoria="notebooks",
        aceita=lambda i: bool(_spec(i, "gpu")) and _num(_spec(i, "ram_gb"), 0) >= 16,
        porque="timeline 4K exige GPU para preview e 16GB+ para não paginar",
    ),
    CasoDeUso(
        query="notebook para trabalho no escritorio",
        rotulo="trabalho",
        categoria="notebooks",
        aceita=lambda i: (
            _num(_spec(i, "ram_gb"), 0) >= 8
            and _spec(i, "storage_type") == "SSD"
            and not _spec(i, "gpu")
        ),
        porque="máquina de escritório: SSD e 8GB bastam, e GPU dedicada só encarece",
    ),
    CasoDeUso(
        query="notebook para faculdade",
        rotulo="faculdade",
        categoria="notebooks",
        aceita=lambda i: (
            _num(_spec(i, "ram_gb"), 0) >= 8
            and _spec(i, "storage_type") == "SSD"
            and _preco(i) <= 4500
        ),
        porque="uso de estudante é leve, mas o orçamento é o filtro que manda",
    ),
    CasoDeUso(
        query="notebook leve para viagem",
        rotulo="portabilidade",
        categoria="notebooks",
        aceita=lambda i: _num(_spec(i, "weight_kg"), 99) <= 1.6,
        porque="o que define portabilidade é o peso, não a marca nem a tela",
    ),
    CasoDeUso(
        query="notebook para programacao",
        rotulo="programação",
        categoria="notebooks",
        aceita=lambda i: (
            _num(_spec(i, "ram_gb"), 0) >= 16
            and _spec(i, "storage_type") == "SSD"
            and _num(_spec(i, "storage_gb"), 0) >= 512
        ),
        porque="container/IDE/browser abertos juntos: 16GB e SSD de 512GB é o piso",
    ),
    # ---- headphones ------------------------------------------------------
    CasoDeUso(
        query="fone para academia",
        rotulo="academia",
        categoria="headphones",
        aceita=lambda i: (
            _spec(i, "water_resistant") is True and _spec(i, "type") in {"earbuds", "in-ear"}
        ),
        porque="suor pede resistência à água, e over-ear não se usa treinando",
    ),
    CasoDeUso(
        query="fone para correr",
        rotulo="corrida",
        categoria="headphones",
        aceita=lambda i: (
            _spec(i, "water_resistant") is True and _spec(i, "type") in {"earbuds", "in-ear"}
        ),
        porque="mesma necessidade da academia, dita com outra palavra — e é esse o ponto",
    ),
    CasoDeUso(
        query="fone para reuniao online",
        rotulo="reunião",
        categoria="headphones",
        aceita=lambda i: _spec(i, "microphone") is True and _spec(i, "anc") is True,
        porque="chamada precisa de microfone; ANC é o que salva quem trabalha em casa",
    ),
    CasoDeUso(
        query="fone para viagem de aviao",
        rotulo="viagem",
        categoria="headphones",
        aceita=lambda i: _spec(i, "anc") is True and _spec(i, "type") == "over-ear",
        porque="ruído de cabine é grave e contínuo: over-ear com ANC é o que corta",
    ),
    # ---- controles: o pipeline de hoje já deveria acertar -----------------
    CasoDeUso(
        query="fone com bateria para o dia todo",
        rotulo="controle: faixa numérica",
        categoria="headphones",
        aceita=lambda i: _num(_spec(i, "battery_h"), 0) >= 30,
        porque="'dia todo' é autonomia; o parser vira isso em battery_h >= 30",
        controle=True,
    ),
    CasoDeUso(
        query="notebook gamer",
        rotulo="controle: termo no título",
        categoria="notebooks",
        aceita=lambda i: bool(_spec(i, "gpu")),
        porque="'gamer' está no título de quem vende; o FTS resolve sem semântica",
        controle=True,
    ),
    CasoDeUso(
        query="fone com cancelamento de ruido",
        rotulo="controle: atributo extraído",
        categoria="headphones",
        aceita=lambda i: _spec(i, "anc") is True,
        porque="o RuleBasedIntentParser já vira isso em filtro duro anc=True",
        controle=True,
    ),
]


@dataclass
class Medicao:
    """Resultado de um caso, guardado para o relatório do fim da suíte."""

    caso: CasoDeUso
    aceitos: int
    avaliados: int
    total: int

    @property
    def precisao(self) -> float:
        return self.aceitos / self.avaliados if self.avaliados else 0.0

    @property
    def cobriu(self) -> bool:
        return self.aceitos > 0


def _medir(service: SearchService, caso: CasoDeUso) -> Medicao:
    """Roda a consulta pelo pipeline real e conta quantos do topo servem."""
    resposta = service.search(q=caso.query, page=1)
    topo = resposta.results[:TOP_N]
    return Medicao(
        caso=caso,
        aceitos=sum(1 for item in topo if caso.aceita(item)),
        avaliados=len(topo),
        total=resposta.total,
    )


@pytest.fixture(scope="session")
def acaso(db_session) -> dict[str, float]:
    """Fração do catálogo que satisfaz cada predicado — o 'acerto ao acaso'.

    Sem isso não dá para ler a precisão: 60% de precisão é ótimo num caso em que
    o acaso é 20%, e é fracasso num caso em que é 70%. Calculado sobre o catálogo
    real (não sobre o YAML do seed) porque é contra o banco que a busca roda.
    """
    from app.search.intent import Intent
    from app.search.providers import FtsSearchProvider

    provider = FtsSearchProvider(db_session)
    fracoes: dict[str, float] = {}
    for categoria in {c.categoria for c in CASOS}:
        # Consulta sem texto: devolve o pool inteiro da categoria, sem FTS no meio.
        hits = provider.search(Intent(raw="", text=""), {"category": categoria})
        itens = [SearchResultItem(**{**h, "specs": h.get("attributes") or {}}) for h in hits]
        for caso in CASOS:
            if caso.categoria != categoria or not itens:
                continue
            fracoes[caso.query] = sum(1 for i in itens if caso.aceita(i)) / len(itens)
    return fracoes


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.rotulo)
def test_caso_de_uso_mede(
    search_service: SearchService, catalogo_tem_use_case: bool, caso: CasoDeUso
) -> None:
    """Registra a medição de cada caso. Só falha nos **controles**.

    Os casos semânticos não afirmam nada isoladamente: quem julga é o agregado,
    porque uma consulta ruim isolada é ruído — o KPI do PRD é sobre o conjunto.
    Os controles, sim, afirmam: eles não dependem de semântica alguma.
    """
    pula_sem_rotulo_de_uso(caso.query, catalogo_tem_use_case)
    medicao = _medir(search_service, caso)

    if caso.controle:
        assert medicao.cobriu, (
            f"controle {caso.rotulo!r} falhou em {caso.query!r}: "
            f"nenhum dos {medicao.avaliados} primeiros satisfaz ({caso.porque}). "
            "Isso indica seed/banco fora do esperado, não falta de busca semântica."
        )


def test_cobertura_casos_de_uso(
    search_service: SearchService, catalogo_tem_use_case: bool, acaso
) -> None:
    """KPI: ≥80% dos casos com ao menos um resultado útil no top-5."""
    for caso in CASOS:
        pula_sem_rotulo_de_uso(caso.query, catalogo_tem_use_case)

    medicoes = [_medir(search_service, caso) for caso in CASOS if not caso.controle]
    cobertos = [m for m in medicoes if m.cobriu]
    taxa = len(cobertos) / len(medicoes)

    assert taxa >= META, f"cobertura@{TOP_N}: {taxa:.0%} (meta {META:.0%})\n" + _relatorio(
        medicoes, acaso
    )


def test_precisao_casos_de_uso(
    search_service: SearchService, catalogo_tem_use_case: bool, acaso
) -> None:
    """Precisão média@5 acima do acaso com folga: o topo tem que ser do caso de uso.

    Meta deliberadamente mais dura que "acima do acaso": um top-5 em que 3 de 5
    servem ainda faz o usuário garimpar. O alvo é a maioria do topo servir.
    """
    for caso in CASOS:
        pula_sem_rotulo_de_uso(caso.query, catalogo_tem_use_case)

    medicoes = [_medir(search_service, caso) for caso in CASOS if not caso.controle]
    media = sum(m.precisao for m in medicoes) / len(medicoes)
    media_acaso = sum(acaso.get(m.caso.query, 0.0) for m in medicoes) / len(medicoes)

    assert media >= 0.60, (
        f"precisão média@{TOP_N}: {media:.0%} (alvo 60%, acaso {media_acaso:.0%})\n"
        + _relatorio(medicoes, acaso)
    )


def _relatorio(medicoes: list[Medicao], acaso: dict[str, float]) -> str:
    """Tabela por caso — é o que se lê para decidir onde a busca está cega."""
    linhas = [
        f"{'caso':22} {'consulta':38} {'top5':>6} {'prec':>6} {'acaso':>6} {'total':>6}",
        "-" * 88,
    ]
    for m in medicoes:
        linhas.append(
            f"{m.caso.rotulo:22} {m.caso.query:38} "
            f"{m.aceitos}/{m.avaliados:<4} {m.precisao:>5.0%} "
            f"{acaso.get(m.caso.query, 0.0):>5.0%} {m.total:>6}"
        )
    return "\n".join(linhas)
