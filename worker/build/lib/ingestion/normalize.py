"""Normalização: `RawProduct` → `NormalizedProduct` (ADR-0005 D3).

Deriva o slug determinístico (marca + modelo), parseia preços em formato BR e
padroniza marca/loja/categoria. Falhas estruturais (sem marca, sem preço válido)
viram `Rejection` — o lote não é derrubado (ADR-0005 D6: rejeita, loga e segue).
"""

import logging
import re
import unicodedata
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from ingestion.models import (
    NormalizedOffer,
    NormalizedProduct,
    RawOffer,
    RawProduct,
    Rejection,
)

logger = logging.getLogger(__name__)

DEFAULT_CURRENCY = "BRL"


def slugify(text: str) -> str:
    """Gera um slug ASCII estável: sem acentos, minúsculo, hifenizado."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def parse_price(value: str | float | int | None) -> Decimal:
    """Converte um preço cru em `Decimal`.

    Aceita número (``3999.9``) e string em formato BR (``"R$ 3.999,00"``),
    US (``"3999.90"``) e milhar (``"1.234.567,89"``). Lança ``ValueError`` se
    não houver preço válido.
    """
    if value is None:
        raise ValueError("preço ausente")
    if isinstance(value, bool):  # bool é subtipo de int: barra explicitamente
        raise ValueError(f"preço inválido: {value!r}")
    if isinstance(value, int | float):
        price = Decimal(str(value))
    else:
        digits = re.sub(r"[^\d,.-]", "", str(value)).strip()
        if not re.search(r"\d", digits):
            raise ValueError(f"preço sem dígitos: {value!r}")
        if "," in digits:
            # vírgula é o separador decimal; pontos são milhar
            digits = digits.replace(".", "").replace(",", ".")
        elif digits.count(".") > 1:
            digits = digits.replace(".", "")  # múltiplos pontos = milhar
        elif digits.count(".") == 1 and len(digits.rsplit(".", 1)[1]) == 3:
            digits = digits.replace(".", "")  # ex.: "3.999" = milhar (BR)
        try:
            price = Decimal(digits)
        except InvalidOperation as exc:
            raise ValueError(f"preço não numérico: {value!r}") from exc
    if price < 0:
        raise ValueError(f"preço negativo: {value!r}")
    return price


def _normalize_offer(raw: RawOffer) -> NormalizedOffer | None:
    """Normaliza uma oferta; devolve ``None`` (e loga) se for inaproveitável."""
    if not raw.store or not raw.store.strip() or raw.price is None:
        return None
    try:
        price = parse_price(raw.price)
    except ValueError as exc:
        logger.warning("Oferta ignorada (loja=%s): %s", raw.store, exc)
        return None
    return NormalizedOffer(
        store_slug=slugify(raw.store),
        store_name=raw.store.strip(),
        price=price,
        currency=(raw.currency or DEFAULT_CURRENCY).strip().upper(),
        url=raw.url,
    )


def normalize_one(raw: RawProduct) -> NormalizedProduct:
    """Normaliza um único produto. Lança ``ValueError`` em falha estrutural."""
    if not raw.brand or not raw.brand.strip():
        raise ValueError("marca ausente (obrigatória para o slug e o catálogo)")
    brand_name = raw.brand.strip()

    slug = slugify(f"{brand_name} {raw.model or raw.name}")
    if not slug:
        raise ValueError("não foi possível derivar um slug")

    category_slug = slugify(raw.category)
    if not category_slug:
        raise ValueError("categoria ausente/inválida")

    offers = [o for o in map(_normalize_offer, raw.offers) if o is not None]

    return NormalizedProduct(
        slug=slug,
        name=raw.name.strip(),
        category_slug=category_slug,
        brand_slug=slugify(brand_name),
        brand_name=brand_name,
        model=raw.model.strip() if raw.model else None,
        description=raw.description.strip() if raw.description else None,
        specs=raw.specs,
        offers=offers,
    )


def normalize(raws: Iterable[RawProduct]) -> tuple[list[NormalizedProduct], list[Rejection]]:
    """Normaliza um lote, deduplicando por slug e coletando rejeições."""
    normalized: list[NormalizedProduct] = []
    rejected: list[Rejection] = []
    seen: set[str] = set()

    for raw in raws:
        try:
            product = normalize_one(raw)
        except ValueError as exc:
            logger.warning("Produto rejeitado na normalização (%s): %s", raw.name, exc)
            rejected.append(Rejection(name=raw.name, reasons=[str(exc)]))
            continue

        if product.slug in seen:
            logger.warning("Slug duplicado no lote, mantendo o primeiro: %s", product.slug)
            rejected.append(Rejection(name=raw.name, reasons=[f"slug duplicado: {product.slug}"]))
            continue

        seen.add(product.slug)
        normalized.append(product)

    return normalized, rejected
