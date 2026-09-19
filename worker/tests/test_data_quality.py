from decimal import Decimal

from ingestion.data_quality import detect_price_outliers
from ingestion.models import NormalizedOffer, NormalizedProduct


def _offer(price: str, store: str = "Loja") -> NormalizedOffer:
    return NormalizedOffer(
        store_slug=store.lower().replace(" ", "-"),
        store_name=store,
        price=Decimal(price),
        currency="BRL",
    )


def _product(
    name: str,
    price: str,
    category: str = "notebooks",
) -> NormalizedProduct:
    return NormalizedProduct(
        slug=name.lower().replace(" ", "-"),
        name=name,
        category_slug=category,
        brand_slug="marca",
        brand_name="Marca",
        offers=[_offer(price)],
    )


def _notebook_reference_prices() -> list[NormalizedProduct]:
    """Amostra estável grande o bastante para cálculo útil de P99."""
    return [
        _product(
            f"Notebook {index}",
            str(4000 + index * 25),
        )
        for index in range(1, 102)
    ]


def test_detecta_outlier_sem_remover_oferta():
    products = _notebook_reference_prices()
    products.append(
        _product(
            "Notebook suspeito",
            "2300000",
        )
    )

    detected_products, rejected = detect_price_outliers(products)

    assert len(detected_products) == 102

    suspect = detected_products[-1]

    assert suspect.name == "Notebook suspeito"
    assert len(suspect.offers) == 1
    assert suspect.offers[0].price == Decimal("2300000")

    assert len(rejected) == 1
    assert rejected[0].product_slug == "notebook-suspeito"
    assert rejected[0].product_name == "Notebook suspeito"
    assert rejected[0].store_slug == "loja"
    assert rejected[0].price == Decimal("2300000")


def test_preserva_preco_alto_mas_plausivel():
    products = _notebook_reference_prices()
    products.append(
        _product(
            "Notebook Premium",
            "21000",
        )
    )

    detected_products, rejected = detect_price_outliers(products)

    assert rejected == []
    assert detected_products[-1].offers[0].price == Decimal("21000")


def test_detecta_apenas_oferta_suspeita_do_produto():
    products = _notebook_reference_prices()

    product = _product(
        "Notebook especial",
        "5000",
    )

    product.offers.append(
        _offer(
            "2300000",
            "Outra Loja",
        )
    )

    products.append(product)

    detected_products, rejected = detect_price_outliers(products)

    notebook = detected_products[-1]

    # As duas ofertas continuam preservadas para persistência/auditoria.
    assert len(notebook.offers) == 2
    assert notebook.offers[0].price == Decimal("5000")
    assert notebook.offers[1].price == Decimal("2300000")

    assert len(rejected) == 1
    assert rejected[0].store_slug == "outra-loja"
    assert rejected[0].price == Decimal("2300000")


def test_calcula_limite_por_categoria():
    notebooks = _notebook_reference_prices()
    notebooks.append(
        _product(
            "Notebook outlier",
            "100000",
            "notebooks",
        )
    )

    headphones = [
        _product(
            f"Fone {index}",
            str(100 + index * 2),
            "headphones",
        )
        for index in range(1, 102)
    ]

    products = notebooks + headphones

    detected_products, rejected = detect_price_outliers(products)

    assert len(rejected) == 1
    assert rejected[0].product_name == "Notebook outlier"

    fones = [product for product in detected_products if product.category_slug == "headphones"]

    assert all(product.offers for product in fones)


def test_nao_classifica_com_amostra_pequena():
    products = [
        _product("Notebook A", "4000"),
        _product("Notebook B", "5000"),
        _product("Notebook suspeito", "2300000"),
    ]

    detected_products, rejected = detect_price_outliers(products)

    assert len(detected_products) == 3
    assert rejected == []

    # Com pouca evidência estatística, nenhuma oferta é rejeitada
    # automaticamente.
    assert detected_products[-1].offers[0].price == Decimal("2300000")


def test_nao_rejeita_produto_premium_em_categoria_de_cauda_longa():
    # Maioria da categoria concentrada em preços baixos.
    products = [
        _product(
            f"Fone {index}",
            str(80 + index * 2),
            "headphones",
        )
        for index in range(1, 101)
    ]

    # A própria categoria possui uma cauda premium legítima.
    products.append(
        _product(
            "Fone Premium Referência",
            "1750",
            "headphones",
        )
    )

    products.append(
        _product(
            "Fone Premium",
            "2199",
            "headphones",
        )
    )

    detected_products, rejected = detect_price_outliers(products)

    assert rejected == []
    assert detected_products[-1].offers[0].price == Decimal("2199")
