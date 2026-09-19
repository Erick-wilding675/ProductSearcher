"""Regras de qualidade de dados aplicadas após a normalização.

Este módulo detecta dados suspeitos, mas não corrige nem remove valores vindos
da fonte. A decisão de persistência e classificação fica a cargo da etapa de
carga, preservando o valor original para auditoria.
"""

import logging
import math
from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from statistics import median

from ingestion.models import NormalizedProduct, OfferRejection

logger = logging.getLogger(__name__)

# A oferta precisa superar os dois limites para ser considerada uma anomalia
# extrema. O P99 protege categorias com cauda longa, como headphones premium.
PRICE_OUTLIER_MEDIAN_MULTIPLIER = Decimal("5")
PRICE_OUTLIER_P99_MULTIPLIER = Decimal("2")

# Evita inferência estatística em categorias com amostras pequenas.
MIN_PRICE_SAMPLE_SIZE = 10


def _percentile(values: list[Decimal], percentile: Decimal) -> Decimal:
    """Calcula percentil pelo método nearest-rank."""
    ordered = sorted(values)

    rank = math.ceil(float(percentile) * len(ordered))

    index = max(0, rank - 1)

    return ordered[index]


def detect_price_outliers(
    products: Iterable[NormalizedProduct],
) -> tuple[list[NormalizedProduct], list[OfferRejection]]:
    """Detecta preços extremamente altos dentro da própria categoria.

    Uma oferta só é classificada como suspeita quando supera o maior entre:

        mediana * PRICE_OUTLIER_MEDIAN_MULTIPLIER
        P99     * PRICE_OUTLIER_P99_MULTIPLIER

    O P99 reduz falsos positivos em categorias naturalmente heterogêneas ou
    com produtos premium.

    Nenhuma oferta é removida ou corrigida nesta etapa.
    """
    products = list(products)

    prices_by_category: dict[str, list[Decimal]] = defaultdict(list)

    for product in products:
        for offer in product.offers:
            if offer.price > 0:
                prices_by_category[product.category_slug].append(offer.price)

    thresholds: dict[str, Decimal] = {}

    for category, prices in prices_by_category.items():
        if len(prices) < MIN_PRICE_SAMPLE_SIZE:
            logger.info(
                "Qualidade de preço não aplicada à categoria %s: amostra insuficiente (%d < %d)",
                category,
                len(prices),
                MIN_PRICE_SAMPLE_SIZE,
            )
            continue

        category_median = Decimal(str(median(prices)))
        category_p99 = _percentile(
            prices,
            Decimal("0.99"),
        )

        median_threshold = category_median * PRICE_OUTLIER_MEDIAN_MULTIPLIER

        p99_threshold = category_p99 * PRICE_OUTLIER_P99_MULTIPLIER

        threshold = max(
            median_threshold,
            p99_threshold,
        )

        thresholds[category] = threshold

        logger.info(
            "Limite de qualidade para %s: mediana=%s, p99=%s, threshold=%s",
            category,
            category_median,
            category_p99,
            threshold,
        )

    rejected: list[OfferRejection] = []

    for product in products:
        threshold = thresholds.get(product.category_slug)

        if threshold is None:
            continue

        for offer in product.offers:
            if offer.price < threshold:
                continue

            reason = (
                f"preço suspeito: {offer.price} excede "
                f"o limite estatístico da categoria "
                f"({threshold})"
            )

            logger.warning(
                "Oferta classificada como suspeita (produto=%s, loja=%s, preço=%s): %s",
                product.name,
                offer.store_name,
                offer.price,
                reason,
            )

            rejected.append(
                OfferRejection(
                    product_slug=product.slug,
                    product_name=product.name,
                    store_slug=offer.store_slug,
                    store_name=offer.store_name,
                    price=offer.price,
                    reason=reason,
                )
            )

    return products, rejected
