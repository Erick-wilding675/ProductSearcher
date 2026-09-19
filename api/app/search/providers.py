"""Interfaces de busca — permitem trocar o datastore sem reescrever o core (ADR-0002).

Camada de **retrieval** do pipeline de busca (ADR-0007):

    query --> IntentParser --> Intent --> SearchProvider.search() --> hits
                                                                   |
                                          RankingService.rank(hits, intent)

O `SearchProvider` recupera *candidatos* (filtros duros + score de relevância textual);
a ordenação final e explicável fica no `RankingService`. Isso mantém retrieval e
ranking desacoplados e testáveis em separado.

MVP: `FtsSearchProvider` (Postgres FTS). Evolução: pgvector/OpenSearch/Qdrant atrás
da mesma interface, sem tocar no core.
"""

import logging
from decimal import Decimal
from typing import Annotated, Protocol

from fastapi import Depends
from sqlalchemy import Numeric, and_, cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.catalog.tables import (
    FTS_CONFIG,
    brands,
    categories,
    offers,
    product_specs,
    products,
)
from app.core.config import settings
from app.core.db import get_session
from app.search.intent import Intent

logger = logging.getLogger(__name__)


class SearchProvider(Protocol):
    def search(
        self,
        intent: Intent,
        filters: dict,
        page: int = 1,
    ) -> list[dict]: ...


class VectorProvider(Protocol):
    """Retrieval semântico por vizinhança de vetores (ADR-010 D3).

    `embed_query` e não `embed`: o modelo escolhido em D3.3 é **assimétrico** —
    consulta e produto entram no espaço por caminhos diferentes. Um `embed`
    genérico convidaria a vetorizar produto pelo caminho da consulta, o que não
    dá erro, só piora o resultado. Ver `app/search/embedding.py`.

    `search` recebe **vetor**, não texto, para que dê para exercitar a busca com
    um vetor fixo, sem carregar o modelo.
    """

    def embed_query(self, text: str) -> list[float]: ...

    def search(
        self,
        vector: list[float],
        k: int = 10,
    ) -> list[str]: ...


def _condicoes_duras(
    intent: Intent,
    filters: dict | None,
) -> tuple[list, float | None]:
    """Filtros duros que valem para os **dois** braços da busca híbrida.

    Extraído para função por uma razão de correção, não de estilo: o braço
    vetorial tem de aplicar exatamente os mesmos filtros do textual. Se ele
    ignorasse `price_max`, a união devolveria produto acima do teto que o
    usuário pediu — o filtro deixaria de filtrar sem erro nenhum, só com
    resultado errado. Mesma família das falhas silenciosas que o ADR-010
    persegue.

    Devolve as condições e o `price_max`, que é `HAVING` (depende do agregado
    `min(offers.price)`) e por isso não cabe na mesma lista.
    """
    filters = filters or {}

    # Intent tem prioridade sobre filters explícitos; filters cobre o que o parser
    # não extrai (ex.: marca escolhida na UI).
    category = intent.category or filters.get("category")
    brand = filters.get("brand")
    price_max = (
        intent.price_max
        if intent.price_max is not None
        else filters.get("price_max")
    )
    attributes = intent.attributes or filters.get("attributes")

    conditions = []

    if category:
        conditions.append(categories.c.slug == category)

    if brand:
        conditions.append(brands.c.slug == brand)

    # Filtro estruturado por atributos (RF-12): containment JSONB (@>),
    # servido pelo índice GIN jsonb_path_ops.
    if attributes:
        conditions.append(
            product_specs.c.attributes.op("@>")(
                cast(attributes, JSONB)
            )
        )

    # Faixa numérica ("pelo menos 30 horas de bateria"). Não cabe no `@>`,
    # que é igualdade: um fone de 40h não *contém* 30h. Por isso é comparação,
    # e por isso vem num campo próprio do Intent.
    #
    # A comparação é jsonb contra jsonb, não `::numeric`. Não é preciosismo:
    # o cast é avaliado sobre todas as linhas que o planner escolher, e um
    # único spec gravado como texto ("30h") derruba a consulta inteira com
    # erro de conversão. Comparar jsonb nunca falha — daí o `jsonb_typeof`
    # ao lado, que é o que restringe a comparação a valores numéricos.
    #
    # Nenhum índice serve esta condição: o GIN jsonb_path_ops só atende
    # containment. Com 235 produtos isso não custa nada; se o catálogo
    # crescer, o caminho é um índice btree por expressão sobre a chave.
    for chave, faixa in (intent.attribute_ranges or {}).items():
        valor = product_specs.c.attributes[chave]
        conditions.append(func.jsonb_typeof(valor) == "number")

        if (minimo := faixa.get("min")) is not None:
            conditions.append(
                valor.op(">=")(_como_jsonb(minimo))
            )

        if (maximo := faixa.get("max")) is not None:
            conditions.append(
                valor.op("<=")(_como_jsonb(maximo))
            )

    return conditions, price_max


