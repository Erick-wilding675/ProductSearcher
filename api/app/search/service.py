"""Orquestração da busca: o pipeline do ADR-0007 em um lugar só.

    query -> IntentParser -> Intent -> SearchProvider.search() -> candidatos
                                                                      |
                                             RankingService.rank(candidatos, intent)
                                                                      |
                                                          ordenação + paginação

O router fica só com o contrato HTTP; a composição das peças vive aqui, o que
mantém o pipeline testável sem subir a aplicação.
"""

from collections import Counter, defaultdict
from decimal import Decimal
from typing import Annotated, Any

from fastapi import Depends

from app.catalog.repository import CatalogRepository, get_catalog_repository
from app.search.intent import Intent, IntentParser, RuleBasedIntentParser
from app.search.log import NullSearchLog, SearchLog, get_search_log
from app.search.providers import SearchProvider, get_fts_search_provider
from app.search.ranking import DeterministicRanking, RankingService
from app.search.schemas import (
    RankingCriterion,
    RankingFactor,
    SearchResponse,
    SearchResultItem,
    SpecOption,
    SpecOptionsResponse,
    SpecOptionValue,
)

PAGE_SIZE = 20

# Evita oferecer no seletor specs com dezenas de valores distintos,
# que gerariam dropdowns pouco práticos para o usuário.
MAX_SPEC_OPTION_VALUES = 20


class SearchService:
    """Compõe parser, retrieval e ranking para atender o `GET /search`."""

    def __init__(
        self,
        parser: IntentParser,
        provider: SearchProvider,
        ranking: RankingService,
        log: SearchLog | None = None,
        catalog: CatalogRepository | None = None,
    ) -> None:
        self._parser = parser
        self._provider = provider
        self._ranking = ranking
        self._log = log or NullSearchLog()
        self._catalog = catalog

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
        rank_by: str = "relevance",
        rank_brand: str | None = None,
        rank_spec: str | None = None,
        rank_spec_value=None,
    ) -> SearchResponse:
        page = max(page, 1)
        intent = self._parser.parse(q) if q else Intent(raw="", text="")

        # Filtros vindos da UI complementam o intent; o parser tem precedência
        # no que ele extrai (categoria/preço), o resto só a UI informa (marca).
        filtros = {
            "category": category,
            "brand": brand,
            "price_max": price_max,
            "attributes": {
                **(intent.attributes or {}),
                **(attributes or {}),
            },
        }

        candidatos = self._provider.search(
            intent,
            filters=filtros,
        )

        ranqueado = self._ranking.rank(
            candidatos,
            intent,
            rank_by=rank_by,
            rank_brand=rank_brand,
            rank_spec=rank_spec,
            rank_spec_value=rank_spec_value,
        )

        itens = _ordena(
            ranqueado["items"],
            sort,
        )

        inicio = (page - 1) * PAGE_SIZE

        # Registra a consulta com o total de candidatos, não com o tamanho da
        # página: é o zero que interessa (busca que não achou nada).
        if q:
            self._log.record(
                q,
                intent,
                len(itens),
            )

        return SearchResponse(
            page=page,
            page_size=PAGE_SIZE,
            total=len(itens),
            criteria=[RankingCriterion(**criterion) for criterion in ranqueado["criteria"]],
            results=[_para_item(hit) for hit in itens[inicio : inicio + PAGE_SIZE]],
        )

    def spec_options(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        price_max: float | None = None,
        brand: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> SpecOptionsResponse:
        """Specs e valores presentes no pool atual de candidatos."""

        intent = self._parser.parse(q) if q else Intent(raw="", text="")

        filtros = {
            "category": category,
            "brand": brand,
            "price_max": price_max,
            "attributes": {
                **(intent.attributes or {}),
                **(attributes or {}),
            },
        }

        candidatos = self._provider.search(
            intent,
            filters=filtros,
        )

        category_slug = intent.category or category

        if not category_slug:
            return SpecOptionsResponse()

        # O catálogo é opcional no construtor para preservar compatibilidade
        # com testes e usos antigos do SearchService. Em produção, a dependency
        # get_search_service sempre o fornece.
        if self._catalog is None:
            return SpecOptionsResponse()

        labels = self._catalog.get_attribute_labels(category_slug)

        counts: dict[str, Counter] = defaultdict(Counter)

        for candidato in candidatos:
            attributes_found = candidato.get("attributes") or {}

            for key, value in attributes_found.items():
                if key not in labels or value is None:
                    continue

                # O contrato público suporta apenas valores simples. Isso também
                # evita tentar usar listas/objetos JSON como chave do Counter.
                if isinstance(value, (str, int, float, bool)):
                    counts[key][value] += 1

        specs: list[SpecOption] = []

        for key, values in counts.items():
            if not values:
                continue

            # Specs com cardinalidade muito alta geram seletores pouco úteis
            # para a preferência explícita do usuário.
            if len(values) > MAX_SPEC_OPTION_VALUES:
                continue

            specs.append(
                SpecOption(
                    key=key,
                    label=labels[key],
                    values=[
                        SpecOptionValue(
                            value=value,
                            count=count,
                        )
                        for value, count in values.most_common()
                    ],
                )
            )

        specs.sort(
            key=lambda spec: spec.label,
        )

        return SpecOptionsResponse(
            specs=specs,
        )


def _ordena(
    itens: list[dict],
    sort: str,
) -> list[dict]:
    """Ordenação pedida pelo usuário. `relevance` mantém a ordem do ranking.

    Nos demais, o desempate por nome mantém o resultado reproduzível quando o
    critério principal empata (vários produtos sem preço, por exemplo).
    """
    if sort == "price_asc":
        return sorted(
            itens,
            key=lambda hit: (
                hit["min_price"] is None,
                hit["min_price"],
                hit["name"],
            ),
        )

    if sort == "price_desc":
        return sorted(
            itens,
            key=lambda hit: (
                hit["min_price"] is None,
                -(hit["min_price"] or 0.0),
                hit["name"],
            ),
        )

    if sort == "name":
        return sorted(
            itens,
            key=lambda hit: hit["name"],
        )

    # relevance: já vem ordenado pelo score do RankingService.
    return itens


def _para_item(hit: dict) -> SearchResultItem:
    """Converte o hit ranqueado no item do contrato público."""

    preco = hit.get("min_price")

    return SearchResultItem(
        id=hit["id"],
        slug=hit["slug"],
        name=hit["name"],
        category=hit["category"],
        brand=hit["brand"],
        min_price=(Decimal(str(preco)) if preco is not None else None),
        specs=hit.get("attributes") or {},
        score=hit.get("score", 0.0),
        factors={key: RankingFactor(**value) for key, value in (hit.get("factors") or {}).items()},
    )


def get_search_service(
    provider: Annotated[
        SearchProvider,
        Depends(get_fts_search_provider),
    ],
    catalog: Annotated[
        CatalogRepository,
        Depends(get_catalog_repository),
    ],
    log: Annotated[
        SearchLog,
        Depends(get_search_log),
    ],
) -> SearchService:
    """Dependency do FastAPI: monta o pipeline com as implementações do MVP."""

    return SearchService(
        RuleBasedIntentParser(),
        provider,
        DeterministicRanking(),
        log=log,
        catalog=catalog,
    )
