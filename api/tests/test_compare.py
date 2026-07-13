"""Testes do POST /compare (comparação alinhada de produtos).

O repositório é substituído por um fake, cobrindo o contrato HTTP e a lógica de
alinhamento sem precisar de banco. `build_comparison` também é testada isolada.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.catalog.repository import get_catalog_repository
from app.catalog.schemas import CompareProduct
from app.main import app
from app.search.comparison import build_comparison


class _FakeRepo:
    def __init__(self, produtos: list[CompareProduct]) -> None:
        self._by_id = {p.id: p for p in produtos}

    def get_products_by_ids(self, ids: list[str]) -> list[CompareProduct]:
        return [self._by_id[i] for i in ids if i in self._by_id]


def _client(produtos: list[CompareProduct]) -> TestClient:
    app.dependency_overrides[get_catalog_repository] = lambda: _FakeRepo(produtos)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _limpa_overrides():
    yield
    app.dependency_overrides.clear()


def _p(pid: str, category: str, specs: dict, min_price=None) -> CompareProduct:
    return CompareProduct(
        id=pid, name=pid.upper(), category=category, min_price=min_price, specs=specs
    )


# ---- build_comparison (função pura) ----


def test_build_comparison_tolera_valores_nao_hashaveis():
    # JSONB permite listas/dicts; a deteccao de diferenca nao pode quebrar (era 500).
    produtos = [
        _p("a", "notebooks", {"ports": ["USB-C", "HDMI"], "ram_gb": 16}),
        _p("b", "notebooks", {"ports": ["USB-C"], "ram_gb": 16}),
    ]
    out = build_comparison(produtos)
    attrs = {a.key: a for a in out.attributes}
    assert attrs["ports"].differ is True
    assert attrs["ram_gb"].differ is False


def test_build_comparison_alinha_e_marca_diferencas():
    produtos = [
        _p("a", "notebooks", {"ram_gb": 16, "cpu": "i7"}),
        _p("b", "notebooks", {"ram_gb": 8, "cpu": "i7"}),
    ]
    out = build_comparison(produtos)
    attrs = {a.key: a for a in out.attributes}

    assert out.category == "notebooks"
    assert attrs["ram_gb"].values == [16, 8]
    assert attrs["ram_gb"].differ is True
    assert attrs["cpu"].differ is False


def test_build_comparison_marca_melhor_valor():
    produtos = [
        _p("a", "notebooks", {"ram_gb": 16}, Decimal("4000")),
        _p("b", "notebooks", {"ram_gb": 8}, Decimal("3000")),
    ]
    out = build_comparison(produtos)
    assert out.best_value_id == "b"  # mais barato
    precos = {p.id: p.min_price for p in out.products}
    assert precos["b"] == Decimal("3000")


def test_build_comparison_melhor_valor_empate_vira_none():
    produtos = [
        _p("a", "notebooks", {}, Decimal("3000")),
        _p("b", "notebooks", {}, Decimal("3000")),
    ]
    assert build_comparison(produtos).best_value_id is None


# ---- endpoint ----


def test_compare_ok():
    produtos = [_p("a", "notebooks", {"ram_gb": 16}), _p("b", "notebooks", {"ram_gb": 8})]
    resp = _client(produtos).post("/compare", json={"product_ids": ["a", "b"]})

    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "notebooks"
    assert body["attributes"][0]["key"] == "ram_gb"
    assert body["attributes"][0]["differ"] is True


def test_compare_expoe_melhor_valor():
    produtos = [
        _p("a", "notebooks", {"ram_gb": 16}, Decimal("4999.00")),
        _p("b", "notebooks", {"ram_gb": 8}, Decimal("2999.00")),
    ]
    resp = _client(produtos).post("/compare", json={"product_ids": ["a", "b"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["best_value_id"] == "b"
    assert body["products"][0]["min_price"] == "4999.00"


def test_compare_categorias_diferentes_400():
    produtos = [_p("a", "notebooks", {"ram_gb": 16}), _p("b", "headphones", {"anc": True})]
    resp = _client(produtos).post("/compare", json={"product_ids": ["a", "b"]})

    assert resp.status_code == 400


def test_compare_produto_inexistente_404():
    produtos = [_p("a", "notebooks", {"ram_gb": 16})]
    resp = _client(produtos).post("/compare", json={"product_ids": ["a", "b"]})

    assert resp.status_code == 404


def test_compare_menos_de_dois_422():
    resp = _client([]).post("/compare", json={"product_ids": ["a"]})

    assert resp.status_code == 422
