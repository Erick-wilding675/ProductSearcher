"""Endpoints de busca/comparação: GET /search, POST /compare."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.catalog.repository import CatalogRepository, get_catalog_repository
from app.search.comparison import CompareOut, CompareRequest, build_comparison

router = APIRouter(tags=["search"])


@router.get("/search")
def search(
    q: str,
    category: str | None = None,
    price_max: float | None = None,
    brand: str | None = None,
    sort: str = "relevance",
    page: int = 1,
) -> dict:
    """Busca de produtos (RF-10/11/12). TODO Fase 3."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/compare", response_model=CompareOut)
def compare(
    req: CompareRequest,
    repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> CompareOut:
    """Comparação de 2-4 produtos da MESMA categoria (RF-20/21).

    Devolve os specs alinhados, marcando quais atributos diferem entre os produtos.
    """
    encontrados = {p.id: p for p in repo.get_products_by_ids(req.product_ids)}
    faltando = [pid for pid in req.product_ids if pid not in encontrados]
    if faltando:
        raise HTTPException(status_code=404, detail=f"Produtos não encontrados: {faltando}")

    produtos = [encontrados[pid] for pid in req.product_ids]
    if len({p.category for p in produtos}) > 1:
        raise HTTPException(
            status_code=400, detail="Só é possível comparar produtos da mesma categoria"
        )

    return build_comparison(produtos)
