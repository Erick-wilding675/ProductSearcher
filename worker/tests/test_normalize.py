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


def test_normalize_lote_funde_repetido_e_rejeita_sem_marca():
    raws = [
        RawProduct(source="seed", name="A", brand="Dell", category="notebooks", model="x"),
        RawProduct(source="seed", name="A dup", brand="Dell", category="notebooks", model="x"),
        RawProduct(source="seed", name="Sem marca", category="notebooks"),
    ]
    normalized, rejected = normalize(raws)

    # Mesma identidade vira um produto só (não é mais descarte) — ADR-0009.
    assert [p.slug for p in normalized] == ["dell-x"]
    assert [r.reasons[0] for r in rejected] == [
        "marca ausente (obrigatória para o slug e o catálogo)"
    ]


def test_normalize_sku_separa_produtos_de_mesmo_modelo():
    # Os "IdeaPad Slim 3 15IRH10" i5 e i7 têm o mesmo modelo e SKUs diferentes:
    # sem o SKU no slug, um sobrescreveria o outro.
    raws = [
        RawProduct(
            source="seed",
            name="IdeaPad i5",
            brand="Lenovo",
            category="notebooks",
            model="IdeaPad Slim 3 15IRH10",
            catalog_parent_id="MLB1",
            catalog_sku="83NS0002BR",
        ),
        RawProduct(
            source="seed",
            name="IdeaPad i7",
            brand="Lenovo",
            category="notebooks",
            model="IdeaPad Slim 3 15IRH10",
            catalog_parent_id="MLB2",
            catalog_sku="83NS0004BR",
        ),
    ]
    normalized, rejected = normalize(raws)

    assert [p.slug for p in normalized] == [
        "lenovo-ideapad-slim-3-15irh10-83ns0002br",
        "lenovo-ideapad-slim-3-15irh10-83ns0004br",
    ]
    assert rejected == []


def test_normalize_funde_variantes_de_cor_somando_ofertas():
    # Os cinco "Dapon H02D" do seed compartilham o mesmo pai: mesma coisa, cores
    # diferentes. Fundir soma os vendedores em vez de jogar oferta fora.
    def variante(nome, loja, preco):
        return RawProduct(
            source="seed",
            name=nome,
            brand="Dapon",
            category="headphones",
            model="H02D",
            catalog_parent_id="MLB24117256",
            offers=[{"store": loja, "price": preco}],
        )

    normalized, rejected = normalize(
        [variante("Dapon H02D Preto", "Loja A", "100"), variante("Dapon H02D Rosa", "Loja B", "90")]
    )

    assert len(normalized) == 1
    assert {o.store_name for o in normalized[0].offers} == {"Loja A", "Loja B"}
    assert rejected == []


def test_normalize_desambigua_slug_de_identidades_diferentes():
    # Sem SKU para desempatar, dois produtos distintos cairiam no mesmo slug e um
    # sobrescreveria o outro no upsert. O sufixo evita a perda silenciosa.
    raws = [
        RawProduct(
            source="seed",
            name="X",
            brand="Dell",
            category="notebooks",
            model="Inspiron",
            catalog_parent_id="MLB1",
        ),
        RawProduct(
            source="seed",
            name="Y",
            brand="Dell",
            category="notebooks",
            model="Inspiron",
            catalog_parent_id="MLB2",
        ),
    ]
    normalized, _ = normalize(raws)

    assert len({p.slug for p in normalized}) == 2
    assert normalized[0].slug == "dell-inspiron"
    assert normalized[1].slug == "dell-inspiron-mlb2"
