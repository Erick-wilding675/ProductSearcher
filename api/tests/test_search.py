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


def _empty_response() -> SearchResponse:
    return SearchResponse(
        page=1,
        page_size=20,
        total=0,
        results=[],
    )


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

    # Os filtros da query chegam ao service.
    assert service.recebido["q"] == "dell"
    assert service.recebido["category"] == "notebooks"
    assert service.recebido["price_max"] == 5000
    assert service.recebido["sort"] == "price_asc"
    assert service.recebido["page"] == 2

    # Sem preferência explícita, o ranking mantém o comportamento anterior.
    assert service.recebido["rank_by"] == "relevance"
    assert service.recebido["rank_brand"] is None
    assert service.recebido["rank_spec"] is None
    assert service.recebido["rank_spec_value"] is None


def test_search_rejeita_parametros_invalidos():
    service = _FakeSearchService(_empty_response())
    client = _client(service)

    # sort fora do enum
    assert client.get("/search?sort=xpto").status_code == 422

    # rank_by fora do enum
    assert client.get("/search?rank_by=xpto").status_code == 422

    # page >= 1
    assert client.get("/search?page=0").status_code == 422

    # price_max >= 0
    assert client.get("/search?price_max=-1").status_code == 422


def test_search_repassa_filtro_de_atributos():
    service = _FakeSearchService(_empty_response())

    resp = _client(service).get('/search?attrs={"ram_gb":16,"anc":true}')

    assert resp.status_code == 200

    assert service.recebido["attributes"] == {
        "ram_gb": 16,
        "anc": True,
    }


def test_search_attrs_invalido_422():
    service = _FakeSearchService(_empty_response())
    client = _client(service)

    # JSON inválido.
    assert client.get("/search?attrs=notjson").status_code == 422

    # JSON válido, mas não é objeto.
    assert client.get("/search?attrs=[1,2]").status_code == 422


def test_rank_by_brand_exige_rank_brand():
    service = _FakeSearchService(_empty_response())

    resp = _client(service).get("/search?q=notebook&rank_by=brand")

    assert resp.status_code == 422

    assert resp.json()["detail"] == ("rank_brand é obrigatório quando rank_by=brand")

    # A validação acontece no router:
    # o service nem deve ser chamado.
    assert service.recebido == {}


def test_rank_by_brand_repassa_marca_ao_service():
    service = _FakeSearchService(_empty_response())

    resp = _client(service).get("/search?q=notebook&rank_by=brand&rank_brand=acer")

    assert resp.status_code == 200

    assert service.recebido["rank_by"] == "brand"
    assert service.recebido["rank_brand"] == "acer"
    assert service.recebido["rank_spec"] is None
    assert service.recebido["rank_spec_value"] is None


def test_rank_by_spec_exige_rank_spec():
    service = _FakeSearchService(_empty_response())

    resp = _client(service).get("/search?q=notebook&rank_by=spec&rank_spec_value=RTX%204050")

    assert resp.status_code == 422

    assert resp.json()["detail"] == ("rank_spec é obrigatório quando rank_by=spec")

    assert service.recebido == {}


def test_rank_by_spec_exige_rank_spec_value():
    service = _FakeSearchService(_empty_response())

    resp = _client(service).get("/search?q=notebook&rank_by=spec&rank_spec=gpu")

    assert resp.status_code == 422

    assert resp.json()["detail"] == ("rank_spec_value é obrigatório quando rank_by=spec")

    assert service.recebido == {}


def test_rank_by_spec_repassa_spec_e_valor_ao_service():
    service = _FakeSearchService(_empty_response())

    resp = _client(service).get(
        "/search?q=notebook%20gamer&rank_by=spec&rank_spec=gpu&rank_spec_value=RTX%204050"
    )

    assert resp.status_code == 200

    assert service.recebido["rank_by"] == "spec"
    assert service.recebido["rank_spec"] == "gpu"
    assert service.recebido["rank_spec_value"] == "RTX 4050"


@pytest.mark.parametrize(
    ("query_value", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("false", False),
        ("FALSE", False),
    ],
)
def test_rank_spec_value_booleano_e_convertido(
    query_value,
    expected,
):
    service = _FakeSearchService(_empty_response())

    resp = _client(service).get(
        f"/search?rank_by=spec&rank_spec=touchscreen&rank_spec_value={query_value}"
    )

    assert resp.status_code == 200
    assert service.recebido["rank_spec_value"] is expected


def test_rank_spec_value_numerico_permanece_string():
    """O ranking faz comparação tolerante entre string e número."""

    service = _FakeSearchService(_empty_response())

    resp = _client(service).get("/search?rank_by=spec&rank_spec=ram_gb&rank_spec_value=16")

    assert resp.status_code == 200

    assert service.recebido["rank_spec_value"] == "16"


def test_rank_by_price_e_aceito():
    """Preço é um critério válido de priorização.

    A escolha automática de `sort=price_asc` pertence à integração da UI;
    o contrato HTTP continua mantendo `rank_by` e `sort` independentes.
    """

    service = _FakeSearchService(_empty_response())

    resp = _client(service).get("/search?q=notebook&rank_by=price")

    assert resp.status_code == 200

    assert service.recebido["rank_by"] == "price"

    # Sem `sort` explícito, o contrato HTTP mantém seu default.
    assert service.recebido["sort"] == "relevance"


def test_rank_by_e_sort_sao_independentes():
    """Priorizar e ordenar são controles diferentes."""

    service = _FakeSearchService(_empty_response())

    resp = _client(service).get("/search?q=notebook&rank_by=brand&rank_brand=acer&sort=price_desc")

    assert resp.status_code == 200

    assert service.recebido["rank_by"] == "brand"
    assert service.recebido["rank_brand"] == "acer"
    assert service.recebido["sort"] == "price_desc"