def _consulta_base(rank_expr):
    """`select` + joins + `group_by` comuns aos dois braços.

    Os dois têm de devolver o **mesmo formato de hit** (ADR-0007 D2), senão a
    fusão comparia linhas de formatos diferentes.

    Somente ofertas com ``quality_status='valid'`` participam do cálculo de
    preço. O filtro fica dentro do LEFT JOIN para que produtos sem oferta válida
    continuem podendo existir como candidatos, com ``min_price=None``.
    """
    min_price = func.min(offers.c.price)

    return (
        select(
            products.c.id,
            products.c.slug,
            products.c.name,
            categories.c.slug.label("category"),
            brands.c.name.label("brand"),
            brands.c.slug.label("brand_slug"),
            min_price.label("min_price"),
            rank_expr.label("fts_rank"),
            product_specs.c.attributes.label("attributes"),
        )
        .select_from(products)
        .join(
            categories,
            categories.c.id == products.c.category_id,
        )
        .join(
            brands,
            brands.c.id == products.c.brand_id,
        )
        .outerjoin(
            offers,
            and_(
                offers.c.product_id == products.c.id,
                offers.c.quality_status == "valid",
            ),
        )
        # LEFT JOIN: produto sem specs continua sendo candidato.
        # É 1:1 com produto (uq_product_specs_product), então não
        # infla as linhas do agrupamento.
        .outerjoin(
            product_specs,
            product_specs.c.product_id == products.c.id,
        )
        .group_by(
            products.c.id,
            products.c.slug,
            products.c.name,
            categories.c.slug,
            brands.c.name,
            brands.c.slug,
            product_specs.c.attributes,
        )
    )


