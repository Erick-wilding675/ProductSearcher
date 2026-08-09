"""Carga idempotente no Postgres (RF-72, ADR-0005 D3).

Estratégia: upsert por chave natural (``slug`` em products/brands/categories/stores;
``product_id`` em specs; ``(product_id, store_id)`` em offers) via
``INSERT ... ON CONFLICT DO UPDATE``. Os UUIDs são gerados na aplicação, então uma
inserção sempre traz um ``id`` novo, mas em conflito o registro existente é
preservado. `price_history` só ganha um ponto quando o preço realmente muda —
rodar o seed N vezes converge ao mesmo estado.

**Em lote, não linha a linha.** A primeira versão fazia um round trip por linha
(e mais um SELECT por oferta). Com 167 ofertas passava; quando o enriquecimento
levou o catálogo a ~1400 ofertas em ~800 lojas, virou milhares de idas ao banco e
a carga estourava o tempo contra o Supabase. Agora cada tabela é uma instrução só,
com `RETURNING` devolvendo os ids que a etapa seguinte precisa — a carga inteira
cabe em pouco mais de meia dúzia de round trips.
"""

import logging
from collections.abc import Iterable, Sequence
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from ingestion import schema
from ingestion.models import Category, NormalizedProduct

logger = logging.getLogger(__name__)


def _upsert(
    conn: Connection,
    table: sa.Table,
    values: dict,
    conflict_cols: Sequence[str],
    update_cols: Sequence[str],
    keep_if_null: Sequence[str] = (),
) -> UUID:
    """Upsert de uma linha; devolve o ``id`` (novo ou já existente).

    ``keep_if_null``: colunas em que um valor **nulo** na entrada não apaga o que
    já está gravado (``coalesce(excluded.col, tabela.col)``). Serve para dado que
    só algumas fontes trazem — a URL da loja, por exemplo: a segunda oferta da
    mesma loja não pode zerar a URL que a primeira trouxe.
    """
    stmt = pg_insert(table).values(id=uuid4(), **values)
    atualizacoes = {
        col: (
            sa.func.coalesce(stmt.excluded[col], table.c[col])
            if col in keep_if_null
            else stmt.excluded[col]
        )
        for col in update_cols
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=list(conflict_cols), set_=atualizacoes
    ).returning(table.c.id)
    return conn.execute(stmt).scalar_one()


def _load_categories(conn: Connection, categories: Iterable[Category]) -> dict[str, UUID]:
    """Upsert das categorias e do seu `category_attribute_schema`."""
    ids: dict[str, UUID] = {}
    for category in categories:
        category_id = _upsert(
            conn,
            schema.categories,
            {"slug": category.slug, "name": category.name},
            ["slug"],
            ["name"],
        )
        ids[category.slug] = category_id
        for attr in category.attributes:
            _upsert(
                conn,
                schema.category_attribute_schema,
                {
                    "category_id": category_id,
                    "attribute_key": attr.attribute_key,
                    "label": attr.label,
                    "data_type": attr.data_type,
                    "allowed_values": attr.allowed_values,
                    "unit": attr.unit,
                    "required": attr.required,
                },
                ["category_id", "attribute_key"],
                ["label", "data_type", "allowed_values", "unit", "required"],
            )
    return ids


def _upsert_lote(
    conn: Connection,
    table: sa.Table,
    linhas: list[dict],
    conflict_cols: Sequence[str],
    update_cols: Sequence[str],
    returning_cols: Sequence[str],
    keep_if_null: Sequence[str] = (),
) -> list:
    """Upsert de várias linhas numa instrução só; devolve as colunas pedidas.

    As linhas precisam vir **sem repetir a chave de conflito**: o Postgres recusa
    um `ON CONFLICT DO UPDATE` que afetaria a mesma linha duas vezes no mesmo
    comando. Quem chama deduplica antes.
    """
    if not linhas:
        return []

    stmt = pg_insert(table).values([{"id": uuid4(), **linha} for linha in linhas])
    atualizacoes = {
        col: (
            sa.func.coalesce(stmt.excluded[col], table.c[col])
            if col in keep_if_null
            else stmt.excluded[col]
        )
        for col in update_cols
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=list(conflict_cols), set_=atualizacoes
    ).returning(*[table.c[col] for col in returning_cols])
    return conn.execute(stmt).all()


