"""Carga offline dos vetores dos produtos (ADR-010 D3).

O desenho de D3 é **assimétrico**: os vetores dos produtos são gerados offline,
uma vez, e em runtime o único cálculo é o vetor da consulta. Este módulo é a
metade offline.

**Roda dentro do serviço que hospeda a API, não na máquina do desenvolvedor**
(ADR-010 D3.1). Por isso mora em `app/` e não no `worker/`: é o mesmo processo,
com o mesmo modelo, que atende as consultas — que é o que garante, por
construção, que produto e consulta caiam no mesmo espaço vetorial.

    python -m app.search.vector_load            # só o que falta
    python -m app.search.vector_load --force    # revetoriza tudo

## Por que existe carimbo

`products.embedding` sozinho não diz **qual modelo** gerou aquele vetor. Se o
modelo mudar, os vetores antigos continuam lá, com a dimensão certa, e a
similaridade contra a consulta nova não significa mais nada — sem erro, sem
aviso, só resultado pior. É a falha silenciosa que o ADR-010 D3 chama de
invariante.

O carimbo vai em `product_specs.attributes._embedding`, e não numa coluna nova,
porque **D3 não tem migration** (a coluna e o índice já existem desde a Fase 2)
e o JSONB já é o lugar dos dados derivados — mesmo caminho do `use_case` de D2.
A chave começa com `_`, então a carga do seed já sabe preservá-la (o `||` de
`ef3468f`) e o `_avisa_specs_orfas` já sabe ignorá-la.

Com o carimbo, trocar de modelo deixa de ser silencioso: os produtos carimbados
com outro id aparecem como pendentes e são revetorizados.
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

from sqlalchemy import cast, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.catalog.tables import product_specs, products
from app.core.db import engine
from app.search.embedding import get_embedder, texto_do_produto

logger = logging.getLogger(__name__)

CHAVE_CARIMBO = "_embedding"


def _pendentes(session: Session, model_id: str, force: bool) -> list[tuple]:
    """Produtos que precisam de vetor.

    Sem `--force`, pendente é quem não tem vetor **ou** foi carimbado por outro
    modelo. O segundo caso é o que torna a troca de modelo segura: não basta
    haver vetor, ele tem de ser do modelo em uso.
    """
    stmt = select(
        products.c.id,
        products.c.name,
        products.c.model,
        products.c.description,
        product_specs.c.attributes,
    ).select_from(products.outerjoin(product_specs, product_specs.c.product_id == products.c.id))

    linhas = session.execute(stmt).all()
    if force:
        return list(linhas)

    faltando = []
    for linha in linhas:
        carimbo = (linha.attributes or {}).get(CHAVE_CARIMBO) or {}
        if carimbo.get("model") != model_id:
            faltando.append(linha)
    return faltando


def carrega(force: bool = False, batch_size: int = 16) -> dict:
    """Gera e grava os vetores. Idempotente: rodar de novo não refaz o que está feito."""
    embedder = get_embedder()
    model_id = embedder.model_id

    with Session(engine) as session:
        alvos = _pendentes(session, model_id, force)
        if not alvos:
            logger.info("Nada a fazer: todos os produtos já têm vetor de %s", model_id)
            return {"total": 0, "modelo": model_id}

        logger.info("Vetorizando %d produtos com %s", len(alvos), model_id)
        textos = [texto_do_produto(a.name, a.model, a.description) for a in alvos]
        vetores = embedder.embed_products(textos, batch_size=batch_size)

        agora = datetime.now(UTC).isoformat()
        for alvo, vetor in zip(alvos, vetores, strict=True):
            session.execute(
                update(products).where(products.c.id == alvo.id).values(embedding=vetor)
            )
            # Merge com `||`, não substituição: `attributes` tem dois donos (o
            # seed traz a ficha técnica, o enriquecimento grava as chaves
            # derivadas). Substituir a coluna apagaria o `use_case` de D2 em
            # silêncio — é o defeito corrigido em `ef3468f`, e ele vale aqui
            # igual.
            carimbo = {
                CHAVE_CARIMBO: {
                    "model": model_id,
                    "dim": len(vetor),
                    "at": agora,
                }
            }
            session.execute(
                update(product_specs)
                .where(product_specs.c.product_id == alvo.id)
                .values(attributes=product_specs.c.attributes.op("||")(cast(carimbo, JSONB)))
            )

        session.commit()
        logger.info("Gravados %d vetores", len(alvos))
        return {"total": len(alvos), "modelo": model_id}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="revetoriza todos os produtos, inclusive os já carimbados com este modelo",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    resultado = carrega(force=args.force, batch_size=args.batch_size)
    print(f"{resultado['total']} produtos vetorizados com {resultado['modelo']}")


if __name__ == "__main__":
    main()
