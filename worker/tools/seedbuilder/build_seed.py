"""CSV de listagem do Apify → ``worker/seed/products/<categoria>.yaml`` (RawProduct).

Specs = título (fallback) sobrepostas pela API do ML quando há ``--token`` (ou a env
``ML_ACCESS_TOKEN``). O que sair sem spec obrigatória é rejeitado depois no `load`
(ADR-0005 D6) — o seed guarda o que temos e o enriquecimento pode rodar de novo.

Uso:
    python -m tools.seedbuilder.build_seed \\
        --csv dataset_a.csv dataset_b.csv --category notebooks \\
        --out seed/products/notebooks.yaml [--token $ML_ACCESS_TOKEN]
"""

import argparse
import csv
import logging
import os

import yaml

from tools.seedbuilder import mapping, ml_api
from tools.seedbuilder import title_parser as tp

logger = logging.getLogger(__name__)

DOMAIN_TO_CATEGORY = {"MLB-NOTEBOOKS": "notebooks", "MLB-HEADPHONES": "headphones"}
CATEGORY_DOMAINS = {"notebooks": {"MLB-NOTEBOOKS"}, "headphones": {"MLB-HEADPHONES"}}
ACCESSORY_PREFIXES = ("suporte", "espuma", "par de espuma", "almofada")


def _build_offer(row: dict) -> dict | None:
    price = (row.get("novoPreco") or "").strip()
    if not price:
        return None
    return {
        "store": (row.get("Vendedor") or "").strip() or "Mercado Livre",
        "price": price,
        "currency": (row.get("Moeda") or "BRL").strip() or "BRL",
        "url": (row.get("zProdutoLink") or "").strip() or None,
    }


def build(rows: list[dict], category: str, token: str | None = None) -> list[dict]:
    """Monta a lista de produtos crus (formato `RawProduct`) a partir das linhas."""
    products: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        sku = (row.get("SKU") or "").strip()
        title = (row.get("eTituloProduto") or "").strip()
        domain = (row.get("produtoDomainID") or "").strip()
        allowed = CATEGORY_DOMAINS.get(category)
        if not sku or not title or sku in seen:
            continue
        if allowed and domain and domain not in allowed:
            continue
        if title.lower().lstrip().startswith(ACCESSORY_PREFIXES):
            continue
        seen.add(sku)

        specs = tp.parse_title(category, title)
        if token:
            ml_specs = mapping.map_attributes(category, ml_api.fetch_attributes(sku, token))
            specs = {**specs, **ml_specs}

        offer = _build_offer(row)
        products.append(
            {
                "source": "apify:mercadolivre",
                "external_id": sku,
                "name": title,
                "brand": (row.get("produtoMarca") or "").strip()
                or tp.extract_brand(category, title),
                "category": category,
                "specs": specs,
                "offers": [offer] if offer else [],
            }
        )
    return products


def main(argv: list[str] | None = None) -> list[dict]:
    from tools.seedbuilder.config import load_env

    load_env()
    parser = argparse.ArgumentParser(description="Gera o seed YAML a partir do CSV do Apify.")
    parser.add_argument("--csv", required=True, nargs="+", help="um ou mais CSVs do Apify")
    parser.add_argument("--category", help="Categoria (senão, inferida por produtoDomainID)")
    parser.add_argument("--out", required=True, help="Arquivo YAML de saída")
    parser.add_argument("--token", default=os.environ.get("ML_ACCESS_TOKEN"))
    args = parser.parse_args(argv)

    rows: list[dict] = []
    for path in args.csv:
        with open(path, encoding="utf-8-sig") as fh:
            rows.extend(csv.DictReader(fh))
    if not rows:
        raise SystemExit("CSV(s) vazio(s).")

    category = args.category or DOMAIN_TO_CATEGORY.get(
        (rows[0].get("produtoDomainID") or "").strip()
    )
    if not category:
        raise SystemExit("Não foi possível inferir a categoria; use --category.")

    products = build(rows, category, args.token)
    with open(args.out, "w", encoding="utf-8") as fh:
        yaml.safe_dump(products, fh, allow_unicode=True, sort_keys=False)
    logger.info("Gravados %d produtos em %s (token=%s)", len(products), args.out, bool(args.token))
    return products


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = main()
    print(f"Gravados {len(result)} produtos.")
