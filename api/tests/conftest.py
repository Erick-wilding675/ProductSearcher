"""Fixtures compartilhadas dos testes da API.

A suíte é majoritariamente **sem banco** (fakes / SQL compilado). A exceção é a
avaliação de relevância (`test_relevance.py`), que mede a qualidade real do
retrieval e por isso exige um Postgres com o seed carregado — `plainto_tsquery`
e `ts_rank` não têm equivalente fiel em fake.

Quando o banco não está disponível (CI sem serviço, dev sem `docker compose up`),
a fixture **pula** o teste em vez de falhar: o KPI só é medido onde há dados.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.catalog.tables import product_specs, products
from app.core.config import settings
from app.search.intent import RuleBasedIntentParser
from app.search.providers import FtsSearchProvider
from app.search.ranking import DeterministicRanking
from app.search.service import SearchService


@pytest.fixture(scope="session")
def db_session() -> Iterator[Session]:
    """Sessão contra o Postgres real. Pula a suíte se o banco não responder."""
    try:
        # Mesmo `connect_args` do `app/core/db.py`: sem isso a suíte quebra com
        # `DuplicatePreparedStatement` contra o pooler do Supabase. Ver db.py.
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
            connect_args={"prepare_threshold": None},
        )
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        session = factory()
        session.execute(select(1))
    except SQLAlchemyError as exc:
        pytest.skip(f"Postgres indisponível em DATABASE_URL: {exc.__class__.__name__}")

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def search_service(db_session: Session) -> SearchService:
    """Pipeline completo sobre o banco real, com o seed carregado.

    É o mesmo pipeline que o `GET /search` monta (ADR-0007), então a relevância
    medida aqui é a que o usuário recebe — não a de um caminho paralelo.

    Sem catálogo não há o que medir — pula em vez de reportar relevância 0.
    """
    total = db_session.execute(select(func.count()).select_from(products)).scalar_one()
    if not total:
        pytest.skip("Catálogo vazio: rode a ingestão do seed antes da suíte de relevância")
    return SearchService(
        RuleBasedIntentParser(),
        FtsSearchProvider(db_session),
        DeterministicRanking(),
    )


@pytest.fixture(scope="session")
def catalogo_tem_use_case(db_session: Session) -> bool:
    """O catálogo carregado tem rótulos de `use_case`?

    Os rótulos são produzidos **offline, por LLM** (ADR-0010 D2) e gravados
    direto em `product_specs.attributes`. Eles **não estão no seed versionado**,
    então um banco recém-carregado pela ingestão não os tem: CI, máquina nova ou
    projeto Supabase recriado começam todos sem rótulo nenhum.
    """
    total = db_session.execute(
        select(func.count())
        .select_from(product_specs)
        .where(product_specs.c.attributes.has_key("use_case"))
    ).scalar_one()
    return bool(total)


def pula_sem_rotulo_de_uso(query: str, tem_rotulos: bool) -> None:
    """Pula a consulta que depende de `use_case` quando o catálogo não tem rótulo.

    Por que isto existe, e por que é um remendo consciente: desde o ADR-0010 D2 o
    `RuleBasedIntentParser` converte necessidade ("gamer", "para jogos") em
    **filtro duro** de `use_case`. Contra um catálogo sem rótulos esse filtro não
    casa com nada e a consulta devolve zero, então o teste mediria a ausência dos
    rótulos, não a qualidade da busca. Falhar aqui seria falha em falso, no mesmo
    sentido em que `db_session` pula sem Postgres.

    O preço é real e está registrado: onde isto pula, o KPI de relevância do PRD
    **não é verificado**, e era exatamente para verificá-lo em todo merge que a CI
    ganhou um serviço Postgres. A correção de raiz é versionar os rótulos no seed,
    o que tornaria este helper desnecessário. Ver ADR-0013.
    """
    if tem_rotulos:
        return
    intent = RuleBasedIntentParser().parse(query)
    if (intent.attributes or {}).get("use_case"):
        pytest.skip(
            f"'{query}' vira filtro duro de use_case, e o catálogo carregado não tem "
            "rótulos (eles não vêm no seed). Rode tools.seedbuilder.label_use_cases "
            "para medir o KPI de verdade."
        )
