"""Endpoints de busca/comparação: GET /search, POST /compare."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.catalog.repository import CatalogRepository, get_catalog_repository
from app.search.comparison import CompareOut, CompareRequest, build_comparison
from app.search.repository import SearchRepository, get_search_repository
from app.search.schemas import SearchResponse, SortOption

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    repo: Annotated[SearchRepository, Depends(get_search_repository)],
    q: str | None = None,
    category: str | None = None,
    price_max: float | None = Query(None, ge=0),
    brand: str | None = None,
    sort: SortOption = SortOption.relevance,
    page: int = Query(1, ge=1),
) -> SearchResponse:
    """Busca de produtos (RF-10/11/12): texto (FTS PT-BR) + filtros + ordenação + paginação."""
    return repo.search(
        q=q, category=category, price_max=price_max, brand=brand, sort=sort.value, page=page
    )


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
