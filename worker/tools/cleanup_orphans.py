"""Remove do catálogo os produtos que o seed atual não produz mais.

Por que existe: o ADR-0009 mudou a chave natural do produto (o slug passou a
incluir o SKU do fabricante e variantes de cor foram fundidas). Como a carga é um
`upsert` por slug, as linhas gravadas sob a regra antiga **não são atualizadas —
ficam ao lado das novas**, duplicando produtos na busca.

Não roda sozinho e não é chamado pela ingestão: apagar dado é decisão de quem
opera o banco. Rode com `--dry-run` primeiro.

    python -m tools.cleanup_orphans --dry-run   # lista o que sairia
    python -m tools.cleanup_orphans             # apaga (pede confirmação)

A ordem respeita as FKs: price_history → offers → reviews → product_specs →
products. Lojas e marcas que ficarem sem uso são removidas no fim.
"""

import argparse
import logging
from pathlib import Path

import sqlalchemy as sa

from ingestion.normalize import normalize
from ingestion.pipeline import SEED_DIR
from ingestion.sources import SeedIngestionSource
from ingestion.validate import read_categories, validate

logger = logging.getLogger(__name__)


def slugs_do_seed(seed_dir: Path = SEED_DIR) -> tuple[set[str], list]:
    """Slugs que a ingestão produziria hoje — a régua do que deve existir."""
    categories = read_categories(seed_dir)
    schemas = {c.slug: c.attributes for c in categories}
    normalizados, _ = normalize(SeedIngestionSource(seed_dir).fetch())
    validos, _ = validate(normalizados, schemas)
    return {p.slug for p in validos}, categories


def orfaos(conn: sa.Connection, validos: set[str]) -> list[tuple[str, str]]:
    """(id, slug) dos produtos que não estão no seed atual."""
    linhas = conn.execute(sa.text("select id, slug from products order by slug")).all()
    return [(str(r.id), r.slug) for r in linhas if r.slug not in validos]


def remove(conn: sa.Connection, ids: list[str]) -> dict[str, int]:
    """Apaga os produtos e tudo que pende deles, na ordem das FKs."""
    if not ids:
        return {}

    p = {"ids": tuple(ids)}
    contagens = {}
    contagens["price_history"] = conn.execute(
        sa.text(
            "delete from price_history where offer_id in "
            "(select id from offers where product_id::text in :ids)"
        ),
        p,
    ).rowcount
    contagens["offers"] = conn.execute(
        sa.text("delete from offers where product_id::text in :ids"), p
    ).rowcount
    contagens["reviews"] = conn.execute(
        sa.text("delete from reviews where product_id::text in :ids"), p
    ).rowcount
    contagens["product_specs"] = conn.execute(
        sa.text("delete from product_specs where product_id::text in :ids"), p
    ).rowcount
    contagens["products"] = conn.execute(
        sa.text("delete from products where id::text in :ids"), p
    ).rowcount

    # Lojas e marcas órfãs: sem produto/oferta apontando, viram lixo no catálogo.
    contagens["stores"] = conn.execute(
        sa.text("delete from stores where id not in (select distinct store_id from offers)")
    ).rowcount
    contagens["brands"] = conn.execute(
        sa.text("delete from brands where id not in (select distinct brand_id from products)")
    ).rowcount
    return contagens


def remove_atributos_orfaos(conn: sa.Connection, categorias) -> int:
    """Apaga linhas de `category_attribute_schema` que o seed não declara mais.

    A carga faz upsert por (categoria, chave): tirar um atributo do
    `categories.json` **não** o remove do banco. Foi o caso do `battery_wh`, que
    a API só expõe em Ah/mAh e por isso saiu do schema (ADR-0009).
    """
    declarados = {(c.slug, a.attribute_key) for c in categorias for a in c.attributes}
    linhas = conn.execute(
        sa.text(
            "select cas.id, c.slug, cas.attribute_key from category_attribute_schema cas "
            "join categories c on c.id = cas.category_id"
        )
    ).all()
    sobrando = [str(r.id) for r in linhas if (r.slug, r.attribute_key) not in declarados]
    if not sobrando:
        return 0
    return conn.execute(
        sa.text("delete from category_attribute_schema where id::text in :ids"),
        {"ids": tuple(sobrando)},
    ).rowcount


def main() -> None:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="lista, não apaga")
    parser.add_argument("--yes", action="store_true", help="pula a confirmação")
    args = parser.parse_args()

    import os

    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Defina DATABASE_URL.")

    validos, categorias = slugs_do_seed()
    engine = sa.create_engine(url, future=True)

    with engine.connect() as conn:
        pendentes = orfaos(conn, validos)

    print(f"seed produz {len(validos)} produtos; {len(pendentes)} órfãos no banco")
    for _, slug in pendentes[:20]:
        print(f"   - {slug}")
    if len(pendentes) > 20:
        print(f"   ... e mais {len(pendentes) - 20}")

    if args.dry_run:
        print("\n(dry-run — nada apagado)")
        return

    if pendentes and not args.yes:
        resposta = input(f"\nApagar {len(pendentes)} produtos e o que depende deles? [s/N] ")
        if resposta.strip().lower() not in {"s", "sim", "y", "yes"}:
            print("Cancelado.")
            return

    with engine.begin() as conn:
        if pendentes:
            print("\nremovido:", remove(conn, [pid for pid, _ in pendentes]))
        atributos = remove_atributos_orfaos(conn, categorias)
        if atributos:
            print(f"atributos de schema removidos: {atributos}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
