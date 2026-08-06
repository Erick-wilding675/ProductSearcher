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

from app.catalog.tables import products
from app.core.config import settings
from app.search.intent import RuleBasedIntentParser
from app.search.providers import FtsSearchProvider
from app.search.ranking import DeterministicRanking
from app.search.service import SearchService


@pytest.fixture(scope="session")
def db_session() -> Iterator[Session]:
    """Sessão contra o Postgres real. Pula a suíte se o banco não responder."""
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
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
