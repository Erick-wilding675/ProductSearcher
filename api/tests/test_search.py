"""Testes do GET /search.

O `SearchService` é substituído por um fake: aqui cobrimos o **contrato HTTP**
(parâmetros aceitos, validação, formato da resposta). O pipeline em si —
parser, retrieval e ranking — é provado nos testes de cada peça e, ponta a
ponta, na suíte de relevância contra um Postgres real.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.search.schemas import SearchResponse, SearchResultItem
from app.search.service import get_search_service


class _FakeSearchService:
    def __init__(self, response: SearchResponse) -> None:
        self._response = response
        self.recebido: dict = {}

    def search(self, **kwargs) -> SearchResponse:
        self.recebido = kwargs
        return self._response


def _client(service: _FakeSearchService) -> TestClient:
    app.dependency_overrides[get_search_service] = lambda: service
    return TestClient(app)


@pytest.fixture(autouse=True)
def _limpa_overrides():
    yield
    app.dependency_overrides.clear()


def test_search_retorna_pagina_e_repassa_filtros():
    resposta = SearchResponse(
        page=2,
        page_size=20,
        total=1,
        results=[
            SearchResultItem(
                id="1",
                slug="dell-xps",
                name="Dell XPS",
                category="notebooks",
                brand="Dell",
                min_price="3999.00",
            )
        ],
    )
    service = _FakeSearchService(resposta)
    resp = _client(service).get(
        "/search?q=dell&category=notebooks&price_max=5000&sort=price_asc&page=2"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 2
    assert body["results"][0]["name"] == "Dell XPS"
    # os filtros da query chegam ao service
    assert service.recebido["q"] == "dell"
    assert service.recebido["category"] == "notebooks"
    assert service.recebido["price_max"] == 5000
    assert service.recebido["sort"] == "price_asc"
    assert service.recebido["page"] == 2


def test_search_rejeita_parametros_invalidos():
    service = _FakeSearchService(SearchResponse(page=1, page_size=20, total=0, results=[]))
    client = _client(service)
    assert client.get("/search?sort=xpto").status_code == 422  # sort fora do enum
    assert client.get("/search?page=0").status_code == 422  # page >= 1
    assert client.get("/search?price_max=-1").status_code == 422  # price_max >= 0


def test_search_repassa_filtro_de_atributos():
    service = _FakeSearchService(SearchResponse(page=1, page_size=20, total=0, results=[]))
    resp = _client(service).get('/search?attrs={"ram_gb":16,"anc":true}')
    assert resp.status_code == 200
    assert service.recebido["attributes"] == {"ram_gb": 16, "anc": True}


def test_search_attrs_invalido_422():
    service = _FakeSearchService(SearchResponse(page=1, page_size=20, total=0, results=[]))
    client = _client(service)
    assert client.get("/search?attrs=notjson").status_code == 422  # JSON inválido
    assert client.get("/search?attrs=[1,2]").status_code == 422  # não é objeto
