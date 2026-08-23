"""Testes da busca híbrida por união + RRF (ADR-010 D4).

Sem banco e sem modelo: os dois braços entram por fake, e o que se verifica é a
**fusão** — que é onde mora a lógica nova. A qualidade do resultado já foi medida
em D4 e está registrada no ADR; teste unitário não é o lugar de medir relevância.
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.search.intent import Intent
from app.search.providers import (
    FtsSearchProvider,
    HybridSearchProvider,
    _condicoes_duras,
    get_search_provider,
)


def _hit(pid: str, nome: str = "Produto") -> dict:
    return {
        "id": pid,
        "slug": f"slug-{pid}",
        "name": nome,
        "category": "notebooks",
        "brand": "Acer",
        "brand_slug": "acer",
        "min_price": 3000.0,
        "fts_rank": 0.5,
        "attributes": {},
    }


class _FtsFake:
    def __init__(self, hits: list[dict]) -> None:
        self.hits = hits
        self.chamado_com = None

    def search(self, intent, filters=None, page=1):
        self.chamado_com = (intent, filters, page)
        return self.hits


def _hibrido(textuais: list[dict], vetoriais: list[dict]) -> HybridSearchProvider:
    """Híbrido com os dois braços trocados por fake."""
    p = HybridSearchProvider(session=None)
    p._fts = _FtsFake(textuais)
    p._candidatos_vetoriais = lambda intent, filters, texto: vetoriais
    return p


def test_uniao_traz_produto_que_o_fts_nao_achou():
    """O ponto da união: o que só o vetor acha continua no resultado."""
    p = _hibrido([_hit("a")], [_hit("b")])
    ids = [h["id"] for h in p.search(Intent(raw="notebook", text="notebook"))]
    assert set(ids) == {"a", "b"}


def test_consenso_entre_os_bracos_sobe():
    """Quem aparece nos dois braços tem de vencer quem aparece só num.

    É a propriedade que justifica RRF: o sinal forte é a concordância, não a
    posição isolada em qualquer um dos lados.
    """
    textuais = [_hit("so_fts"), _hit("ambos")]
    vetoriais = [_hit("ambos"), _hit("so_vet")]
    p = _hibrido(textuais, vetoriais)

    ids = [h["id"] for h in p.search(Intent(raw="q", text="q"))]
    assert ids[0] == "ambos", ids


def test_hit_do_fts_vence_como_base():
    """O `fts_rank` verdadeiro não pode ser sobrescrito pelo zero do braço vetorial.

    O ranking consome `fts_rank` como um dos fatores; deixar o zero vencer
    apagaria o sinal textual de quem apareceu nos dois lados.
    """
    textual = _hit("x")
    textual["fts_rank"] = 0.9
    vetorial = _hit("x")
    vetorial["fts_rank"] = 0.0

    p = _hibrido([textual], [vetorial])
    (hit,) = p.search(Intent(raw="q", text="q"))
    assert hit["fts_rank"] == 0.9


def test_vector_rank_e_anotado_para_o_ranking():
    """ADR-010 D4: a posição vetorial vira sinal disponível ao ranking."""
    p = _hibrido([_hit("a")], [_hit("b"), _hit("a")])
    por_id = {h["id"]: h for h in p.search(Intent(raw="q", text="q"))}

    assert por_id["b"]["vector_rank"] == 1
    assert por_id["a"]["vector_rank"] == 2


def test_sem_texto_nao_chama_o_braco_vetorial():
    """Navegação por filtro puro não tem consulta a vetorizar.

    Chamar o modelo aqui gastaria latência do caminho crítico sem ter texto que
    justificasse — e o embedding de string vazia não significa nada.
    """
    chamou = False

    def _nao_deveria(*args, **kwargs):
        nonlocal chamou
        chamou = True
        return []

    p = HybridSearchProvider(session=None)
    p._fts = _FtsFake([_hit("a")])
    p._candidatos_vetoriais = _nao_deveria

    p.search(Intent(raw="", text=""), {"category": "notebooks"})
    assert not chamou


def test_falha_do_braco_vetorial_nao_derruba_a_busca():
    """A IA é complementar: o braço opcional não pode levar o obrigatório junto."""

    def _explode(*args, **kwargs):
        raise RuntimeError("modelo indisponível")

    p = HybridSearchProvider(session=None)
    p._fts = _FtsFake([_hit("a")])
    p._candidatos_vetoriais = _explode

    resultado = p.search(Intent(raw="notebook", text="notebook"))
    assert [h["id"] for h in resultado] == ["a"]


def test_uniao_respeita_o_pool_configurado():
    """`total` é o tamanho do pool (ADR-0007 D5.1) — a união não pode estourá-lo."""
    textuais = [_hit(f"t{i}") for i in range(settings.search_candidate_pool)]
    vetoriais = [_hit(f"v{i}") for i in range(50)]

    p = _hibrido(textuais, vetoriais)
    assert len(p.search(Intent(raw="q", text="q"))) == settings.search_candidate_pool


# --------------------------------------------------------------- filtros duros


def test_braco_vetorial_herda_os_filtros_duros():
    """O teste que mais importa aqui.

    Se o braço vetorial ignorasse `price_max`, a união devolveria produto acima
    do teto que o usuário pediu — sem erro, só resultado errado. As condições
    são compartilhadas justamente para que isso não seja possível.
    """
    intent = Intent(raw="notebook", text="notebook", category="notebooks", price_max=3000)
    conditions, price_max = _condicoes_duras(intent, {})

    assert price_max == 3000
    sql = " ".join(
        str(c.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        for c in conditions
    )
    assert "notebooks" in sql


@pytest.mark.parametrize(
    ("intent", "filtros", "esperado_no_sql"),
    [
        (Intent(raw="", text=""), {"brand": "acer"}, "acer"),
        (Intent(raw="", text="", category="headphones"), {}, "headphones"),
    ],
)
def test_condicoes_duras_cobrem_intent_e_filters(intent, filtros, esperado_no_sql):
    """Os dois braços têm de enxergar tanto o que o parser extraiu quanto o que veio da UI."""
    conditions, _ = _condicoes_duras(intent, filtros)
    sql = " ".join(
        str(c.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        for c in conditions
    )
    assert esperado_no_sql in sql


# ------------------------------------------------------------------- a flag


def test_flag_desligada_devolve_o_fts_puro(monkeypatch):
    """Desligada, não é um híbrido vazio: é o mesmo provider de antes de D4.

    Importa porque um híbrido com braço vetorial inerte ainda teria custo e
    caminho de código novo no request de todo mundo.
    """
    monkeypatch.setattr(settings, "hybrid_enabled", False)
    assert isinstance(get_search_provider(session=None), FtsSearchProvider)


def test_flag_ligada_devolve_o_hibrido(monkeypatch):
    monkeypatch.setattr(settings, "hybrid_enabled", True)
    assert isinstance(get_search_provider(session=None), HybridSearchProvider)
