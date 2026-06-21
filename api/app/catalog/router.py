"""Endpoints do catálogo: GET /categories, GET /products/{id}."""
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["catalog"])


@router.get("/categories")
def list_categories() -> list[dict]:
    """Categorias cobertas (usado pela extensão para ativação por cobertura). TODO Fase 3."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/products/{product_id}")
def get_product(product_id: str) -> dict:
    """Detalhe do produto: specs + ofertas (RF-42). TODO Fase 3."""
    raise HTTPException(status_code=501, detail="Not implemented")
