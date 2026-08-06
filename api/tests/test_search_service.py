"""Composição do pipeline de busca (ADR-0007) — sem banco.

Provider e ranking são fakes: aqui interessa como o `SearchService` liga as peças
(precedência de filtros, ordenação, paginação, exposição dos critérios), não o SQL
nem a fórmula do score, que têm testes próprios.
"""

import pytest

from app.search.intent import Intent, RuleBasedIntentParser
from app.search.ranking import DeterministicRanking
from app.search.service import PAGE_SIZE, SearchService


def _hit(nome: str, preco: float | None = None, rank: float = 0.5) -> dict:
    return {
        "id": f"id-{nome}",
        "slug": nome.lower().replace(" ", "-"),
        "name": nome,
        "category": "notebooks",
        "brand": "Dell",
        "min_price": preco,
        "fts_rank": rank,
        "attributes": {},
    }


class _FakeProvider:
    def __init__(self, hits: list[dict]) -> None:
        self._hits = hits
        self.intent: Intent | None = None
        self.filters: dict = {}

    def search(self, intent, filters=None, page=1):
        self.intent, self.filters = intent, filters or {}
        return self._hits


def _service(hits: list[dict]) -> tuple[SearchService, _FakeProvider]:
    provider = _FakeProvider(hits)
    return (
        SearchService(RuleBasedIntentParser(), provider, DeterministicRanking()),
        provider,
    )


def test_consulta_passa_pelo_parser_antes_do_retrieval():
    """O provider recebe o Intent interpretado, não a string crua."""
    service, provider = _service([])
    service.search(q="melhor notebook até R$5000")

    assert provider.intent.category == "notebooks"
    assert provider.intent.price_max == 5000.0
    assert provider.intent.text == "notebook"  # sem filler nem preço


def test_filtros_da_ui_chegam_ao_provider():
    service, provider = _service([])
    service.search(q="notebook", brand="dell", price_max=3000, attributes={"ram_gb": 16})

    assert provider.filters["brand"] == "dell"
    assert provider.filters["price_max"] == 3000
    assert provider.filters["attributes"] == {"ram_gb": 16}


def test_atributos_do_parser_e_da_ui_se_somam():
    """A UI complementa o que o parser extraiu, sem descartá-lo."""
    service, provider = _service([])
    service.search(q="notebook com ssd", attributes={"ram_gb": 16})

    assert provider.filters["attributes"] == {"storage_type": "SSD", "ram_gb": 16}


def test_resposta_expoe_os_criterios_do_ranking():
    """RF-31: a UI precisa dos critérios para explicar a ordenação."""
    service, _ = _service([_hit("Dell XPS")])
    resposta = service.search(q="notebook")

    fatores = {c.factor for c in resposta.criteria}
    assert fatores == {"relevance", "price", "attributes"}
    assert any(c.active for c in resposta.criteria)


def test_item_carrega_score_e_fatores():
    """RF-30/31: cada item explica a própria posição."""
    service, _ = _service([_hit("Dell XPS")])
    item = service.search(q="notebook").results[0]

    assert item.score > 0
    assert set(item.factors) == {"relevance", "price", "attributes"}


def test_ordem_default_e_a_do_ranking():
    service, _ = _service([_hit("Fraco", rank=0.1), _hit("Forte", rank=0.9)])
    nomes = [i.name for i in service.search(q="notebook").results]
    assert nomes == ["Forte", "Fraco"]


@pytest.mark.parametrize(
    ("sort", "esperado"),
    [
        ("price_asc", ["Barato", "Caro"]),
        ("price_desc", ["Caro", "Barato"]),
        ("name", ["Barato", "Caro"]),
    ],
)
def test_ordenacoes_explicitas(sort: str, esperado: list[str]):
    service, _ = _service([_hit("Caro", 9000.0), _hit("Barato", 100.0)])
    nomes = [i.name for i in service.search(q="notebook", sort=sort).results]
    assert nomes == esperado


def test_produto_sem_preco_vai_para_o_fim_na_ordenacao_por_preco():
    """Sem preço não é "mais barato" — senão ele lidera o price_asc indevidamente."""
    service, _ = _service([_hit("Sem preco", None), _hit("Com preco", 500.0)])
    nomes = [i.name for i in service.search(q="notebook", sort="price_asc").results]
    assert nomes == ["Com preco", "Sem preco"]


def test_paginacao_fatiaa_o_conjunto_ranqueado():
    hits = [_hit(f"Produto {i:02d}", rank=1.0 - i / 100) for i in range(PAGE_SIZE + 5)]
    service, _ = _service(hits)

    p1 = service.search(q="notebook", page=1)
    p2 = service.search(q="notebook", page=2)

    assert len(p1.results) == PAGE_SIZE
    assert len(p2.results) == 5
    assert p1.total == p2.total == PAGE_SIZE + 5  # total é o conjunto todo
    assert not {i.id for i in p1.results} & {i.id for i in p2.results}


def test_pagina_alem_do_fim_volta_vazia_sem_erro():
    service, _ = _service([_hit("Unico")])
    resposta = service.search(q="notebook", page=99)
    assert resposta.results == []
    assert resposta.total == 1


def test_busca_sem_texto_nao_quebra():
    """Navegação só por filtros (ex.: categoria na sidebar) não tem `q`."""
    service, provider = _service([_hit("Dell XPS")])
    resposta = service.search(category="notebooks")

    assert provider.intent.raw == ""
    assert len(resposta.results) == 1