def _load_offers(
    conn: Connection,
    product_ids: dict[str, UUID],
    products: list[NormalizedProduct],
) -> tuple[int, int]:
    """Carrega lojas, ofertas e histórico de preço do lote inteiro.

    Quatro instruções no total: lojas, leitura dos preços atuais, ofertas e
    histórico. O histórico só recebe ponto onde o preço mudou de verdade — é o que
    mantém a reexecução idempotente.
    """
    # 1) Lojas — deduplicadas por slug, preferindo a ocorrência que traz URL.
    lojas: dict[str, dict] = {}
    for product in products:
        for offer in product.offers:
            atual = lojas.get(offer.store_slug)
            if atual is None or (offer.store_url and not atual["url"]):
                lojas[offer.store_slug] = {
                    "slug": offer.store_slug,
                    "name": offer.store_name,
                    "url": offer.store_url,
                }

    store_ids = {
        row.slug: row.id
        for row in _upsert_lote(
            conn,
            schema.stores,
            list(lojas.values()),
            ["slug"],
            ["name", "url"],
            ["id", "slug"],
            keep_if_null=["url"],
        )
    }

    # 2) Ofertas — dedup por (produto, loja), que é a chave de conflito.
    ofertas: dict[tuple[UUID, UUID], dict] = {}
    for product in products:
        product_id = product_ids[product.slug]
        for offer in product.offers:
            chave = (product_id, store_ids[offer.store_slug])
            ofertas.setdefault(
                chave,
                {
                    "product_id": chave[0],
                    "store_id": chave[1],
                    "price": offer.price,
                    "currency": offer.currency,
                    "url": offer.url,
                },
            )

    # 3) Preços atuais, de uma vez, para saber o que mudou.
    anteriores = {
        (row.product_id, row.store_id): row.price
        for row in conn.execute(
            sa.select(
                schema.offers.c.product_id, schema.offers.c.store_id, schema.offers.c.price
            ).where(schema.offers.c.product_id.in_(list(product_ids.values())))
        ).all()
    }

    gravadas = _upsert_lote(
        conn,
        schema.offers,
        list(ofertas.values()),
        ["product_id", "store_id"],
        ["price", "currency", "url"],
        ["id", "product_id", "store_id"],
    )

    # 4) Histórico só onde o preço mudou (ou é oferta nova).
    pontos = []
    for row in gravadas:
        chave = (row.product_id, row.store_id)
        anterior = anteriores.get(chave)
        preco = ofertas[chave]["price"]
        if anterior is None or Decimal(anterior) != preco:
            pontos.append({"id": uuid4(), "offer_id": row.id, "price": preco})

    if pontos:
        conn.execute(pg_insert(schema.price_history).values(pontos))

    return len(gravadas), len(pontos)


def load(
    conn: Connection,
    products: Iterable[NormalizedProduct],
    categories: Iterable[Category],
) -> dict[str, int]:
    """Persiste categorias e produtos (com specs e ofertas) de forma idempotente."""
    category_ids = _load_categories(conn, categories)
    products = list(products)

    # Marcas: uma instrução para o lote todo.
    marcas = {p.brand_slug: {"slug": p.brand_slug, "name": p.brand_name} for p in products}
    brand_ids = {
        row.slug: row.id
        for row in _upsert_lote(
            conn, schema.brands, list(marcas.values()), ["slug"], ["name"], ["id", "slug"]
        )
    }

    # `validate()` já garante categoria conhecida; a checagem aqui é defensiva.
    conhecidos = [p for p in products if p.category_slug in category_ids]
    for p in products:
        if p.category_slug not in category_ids:
            logger.warning("Categoria sem id para %s: %s", p.name, p.category_slug)

    product_ids = {
        row.slug: row.id
        for row in _upsert_lote(
            conn,
            schema.products,
            [
                {
                    "category_id": category_ids[p.category_slug],
                    "brand_id": brand_ids[p.brand_slug],
                    "slug": p.slug,
                    "name": p.name,
                    "model": p.model,
                    "description": p.description,
                }
                for p in conhecidos
            ],
            ["slug"],
            ["category_id", "brand_id", "name", "model", "description"],
            ["id", "slug"],
            # Uma carga a partir de um seed ainda não enriquecido não pode zerar
            # o `model`/`description` que o enriquecimento já trouxe.
            keep_if_null=["model", "description"],
        )
    }

    _upsert_lote(
        conn,
        schema.product_specs,
        [
            {"product_id": product_ids[p.slug], "attributes": p.specs}
            for p in conhecidos
            if p.slug in product_ids
        ],
        ["product_id"],
        ["attributes"],
        ["id"],
    )

    offers_count, price_points = _load_offers(conn, product_ids, conhecidos)

    return {
        "categories": len(category_ids),
        "products": len(product_ids),
        "offers": offers_count,
        "price_points": price_points,
    }
