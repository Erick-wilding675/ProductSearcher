"""Testes do endpoint GET /categories.

O repositório é substituído por um fake (dependency override), então o teste
cobre o contrato HTTP (rota, formato, status) sem precisar de banco.
"""

import pytest
from fastapi.testclient import TestClient

from app.catalog.repository import get_catalog_repository
from app.catalog.schemas import CategoryOut
from app.main import app


class _FakeRepo:
    def __init__(self, categories: list[CategoryOut]) -> None:
        self._categories = categories

    def get_categories(self) -> list[CategoryOut]:
        return self._categories


def _client(categories: list[CategoryOut]) -> TestClient:
    app.dependency_overrides[get_catalog_repository] = lambda: _FakeRepo(categories)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _limpa_overrides():
    yield
    app.dependency_overrides.clear()


def test_get_categories_retorna_cobertas():
    categorias = [
        CategoryOut(slug="headphones", name="Fones de ouvido", product_count=2),
        CategoryOut(slug="notebooks", name="Notebooks", product_count=3),
    ]
    resp = _client(categorias).get("/categories")

    assert resp.status_code == 200
    assert resp.json() == [
        {"slug": "headphones", "name": "Fones de ouvido", "product_count": 2},
        {"slug": "notebooks", "name": "Notebooks", "product_count": 3},
    ]


def test_get_categories_catalogo_vazio():
    resp = _client([]).get("/categories")

    assert resp.status_code == 200
    assert resp.json() == []
