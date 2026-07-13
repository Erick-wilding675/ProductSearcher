"""Endpoints do catálogo: GET /categories, GET /products/{id}."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.catalog.repository import CatalogRepository, get_catalog_repository
from app.catalog.schemas import CategoryOut

router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    repo: Annotated[CatalogRepository, Depends(get_catalog_repository)],
) -> list[CategoryOut]:
    """Categorias cobertas (com produtos).

    A extensão consulta este endpoint para saber em quais categorias ela deve se
    ativar na SERP do Google (ativação por cobertura — ADR-0001).
    """
    return repo.get_categories()


@router.get("/products/{product_id}")
def get_product(product_id: str) -> dict:
    """Detalhe do produto: specs + ofertas (RF-42). TODO Fase 3."""
    raise HTTPException(status_code=501, detail="Not implemented")
