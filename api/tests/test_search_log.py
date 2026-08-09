"""Testes do registro de consultas (tabela `searches`).

A regra que importa aqui é negativa: **falhar ao registrar não pode derrubar a
busca**. Por isso os testes cobrem tanto o caminho feliz quanto a sessão que
explode.
"""

from app.search.intent import Intent, RuleBasedIntentParser
from app.search.log import NullSearchLog, SqlSearchLog
from app.search.ranking import DeterministicRanking
from app.search.service import SearchService


class _SessaoFake:
    """Sessão que grava o que recebeu — ou explode, se `falha=True`."""

    def __init__(self, falha: bool = False) -> None:
        self.falha = falha
        self.executados: list = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, stmt):
        if self.falha:
            raise RuntimeError("banco fora do ar")
        self.executados.append(stmt)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _LogEspiao:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, Intent, int]] = []

    def record(self, query, intent, result_count):
        self.chamadas.append((query, intent, result_count))


class _ProviderFake:
    def __init__(self, hits=None):
        self._hits = hits or []

    def search(self, intent, filters=None, page=1):
        return self._hits


def _service(log=None, hits=None):
    return SearchService(RuleBasedIntentParser(), _ProviderFake(hits), DeterministicRanking(), log)


def test_registra_a_consulta_com_o_total_encontrado():
    log = _LogEspiao()
    hits = [
        {
            "id": "1",
            "slug": "a",
            "name": "Notebook A",
            "category": "notebooks",
            "brand": "Dell",
            "min_price": 100.0,
            "fts_rank": 1.0,
            "attributes": {},
        }
    ]

    _service(log, hits).search(q="notebook gamer")

    assert len(log.chamadas) == 1
    query, intent, total = log.chamadas[0]
    assert query == "notebook gamer"
    assert intent.category == "notebooks"
    assert total == 1


def test_busca_sem_texto_nao_registra():
    # Só filtros: não há consulta que valha analisar.
    log = _LogEspiao()

    _service(log).search(category="notebooks")

    assert log.chamadas == []


def test_registra_tambem_quando_nao_encontra_nada():
    # É justamente o zero que interessa para achar buraco de catálogo.
    log = _LogEspiao()

    _service(log).search(q="geladeira")

    assert log.chamadas[0][2] == 0


def test_servico_funciona_sem_log_configurado():
    resposta = _service().search(q="notebook")

    assert resposta.total == 0


def test_null_log_nao_faz_nada():
    assert NullSearchLog().record("x", Intent(raw="x"), 0) is None


def test_sql_log_grava_e_commita():
    sessao = _SessaoFake()

    SqlSearchLog(sessao).record("notebook 16gb", Intent(raw="notebook 16gb"), 3)

    assert len(sessao.executados) == 1
    assert sessao.commits == 1


def test_sql_log_ignora_consulta_vazia():
    sessao = _SessaoFake()

    SqlSearchLog(sessao).record("   ", Intent(raw="   "), 0)

    assert sessao.executados == []
    assert sessao.commits == 0


def test_sql_log_engole_falha_do_banco():
    # Analytics é secundário: a busca não pode quebrar por causa do log.
    sessao = _SessaoFake(falha=True)

    SqlSearchLog(sessao).record("notebook", Intent(raw="notebook"), 1)

    assert sessao.commits == 0
    assert sessao.rollbacks == 1


def test_falha_no_log_nao_derruba_a_busca():
    servico = SearchService(
        RuleBasedIntentParser(),
        _ProviderFake(),
        DeterministicRanking(),
        SqlSearchLog(_SessaoFake(falha=True)),
    )

    resposta = servico.search(q="notebook")

    assert resposta.total == 0
