"""Engine/sessão do SQLAlchemy.

TODO Fase 2/3: revisar pool, migrations (Alembic) e registro de tipos pgvector.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Iterator[Session]:
    """Dependency do FastAPI para obter uma sessão por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
