"""Endpoints de busca/comparação: GET /search, POST /compare."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


class CompareRequest(BaseModel):
    product_ids: list[str]


@router.post("/compare")
def compare(req: CompareRequest) -> dict:
    """Comparação de 2-4 produtos da mesma categoria (RF-20/21). TODO Fase 3."""
    raise HTTPException(status_code=501, detail="Not implemented")
