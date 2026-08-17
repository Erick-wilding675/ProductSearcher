"""Endpoints de busca/comparação: GET /search, GET /spec-options, POST /compare."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.catalog.repository import CatalogRepository, get_catalog_repository
from app.search.comparison import CompareOut, CompareRequest, build_comparison
from app.search.schemas import (
    RankByOption,
    SearchResponse,
    SortOption,
    SpecOptionsResponse,
)
from app.search.service import SearchService, get_search_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    service: Annotated[SearchService, Depends(get_search_service)],
    q: str | None = None,
    category: str | None = None,
    price_max: float | None = Query(None, ge=0),
    brand: str | None = None,
    rank_by: RankByOption = RankByOption.relevance,
    rank_brand: str | None = None,
    rank_spec: str | None = None,
    rank_spec_value: str | None = None,
    # Sem default no servidor: assim dá para distinguir "o usuário escolheu
    # Relevância" de "não veio ordenação", e `rank_by=price` pode aplicar a ordem
    # crescente que o requisito pede. Ver `_sort_efetivo`.
    sort: SortOption | None = None,
    page: int = Query(1, ge=1),
    attrs: str | None = Query(
        None,
        description='Filtro por atributos, objeto JSON. Ex.: {"ram_gb": 16, "anc": true}',
    ),
) -> SearchResponse:
    """Busca de produtos (RF-10/11/12/30/31).

    Pipeline do ADR-0007: o texto passa pelo `IntentParser`, o retrieval aplica os
    filtros duros e o `RankingService` produz a ordem final — junto dos **critérios**
    que a justificam, para a UI poder explicar o porquê de cada posição.

    `rank_by` define uma preferência de ranking, sem transformar essa preferência
    em filtro duro.
    """
    if rank_by == RankByOption.brand and not rank_brand:
        raise HTTPException(
            status_code=422,
            detail="rank_brand é obrigatório quando rank_by=brand",
        )

    if rank_by == RankByOption.spec:
        if not rank_spec:
            raise HTTPException(
                status_code=422,
                detail="rank_spec é obrigatório quando rank_by=spec",
            )

        if rank_spec_value is None:
            raise HTTPException(
                status_code=422,
                detail="rank_spec_value é obrigatório quando rank_by=spec",
            )

    return service.search(
        q=q,
        category=category,
        price_max=price_max,
        brand=brand,
        attributes=_parse_attrs(attrs),
        sort=sort.value if sort else None,
        page=page,
        rank_by=rank_by.value,
        rank_brand=rank_brand,
        rank_spec=rank_spec,
        rank_spec_value=_parse_rank_spec_value(rank_spec_value),
    )


def _parse_attrs(attrs: str | None) -> dict | None:
    """Interpreta o filtro de atributos (JSON) do /search (RF-12). Erros viram 422."""
    if not attrs:
        return None

    try:
        parsed = json.loads(attrs)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail="attrs deve ser JSON válido",
        ) from exc

    if not isinstance(parsed, dict) or not parsed:
        raise HTTPException(
            status_code=422,
            detail="attrs deve ser um objeto JSON não vazio",
        )

    return parsed


def _parse_rank_spec_value(value: str | None):
    """Converte booleanos da query para o tipo usado no ranking.

    Números e textos permanecem como string porque `_attr_matches` já faz a
    comparação tolerante entre string/número.
    """
    if value is None:
        return None

    normalized = value.strip().lower()

    if normalized == "true":
        return True

    if normalized == "false":
        return False

    return value


@router.get("/spec-options", response_model=SpecOptionsResponse)
def spec_options(
    service: Annotated[SearchService, Depends(get_search_service)],
    q: str | None = None,
    category: str | None = None,
    price_max: float | None = Query(None, ge=0),
    brand: str | None = None,
    attrs: str | None = Query(
        None,
        description='Filtro por atributos, objeto JSON. Ex.: {"ram_gb": 16}',
    ),
) -> SpecOptionsResponse:
    """Specs e valores disponíveis no pool atual de candidatos."""

    return service.spec_options(
        q=q,
        category=category,
        price_max=price_max,
        brand=brand,
        attributes=_parse_attrs(attrs),
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
        raise HTTPException(
            status_code=404,
            detail=f"Produtos não encontrados: {faltando}",
        )

    produtos = [encontrados[pid] for pid in req.product_ids]

    if len({p.category for p in produtos}) > 1:
        raise HTTPException(
            status_code=400,
            detail="Só é possível comparar produtos da mesma categoria",
        )

    return build_comparison(produtos)
