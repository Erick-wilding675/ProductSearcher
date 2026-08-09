"""Engine/sessão do SQLAlchemy.

TODO Fase 2/3: revisar pool, migrations (Alembic) e registro de tipos pgvector.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# `prepare_threshold=None` desliga os prepared statements do psycopg3.
#
# O Supabase é acessado pelo **pooler em modo transação** (porta 6543), que
# multiplexa várias sessões na mesma conexão do Postgres. Prepared statements são
# por sessão: quando a mesma consulta repete, o driver tenta reaproveitar um nome
# (`_pg3_0`) que pode pertencer a outra sessão e o banco responde
# `DuplicatePreparedStatement`. Não é hipótese — foi o que derrubou a suíte de
# relevância inteira contra o banco real.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args={"prepare_threshold": None},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Iterator[Session]:
    """Dependency do FastAPI para obter uma sessão por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
