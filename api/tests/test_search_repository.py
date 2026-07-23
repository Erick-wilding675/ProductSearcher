"""Construção de SQL do SqlSearchRepository — filtro por atributos (RF-12).

Sessão fake que compila o statement no dialeto Postgres: valida que o filtro por
atributos vira JSONB containment (@>) com join em product_specs, sem precisar de banco.
"""

from sqlalchemy.dialects import postgresql

from app.search.repository import SqlSearchRepository


class _FakeResult:
    def all(self):
        return []

    def scalar_one(self):
        return 0


class _FakeSession:
    def __init__(self):
        self.sqls = []

    def execute(self, stmt):
        self.sqls.append(str(stmt.compile(dialect=postgresql.dialect())))
        return _FakeResult()


def test_filtro_de_atributos_usa_containment_jsonb():
    session = _FakeSession()
    SqlSearchRepository(session).search(q="notebook", attributes={"ram_gb": 16})
    sql = " ".join(session.sqls)
    assert "product_specs" in sql  # join na tabela de specs
    assert "@>" in sql  # containment JSONB
    assert "CAST" in sql.upper()  # cast do filtro para JSONB


def test_sem_atributos_nao_junta_product_specs():
    session = _FakeSession()
    SqlSearchRepository(session).search(q="notebook")
    assert "product_specs" not in " ".join(session.sqls)
