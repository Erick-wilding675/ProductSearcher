"""Testes do endpoint GET /products/{id}.

O repositório é substituído por um fake (dependency override): cobre o contrato
HTTP (achado -> 200 com detalhe; não achado -> 404) sem precisar de banco.
"""

import pytest
from fastapi.testclient import TestClient

from app.catalog.repository import get_catalog_repository
from app.catalog.schemas import OfferOut, ProductDetailOut
from app.main import app


class _FakeRepo:
    def __init__(self, product: ProductDetailOut | None) -> None:
        self._product = product

    def get_product(self, product_id: str) -> ProductDetailOut | None:
        return self._product


def _client(product: ProductDetailOut | None) -> TestClient:
    app.dependency_overrides[get_catalog_repository] = lambda: _FakeRepo(product)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _limpa_overrides():
    yield
    app.dependency_overrides.clear()


def test_get_product_retorna_detalhe():
    produto = ProductDetailOut(
        id="11111111-1111-1111-1111-111111111111",
        slug="dell-xps-13",
        name="Dell XPS 13",
        model="9340",
        description="Ultrabook",
        category="notebooks",
        brand="Dell",
        specs={"ram_gb": 16, "storage_type": "SSD"},
        offers=[OfferOut(store="Loja A", price="8999.00", currency="BRL", url="https://x")],
    )
    resp = _client(produto).get("/products/11111111-1111-1111-1111-111111111111")

    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "dell-xps-13"
    assert body["specs"]["ram_gb"] == 16
    assert body["offers"][0]["store"] == "Loja A"
    assert body["offers"][0]["url"] == "https://x"


def test_get_product_inexistente_retorna_404():
    resp = _client(None).get("/products/does-not-exist")

    assert resp.status_code == 404
