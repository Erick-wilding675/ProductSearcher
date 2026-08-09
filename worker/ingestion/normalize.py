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
        store_url=(raw.store_url or "").strip() or None,
        price=price,
        currency=(raw.currency or DEFAULT_CURRENCY).strip().upper(),
        url=raw.url,
    )


def normalize_one(raw: RawProduct) -> NormalizedProduct:
    """Normaliza um único produto. Lança ``ValueError`` em falha estrutural."""
    if not raw.brand or not raw.brand.strip():
        raise ValueError("marca ausente (obrigatória para o slug e o catálogo)")
    brand_name = raw.brand.strip()

    # O SKU do fabricante entra no slug porque `marca + modelo` NÃO é único: os
    # quatro "Lenovo IdeaPad Slim 3 15IRH10" do seed são produtos diferentes
    # (i5 e i7), e sem o SKU três deles seriam descartados como duplicata.
    # Ver ADR-0009.
    sku = (raw.catalog_sku or "").strip()
    base = raw.model or raw.name
    slug = slugify(f"{brand_name} {base} {sku}" if sku else f"{brand_name} {base}")
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


def _funde(destino: NormalizedProduct, origem: NormalizedProduct) -> None:
    """Absorve `origem` em `destino`: une as ofertas e preenche o que faltava.

    Variantes de cor do mesmo produto trazem, cada uma, os seus vendedores. Juntar
    é o que dá sentido ao "melhor valor" da comparação — descartar jogaria fora
    oferta boa, e manter cinco entradas idênticas na busca seria ruído.
    """
    lojas = {o.store_slug for o in destino.offers}
    destino.offers.extend(o for o in origem.offers if o.store_slug not in lojas)

    if not destino.model and origem.model:
        destino.model = origem.model
    if not destino.description and origem.description:
        destino.description = origem.description
    for chave, valor in (origem.specs or {}).items():
        destino.specs.setdefault(chave, valor)


def normalize(raws: Iterable[RawProduct]) -> tuple[list[NormalizedProduct], list[Rejection]]:
    """Normaliza um lote, fundindo variantes do mesmo produto.

    A identidade é o `catalog_parent_id` quando a fonte o fornece (variantes de
    cor compartilham o pai) e o `slug` quando não. Duas linhas da mesma identidade
    **não** são descarte: são o mesmo produto anunciado em cores/vendedores
    diferentes, e viram um só com as ofertas somadas (ADR-0009).
    """
    por_identidade: dict[str, NormalizedProduct] = {}
    ordem: list[str] = []
    rejected: list[Rejection] = []
    slugs: dict[str, str] = {}  # slug -> identidade que já o ocupa

    for raw in raws:
        try:
            product = normalize_one(raw)
        except ValueError as exc:
            logger.warning("Produto rejeitado na normalização (%s): %s", raw.name, exc)
            rejected.append(Rejection(name=raw.name, reasons=[str(exc)]))
            continue

        identidade = (raw.catalog_parent_id or "").strip() or product.slug
        existente = por_identidade.get(identidade)
        if existente is None:
            # Produtos distintos que caíram no mesmo slug (sem SKU para desempatar)
            # ganham sufixo da identidade. Sem isso o upsert por slug faria um
            # sobrescrever o outro em silêncio — pior que a rejeição de antes.
            dono = slugs.get(product.slug)
            if dono is not None and dono != identidade:
                product.slug = f"{product.slug}-{slugify(identidade)}"
                logger.info("Slug em conflito, desambiguado para %s", product.slug)
            slugs[product.slug] = identidade

            por_identidade[identidade] = product
            ordem.append(identidade)
            continue

        logger.info(
            "Variante do mesmo produto (%s): fundindo %s em %s",
            identidade,
            raw.name,
            existente.slug,
        )
        _funde(existente, product)

    return [por_identidade[i] for i in ordem], rejected
