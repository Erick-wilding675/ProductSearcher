"""Testes do FtsSearchProvider (retrieval Postgres FTS — Fase 3, RF-10, ADR-0007).

A sessão é substituída por um fake que captura o statement e devolve linhas prontas,
então testamos o mapeamento row->hit e a construção do SQL (filtros/precedência) sem
um Postgres real. A execução ponta-a-ponta é coberta contra o banco à parte.
"""

from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.search.intent import Intent, RuleBasedIntentParser
from app.search.providers import FtsSearchProvider


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
        "brand_slug": "dell",
        "min_price": Decimal("3999.90"),
        "fts_rank": 0.42,
        "attributes": {
            "ram_gb": 16,
            "storage_type": "SSD",
        },
    }

    base.update(kw)

    return SimpleNamespace(**base)


def test_mapeia_row_para_hit_com_tipos_normalizados():
    session = _FakeSession(
        [
            _row(),
        ]
    )

    hits = FtsSearchProvider(session).search(Intent(raw="notebook dell"))

    assert len(hits) == 1

    hit = hits[0]

    assert hit["slug"] == "dell-xps"
    assert hit["category"] == "notebooks"
    assert hit["brand"] == "Dell"

    # O slug é usado pelo ranking de preferência por marca.
    assert hit["brand_slug"] == "dell"

    # Decimal -> float para o ranking somar sem misturar tipos.
    assert isinstance(
        hit["min_price"],
        float,
    )

    assert hit["min_price"] == 3999.90

    assert isinstance(
        hit["fts_rank"],
        float,
    )

    assert hit["fts_rank"] == 0.42

    assert isinstance(
        hit["id"],
        str,
    )


def test_min_price_none_e_fts_rank_none_viram_valores_seguros():
    session = _FakeSession(
        [
            _row(
                min_price=None,
                fts_rank=None,
            ),
        ]
    )

    hit = FtsSearchProvider(session).search(Intent(raw="x"))[0]

    assert hit["min_price"] is None

    # Sem query/rank -> 0.0, não None.
    assert hit["fts_rank"] == 0.0


def test_sem_hits_retorna_lista_vazia():
    assert FtsSearchProvider(_FakeSession([])).search(Intent(raw="nada")) == []


def test_intent_tem_precedencia_sobre_filters_na_categoria_e_preco():
    session = _FakeSession([])

    intent = Intent(
        raw="fone",
        category="fones",
        price_max=300.0,
    )

    FtsSearchProvider(session).search(
        intent,
        filters={
            "category": "notebooks",
            "price_max": 9999,
        },
    )

    valores = session.bound_values()

    # A categoria e o teto do intent entram no SQL;
    # os de filters não sobrescrevem.
    assert "fones" in valores
    assert 300.0 in valores
    assert "notebooks" not in valores
    assert 9999 not in valores


def test_filtros_de_ui_complementam_o_intent():
    session = _FakeSession([])

    # Marca não é extraída pelo parser:
    # vem via filters e deve entrar no WHERE.
    FtsSearchProvider(session).search(
        Intent(raw="notebook"),
        filters={
            "brand": "dell",
        },
    )

    assert "dell" in session.bound_values()


def test_limita_ao_pool_de_candidatos():
    session = _FakeSession([])

    FtsSearchProvider(session).search(Intent(raw="notebook"))

    pool = settings.search_candidate_pool

    assert f"LIMIT {pool}" in session.sql() or pool in session.bound_values()


def test_fts_usa_texto_sem_preco_e_nao_a_query_crua():
    """Regressão: o provider precisa consultar `intent.text`, não `intent.raw`.

    `plainto_tsquery` combina os termos com AND — mandar "notebook ate r$5000"
    exigiria "ate"/"r"/"5000" no produto e devolveria zero resultado.
    """

    session = _FakeSession([])

    intent = RuleBasedIntentParser().parse("notebook gamer até R$5000")

    FtsSearchProvider(session).search(intent)

    valores = session.bound_values()

    # Texto limpo vai para o tsquery.
    assert "notebook gamer" in valores

    # O preço vira filtro.
    assert 5000.0 in valores

    assert not any(isinstance(value, str) and "5000" in value for value in valores)


def test_hit_carrega_os_atributos_para_o_ranking():
    """O fator de atributos do RankingService lê `hit["attributes"]`.

    Sem essa chave ele ficava sempre com score 0 mas "aplicável", diluindo o score
    final sem discriminar nada.
    """

    session = _FakeSession(
        [
            _row(),
        ]
    )

    hit = FtsSearchProvider(session).search(Intent(raw="notebook"))[0]

    assert hit["attributes"] == {
        "ram_gb": 16,
        "storage_type": "SSD",
    }


def test_hit_carrega_brand_slug_para_preferencia_de_marca():
    """O ranking por marca usa slug, não o nome de exibição."""

    session = _FakeSession(
        [
            _row(
                brand="Acer",
                brand_slug="acer",
            ),
        ]
    )

    hit = FtsSearchProvider(session).search(Intent(raw="notebook"))[0]

    assert hit["brand"] == "Acer"
    assert hit["brand_slug"] == "acer"


def test_produto_sem_specs_nao_quebra_o_hit():
    session = _FakeSession(
        [
            _row(
                attributes=None,
            ),
        ]
    )

    hit = FtsSearchProvider(session).search(Intent(raw="notebook"))[0]

    assert hit["attributes"] == {}


def test_filtro_de_atributos_usa_containment_jsonb():
    """RF-12: o filtro estruturado vira @> sobre product_specs (índice GIN)."""

    session = _FakeSession([])

    FtsSearchProvider(session).search(
        Intent(raw="notebook"),
        filters={
            "attributes": {
                "ram_gb": 16,
            },
        },
    )

    sql = session.sql()

    assert "product_specs" in sql
    assert "@>" in sql


def test_atributos_do_intent_tambem_filtram():
    """O que o parser extrai da consulta filtra igual ao que vem da UI."""

    session = _FakeSession([])

    intent = RuleBasedIntentParser().parse("notebook 16gb ram ssd")

    assert intent.attributes

    FtsSearchProvider(session).search(intent)

    assert "@>" in session.sql()


def test_sem_atributos_nao_filtra_por_specs():
    """Sem atributos pedidos, não deve haver containment no WHERE."""

    session = _FakeSession([])

    FtsSearchProvider(session).search(Intent(raw="notebook"))

    assert "@>" not in session.sql()
