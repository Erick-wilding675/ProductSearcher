"""Orquestração da busca: o pipeline do ADR-0007 em um lugar só.

    query -> IntentParser -> Intent -> SearchProvider.search() -> candidatos
                                                                      |
                                             RankingService.rank(candidatos, intent)
                                                                      |
                                                          ordenação + paginação

O router fica só com o contrato HTTP; a composição das peças vive aqui, o que
mantém o pipeline testável sem subir a aplicação.
"""

from decimal import Decimal
from typing import Annotated, Any

from fastapi import Depends

from app.search.intent import Intent, IntentParser, RuleBasedIntentParser
from app.search.log import NullSearchLog, SearchLog, get_search_log
from app.search.providers import SearchProvider, get_fts_search_provider
from app.search.ranking import DeterministicRanking, RankingService
from app.search.schemas import (
    RankingCriterion,
    RankingFactor,
    SearchResponse,
    SearchResultItem,
)

PAGE_SIZE = 20


class SearchService:
    """Compõe parser, retrieval e ranking para atender o `GET /search`."""

    def __init__(
        self,
        parser: IntentParser,
        provider: SearchProvider,
        ranking: RankingService,
        log: SearchLog | None = None,
    ) -> None:
        self._parser = parser
        self._provider = provider
        self._ranking = ranking
        # Default sem registro: o serviço continua utilizável sem banco de log.
        self._log = log or NullSearchLog()

    def search(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        price_max: float | None = None,
        brand: str | None = None,
        attributes: dict[str, Any] | None = None,
        sort: str = "relevance",
        page: int = 1,
    ) -> SearchResponse:
        page = max(page, 1)
        intent = self._parser.parse(q) if q else Intent(raw="", text="")

        # Filtros vindos da UI complementam o intent; o parser tem precedência no que
        # ele extrai (categoria/preço), o resto só a UI informa (marca).
        filtros = {
            "category": category,
            "brand": brand,
            "price_max": price_max,
            "attributes": {**(intent.attributes or {}), **(attributes or {})},
        }
        candidatos = self._provider.search(intent, filters=filtros)
        ranqueado = self._ranking.rank(candidatos, intent)

        itens = _ordena(ranqueado["items"], sort)
        inicio = (page - 1) * PAGE_SIZE

        # Registra a consulta com o total de candidatos, não com o tamanho da
        # página: é o zero que interessa (busca que não achou nada).
        if q:
            self._log.record(q, intent, len(itens))

        return SearchResponse(
            page=page,
            page_size=PAGE_SIZE,
            total=len(itens),
            criteria=[RankingCriterion(**c) for c in ranqueado["criteria"]],
            results=[_para_item(h) for h in itens[inicio : inicio + PAGE_SIZE]],
        )


def _ordena(itens: list[dict], sort: str) -> list[dict]:
    """Ordenação pedida pelo usuário. `relevance` mantém a ordem do ranking.

    Nos demais, o desempate por nome mantém o resultado reproduzível quando o
    critério principal empata (vários produtos sem preço, por exemplo).
    """
    if sort == "price_asc":
        return sorted(itens, key=lambda h: (h["min_price"] is None, h["min_price"], h["name"]))
    if sort == "price_desc":
        return sorted(
            itens,
            key=lambda h: (h["min_price"] is None, -(h["min_price"] or 0.0), h["name"]),
        )
    if sort == "name":
        return sorted(itens, key=lambda h: h["name"])
    return itens  # já vem ordenado por score do ranking


def _para_item(hit: dict) -> SearchResultItem:
    """Converte o hit ranqueado no item do contrato público."""
    preco = hit.get("min_price")
    return SearchResultItem(
        id=hit["id"],
        slug=hit["slug"],
        name=hit["name"],
        category=hit["category"],
        brand=hit["brand"],
        min_price=Decimal(str(preco)) if preco is not None else None,
        specs=hit.get("attributes") or {},
        score=hit.get("score", 0.0),
        factors={k: RankingFactor(**v) for k, v in (hit.get("factors") or {}).items()},
    )


def get_search_service(
    provider: Annotated[SearchProvider, Depends(get_fts_search_provider)],
    log: Annotated[SearchLog, Depends(get_search_log)],
) -> SearchService:
    """Dependency do FastAPI: monta o pipeline com as implementações do MVP."""
    return SearchService(RuleBasedIntentParser(), provider, DeterministicRanking(), log)
