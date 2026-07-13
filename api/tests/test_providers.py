"""Testes do FtsSearchProvider (retrieval Postgres FTS — Fase 3, RF-10, ADR-0007).

A sessão é substituída por um fake que captura o statement e devolve linhas prontas,
então testamos o mapeamento row->hit e a construção do SQL (filtros/precedência) sem
um Postgres real. A execução ponta-a-ponta é coberta contra o banco à parte.
"""

from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.search.intent import Intent
from app.search.providers import CANDIDATE_POOL, FtsSearchProvider


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    """Captura o último statement e devolve linhas pré-definidas."""

    def __init__(self, rows=None):
        self._rows = rows or []
        self.last_stmt = None

    def execute(self, stmt):
        self.last_stmt = stmt
        return _FakeResult(self._rows)

    def _compiled(self):
        return self.last_stmt.compile(dialect=postgresql.dialect())

    def sql(self) -> str:
        return str(self._compiled())

    def bound_values(self) -> list:
        return list(self._compiled().params.values())


def _row(**kw):
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "slug": "dell-xps",
        "name": "Dell XPS",
        "category": "notebooks",
        "brand": "Dell",
        "min_price": Decimal("3999.90"),
        "fts_rank": 0.42,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_mapeia_row_para_hit_com_tipos_normalizados():
    session = _FakeSession([_row()])
    hits = FtsSearchProvider(session).search(Intent(raw="notebook dell"))
    assert len(hits) == 1
    hit = hits[0]
    assert hit["slug"] == "dell-xps"
    assert hit["category"] == "notebooks"
    assert hit["brand"] == "Dell"
    # Decimal -> float (para o ranking somar sem misturar tipos)
    assert isinstance(hit["min_price"], float) and hit["min_price"] == 3999.90
    assert isinstance(hit["fts_rank"], float) and hit["fts_rank"] == 0.42
    assert isinstance(hit["id"], str)


def test_min_price_none_e_fts_rank_none_viram_valores_seguros():
    session = _FakeSession([_row(min_price=None, fts_rank=None)])
    hit = FtsSearchProvider(session).search(Intent(raw="x"))[0]
    assert hit["min_price"] is None
    assert hit["fts_rank"] == 0.0  # sem query/rank -> 0.0, não None


def test_sem_hits_retorna_lista_vazia():
    assert FtsSearchProvider(_FakeSession([])).search(Intent(raw="nada")) == []


def test_intent_tem_precedencia_sobre_filters_na_categoria_e_preco():
    session = _FakeSession([])
    intent = Intent(raw="fone", category="fones", price_max=300.0)
    FtsSearchProvider(session).search(intent, filters={"category": "notebooks", "price_max": 9999})
    valores = session.bound_values()
    # a categoria e o teto do intent entram no SQL; os de filters não sobrescrevem
    assert "fones" in valores
    assert 300.0 in valores
    assert "notebooks" not in valores
    assert 9999 not in valores


def test_filtros_de_ui_complementam_o_intent():
    session = _FakeSession([])
    # marca não é extraída pelo parser: vem via filters e deve entrar no WHERE
    FtsSearchProvider(session).search(Intent(raw="notebook"), filters={"brand": "dell"})
    assert "dell" in session.bound_values()


def test_limita_ao_pool_de_candidatos():
    session = _FakeSession([])
    FtsSearchProvider(session).search(Intent(raw="notebook"))
    assert f"LIMIT {CANDIDATE_POOL}" in session.sql() or CANDIDATE_POOL in session.bound_values()
