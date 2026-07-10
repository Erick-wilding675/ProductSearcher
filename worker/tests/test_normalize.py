from decimal import Decimal

import pytest

from ingestion.models import RawOffer, RawProduct
from ingestion.normalize import normalize, normalize_one, parse_price, slugify


def test_slugify_remove_acentos_e_normaliza():
    assert slugify("Fones de Ouvido") == "fones-de-ouvido"
    assert slugify("Dell Inspiron 15 5530") == "dell-inspiron-15-5530"
    assert slugify("  Áçãí+++TÊNIS  ") == "acai-tenis"


@pytest.mark.parametrize(
    "raw, esperado",
    [
        ("R$ 3.999,00", Decimal("3999.00")),
        ("3999.90", Decimal("3999.90")),
        ("1.234.567,89", Decimal("1234567.89")),
        ("R$ 3.999", Decimal("3999")),  # ponto de milhar sem centavos
        ("1500,50", Decimal("1500.50")),
        (3999.9, Decimal("3999.9")),
        (1500, Decimal("1500")),
    ],
)
def test_parse_price_formatos(raw, esperado):
    assert parse_price(raw) == esperado


@pytest.mark.parametrize("ruim", [None, "", "grátis", True, -10])
def test_parse_price_invalido(ruim):
    with pytest.raises(ValueError):
        parse_price(ruim)


def test_normalize_one_deriva_slug_e_ofertas():
    raw = RawProduct(
        source="seed",
        name="Inspiron 15",
        brand="Dell",
        category="Notebooks",
        model="i5530",
        specs={"ram_gb": 16},
        offers=[
            RawOffer(store="Amazon", price="R$ 3.999,00"),
            RawOffer(store=None, price="R$ 10,00"),  # sem loja → descartada
            RawOffer(store="Magalu", price="quebrado"),  # preço inválido → descartada
        ],
    )
    product = normalize_one(raw)
    assert product.slug == "dell-i5530"
    assert product.category_slug == "notebooks"
    assert product.brand_slug == "dell"
    assert [o.store_slug for o in product.offers] == ["amazon"]
    assert product.offers[0].price == Decimal("3999.00")
    assert product.offers[0].currency == "BRL"


def test_normalize_one_sem_marca_rejeita():
    raw = RawProduct(source="seed", name="Sem marca", category="notebooks")
    with pytest.raises(ValueError):
        normalize_one(raw)


def test_normalize_lote_dedup_e_rejeicoes():
    raws = [
        RawProduct(source="seed", name="A", brand="Dell", category="notebooks", model="x"),
        RawProduct(source="seed", name="A dup", brand="Dell", category="notebooks", model="x"),
        RawProduct(source="seed", name="Sem marca", category="notebooks"),
    ]
    normalized, rejected = normalize(raws)
    assert [p.slug for p in normalized] == ["dell-x"]
    assert len(rejected) == 2  # duplicado + sem marca
