"""Testes dos endpoints GET /categories e GET /brands.

O repositório é substituído por um fake (dependency override), então o teste
cobre o contrato HTTP (rota, formato, status) sem precisar de banco.
"""

import pytest
from fastapi.testclient import TestClient

from app.catalog.repository import get_catalog_repository
from app.catalog.schemas import BrandOut, CategoryOut
from app.main import app


class _FakeRepo:
    def __init__(
        self,
        categories: list[CategoryOut] | None = None,
        brands: list[BrandOut] | None = None,
    ) -> None:
        self._categories = categories or []
        self._brands = brands or []
        self.category_recebida: str | None = None

    def get_categories(self) -> list[CategoryOut]:
        return self._categories

    def get_brands(self, category: str | None = None) -> list[BrandOut]:
        # Guarda o argumento para o teste conferir que o ?category= chega ao repo.
        self.category_recebida = category
        return self._brands


def _client(repo: _FakeRepo) -> TestClient:
    app.dependency_overrides[get_catalog_repository] = lambda: repo
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
    resp = _client(_FakeRepo(categories=categorias)).get("/categories")

    assert resp.status_code == 200
    assert resp.json() == [
        {"slug": "headphones", "name": "Fones de ouvido", "product_count": 2},
        {"slug": "notebooks", "name": "Notebooks", "product_count": 3},
    ]


def test_get_categories_catalogo_vazio():
    resp = _client(_FakeRepo()).get("/categories")

    assert resp.status_code == 200
    assert resp.json() == []


def test_get_brands_retorna_presentes():
    marcas = [
        BrandOut(slug="dell", name="Dell", product_count=14),
        BrandOut(slug="havit", name="Havit", product_count=9),
    ]
    resp = _client(_FakeRepo(brands=marcas)).get("/brands")

    assert resp.status_code == 200
    assert resp.json() == [
        {"slug": "dell", "name": "Dell", "product_count": 14},
        {"slug": "havit", "name": "Havit", "product_count": 9},
    ]


def test_get_brands_repassa_filtro_de_categoria():
    repo = _FakeRepo(brands=[])
    resp = _client(repo).get("/brands", params={"category": "notebooks"})

    assert resp.status_code == 200
    assert repo.category_recebida == "notebooks"


def test_get_brands_sem_filtro_nao_restringe_categoria():
    repo = _FakeRepo(brands=[])
    resp = _client(repo).get("/brands")

    assert resp.status_code == 200
    assert repo.category_recebida is None


def test_get_brands_catalogo_vazio():
    resp = _client(_FakeRepo()).get("/brands")

    assert resp.status_code == 200
    assert resp.json() == []