class FtsSearchProvider:
    """Retrieval textual via Postgres Full-Text Search (default do MVP, RF-10).

    Aplica os filtros duros (categoria, marca, preço-teto) e devolve candidatos com o
    score bruto de relevância (`fts_rank` = `ts_rank`), que o `RankingService` usa como
    um dos critérios. Não ordena para o usuário final nem pagina — isso é do ranking.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        intent: Intent,
        filters: dict | None = None,
        page: int = 1,
    ) -> list[dict]:
        conditions, price_max = _condicoes_duras(intent, filters)

        # `intent.text` (e não `raw`): o texto já sem as partes que viraram filtro.
        # `plainto_tsquery` combina os termos com AND — "até R$5000" no texto exigiria
        # "ate"/"r"/"5000" no produto e zeraria o resultado.
        # `FTS_CONFIG` e não "portuguese": tem de ser a **mesma** configuração da
        # coluna gerada. Consulta e documento processados por configurações
        # diferentes casam menos e não dão erro — falha silenciosa.
        texto = intent.text or intent.raw
        tsquery = (
            func.plainto_tsquery(FTS_CONFIG, texto)
            if texto
            else None
        )

        min_price = func.min(offers.c.price)

        if tsquery is not None:
            conditions.append(
                products.c.search_vector.op("@@")(tsquery)
            )

        rank_expr = (
            func.ts_rank(
                products.c.search_vector,
                tsquery,
            )
            if tsquery is not None
            else literal(0.0)
        )

        stmt = _consulta_base(rank_expr)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        if price_max is not None:
            stmt = stmt.having(min_price <= price_max)

        stmt = stmt.order_by(
            func.coalesce(
                rank_expr,
                0.0,
            ).desc()
        ).limit(settings.search_candidate_pool)

        rows = self._session.execute(stmt).all()

        return [_row_to_hit(row) for row in rows]


def _como_jsonb(valor: float):
    """`30.0` -> `to_jsonb(30.0::numeric)`, o lado direito da comparação.

    O cast explícito para `numeric` é obrigatório: `to_jsonb` é polimórfica e um
    parâmetro sem tipo chega ao Postgres como `unknown`, que ela rejeita.
    """
    return func.to_jsonb(
        cast(
            literal(float(valor)),
            Numeric,
        )
    )


def _row_to_hit(row) -> dict:
    """Converte a linha do retrieval no `hit` que o RankingService consome."""

    min_price = row.min_price

    if isinstance(min_price, Decimal):
        min_price = float(min_price)

    return {
        "id": str(row.id),
        "slug": row.slug,
        "name": row.name,
        "category": row.category,
        "brand": row.brand,
        "brand_slug": row.brand_slug,
        "min_price": min_price,
        "fts_rank": float(row.fts_rank or 0.0),
        # O ranking usa isto para o fator de atributos; sem a chave,
        # o fator ficava sempre com score 0 e só diluía o score final.
        "attributes": row.attributes or {},
    }


def get_fts_search_provider(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
) -> SearchProvider:
    """Dependency do FastAPI: injeta o provider FTS (uma sessão por request)."""

    return FtsSearchProvider(session)


class PgVectorProvider:
    """Retrieval semântico via pgvector, servido pelo índice HNSW (ADR-010 D3).

    Devolve **ids**, não hits completos: o vetorial responde "quais produtos se
    parecem com esta necessidade", e quem monta a linha do resultado continua
    sendo o caminho que já sabe fazer isso. Manter os dois papéis separados é o
    que permite a união do D4 sem duplicar a montagem do hit.
    """

    def __init__(
        self,
        session: Session,
        embedder: object | None = None,
    ) -> None:
        self._session = session
        # Injetável para teste; em produção resolve para a instância única.
        self._embedder = embedder

    def embed_query(self, text: str) -> list[float]:
        if self._embedder is None:
            from app.search.embedding import get_embedder

            self._embedder = get_embedder()

        return self._embedder.embed_query(text)

    def search(
        self,
        vector: list[float],
        k: int = 10,
    ) -> list[str]:
        # `<=>` é distância de cosseno, e é o operador que o índice HNSW foi
        # criado para servir (`vector_cosine_ops`, migration 71ab0046068d).
        # Usar outro operador aqui não daria erro — só deixaria de usar o
        # índice e passaria a varrer a tabela.
        distancia = products.c.embedding.cosine_distance(vector)

        # `IS NOT NULL` explícito: produto ainda não vetorizado não é "muito
        # distante", é *desconhecido*. Sem este filtro o Postgres ordena nulos
        # e eles entram no topo ou no fim conforme a versão — melhor excluir.
        stmt = (
            select(products.c.id)
            .where(products.c.embedding.isnot(None))
            .order_by(distancia)
            .limit(k)
        )

        return [
            str(linha.id)
            for linha in self._session.execute(stmt).all()
        ]


def get_vector_provider(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
) -> VectorProvider:
    """Dependency do FastAPI: injeta o provider vetorial (uma sessão por request).

    Não checa `vector_enabled` — quem decide se o caminho vetorial entra na
    busca é o serviço, não a construção do provider.
    """

    return PgVectorProvider(session)


class HybridSearchProvider:
    """União textual + vetorial fundida por Reciprocal Rank Fusion (ADR-010 D4).

    Implementa a **mesma** `SearchProvider` Protocol do `FtsSearchProvider`, então
    `service.py` não muda uma linha — a troca é na dependency.

    União e não *switch*: vetorial puro perde o match exato que o FTS acerta.
    "IdeaPad Slim 3 15IRH10" casa literal no FTS e vira ruído no espaço vetorial.

    ## Por que RRF, e não soma de scores

    `ts_rank` e distância de cosseno não são comparáveis: vivem em escalas
    diferentes, e a do e5 é comprimida (medido em D3.3: margens de 0,04 onde o
    mpnet dava 0,24). Somar exigiria normalizar duas distribuições instáveis.
    RRF usa só a **posição**, que é o que os dois braços produzem de comparável.

    ## Desligado por padrão, e a medição diz por quê

    Medido em 22/08/2026 sobre a suíte de D1, com o catálogo de 235 produtos:

    | rota | precisão@5 | cobertura@5 |
    | --- | --- | --- |
    | só FTS (hoje) | **68%** | 100% |
    | RRF puro (este provider) | 64% | 100% |

    O braço vetorial sozinho dá 34% de precisão e não ganha do FTS em nenhum
    caso da suíte — ele acerta a **categoria** (5/5 sempre) e erra a **spec**,
    porque GPU, RAM e peso não estão no texto vetorizado. Incluir as specs no
    texto piora (42% → 36%), então não é questão de ajustar o texto.

    A causa provável é que D2 já resolveu a fome de resultado que D4 foi escrito
    para atacar: nenhuma consulta da suíte volta vazia, e o menor pool é 6.

    Fica **construído e desligado** (`hybrid_enabled=false`) por decisão do Erick
    em 22/08/2026: a suíte tem 10 casos curados, `searches` está vazia porque não
    há deploy, e as consultas onde o vetorial plausivelmente ajudaria — erro de
    digitação, sinônimo, formulação imprevista — são exatamente as que ainda não
    temos. Ligar antes de ter esse dado trocaria 4 pontos de precisão medidos por
    um ganho hipotético.
    """

    def __init__(
        self,
        session: Session,
        vector: VectorProvider | None = None,
        k_rrf: int = 60,
    ) -> None:
        self._session = session
        self._fts = FtsSearchProvider(session)
        self._vector = vector

        # Constante clássica do RRF. Amortece o topo: sem ela, o 1º lugar de um
        # braço dominaria qualquer consenso entre os dois.
        self._k = k_rrf

    def search(
        self,
        intent: Intent,
        filters: dict | None = None,
        page: int = 1,
    ) -> list[dict]:
        textuais = self._fts.search(
            intent,
            filters,
            page,
        )

        texto = intent.text or intent.raw

        if not texto:
            # Sem texto não há consulta a vetorizar — navegação por filtro puro
            # é caso do FTS, e chamar o modelo aqui só gastaria latência.
            return textuais

        try:
            vetoriais = self._candidatos_vetoriais(
                intent,
                filters,
                texto,
            )
        except Exception:  # pragma: no cover - degradação proposital
            # O braço vetorial é complementar: se o modelo não carregou ou o
            # índice falhou, a busca continua servindo o textual. Cair a busca
            # inteira por causa do braço opcional seria pior que não tê-lo.
            logger.exception(
                "Braço vetorial falhou; servindo só o textual"
            )
            return textuais

        return self._funde(
            textuais,
            vetoriais,
        )

    def _candidatos_vetoriais(
        self,
        intent: Intent,
        filters: dict | None,
        texto: str,
    ) -> list[dict]:
        """Vizinhos mais próximos, sob os **mesmos filtros duros** do braço textual.

        Reaproveitar `_condicoes_duras` é o que impede a união de devolver
        produto que contradiz um filtro explícito do usuário.
        """
        vetor = (
            self._vector
            or PgVectorProvider(self._session)
        ).embed_query(texto)

        conditions, price_max = _condicoes_duras(
            intent,
            filters,
        )

        distancia = products.c.embedding.cosine_distance(vetor)

        # `fts_rank` zero: quem entra só pelo vetor não tem score textual. O
        # ranking já trata 0 como "sem sinal textual".
        stmt = _consulta_base(
            literal(0.0)
        ).where(
            products.c.embedding.isnot(None)
        )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        if price_max is not None:
            stmt = stmt.having(
                func.min(offers.c.price) <= price_max
            )

        stmt = (
            stmt.order_by(distancia)
            .limit(settings.vector_top_k)
        )

        return [
            _row_to_hit(linha)
            for linha in self._session.execute(stmt).all()
        ]

    def _funde(
        self,
        textuais: list[dict],
        vetoriais: list[dict],
    ) -> list[dict]:
        """Reciprocal Rank Fusion: `score = Σ 1 / (k + posição)`.

        Anota `vector_rank` no hit para o ranking poder consumir a posição
        vetorial como sinal (ADR-010 D4), sem ter de refazer a busca.
        """
        score: dict[str, float] = {}
        hits: dict[str, dict] = {}

        for posicao, hit in enumerate(textuais):
            pid = hit["id"]

            score[pid] = (
                score.get(pid, 0.0)
                + 1.0 / (self._k + posicao + 1)
            )

            hits[pid] = hit

        for posicao, hit in enumerate(vetoriais):
            pid = hit["id"]

            score[pid] = (
                score.get(pid, 0.0)
                + 1.0 / (self._k + posicao + 1)
            )

            # O hit textual vence como base: ele traz o `fts_rank` de verdade.
            hits.setdefault(pid, hit)
            hits[pid]["vector_rank"] = posicao + 1

        ordenados = sorted(
            hits.values(),
            key=lambda hit: score[hit["id"]],
            reverse=True,
        )

        return ordenados[
            : settings.search_candidate_pool
        ]


def get_search_provider(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
) -> SearchProvider:
    """Escolhe o braço de retrieval conforme a flag (ADR-010 D4).

    `hybrid_enabled=false` (o default) devolve exatamente o `FtsSearchProvider`
    de hoje — não é um híbrido com o braço vetorial vazio, é o mesmo objeto, sem
    caminho novo no meio.
    """

    if settings.hybrid_enabled:
        return HybridSearchProvider(session)

    return FtsSearchProvider(session)