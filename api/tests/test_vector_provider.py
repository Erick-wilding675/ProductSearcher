"""Testes do retrieval vetorial (ADR-010 D3).

Dois níveis, de propósito:

- O que roda **sempre**: a forma do SQL e o contrato do provider, com um fake no
  lugar do modelo. Não exige o extra `vector`, nem banco, nem os 750 MB de
  pesos — então a CI verifica isto em todo merge.
- O que roda **só onde o modelo existe** (`test_embedding_real.py`): a qualidade
  do vetor. Separado porque depende de artefato pesado, e misturar os dois faria
  a suíte inteira ser pulada quando o modelo falta.
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from app.search.providers import PgVectorProvider


class _EmbedderFake:
    """Modelo de mentira: devolve um vetor fixo e conta as chamadas.

    Existe para provar que o provider **não** vetoriza produto pelo caminho da
    consulta — a assimetria do e5 é a coisa mais fácil de quebrar por engano
    aqui, e ela não dá erro quando quebra.
    """

    def __init__(self) -> None:
        self.consultas: list[str] = []

    def embed_query(self, texto: str) -> list[float]:
        self.consultas.append(texto)
        return [0.1] * 768


class _SessionFake:
    def __init__(self, linhas: list | None = None) -> None:
        self.linhas = linhas or []
        self.stmt = None

    def execute(self, stmt):
        self.stmt = stmt
        return self

    def all(self):
        return self.linhas


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_search_ordena_por_distancia_de_cosseno():
    """`<=>` e não outro operador: é o que o índice HNSW foi criado para servir.

    Trocar por distância L2 não daria erro — só deixaria de usar o índice
    `vector_cosine_ops` e passaria a varrer a tabela.
    """
    session = _SessionFake()
    PgVectorProvider(session, embedder=_EmbedderFake()).search([0.1] * 768, k=5)

    sql = _sql(session.stmt)
    assert "<=>" in sql, sql
    assert "ORDER BY" in sql.upper()


def test_search_exclui_produto_sem_vetor():
    """Produto ainda não vetorizado é desconhecido, não 'muito distante'.

    Sem o filtro, a ordenação de nulos do Postgres decide por conta própria se
    eles vão para o topo — e um produto sem vetor no topo do resultado semântico
    é pior que ausência.
    """
    session = _SessionFake()
    PgVectorProvider(session, embedder=_EmbedderFake()).search([0.1] * 768)

    sql = _sql(session.stmt).upper()
    assert "IS NOT NULL" in sql, sql


def test_search_respeita_o_k():
    session = _SessionFake()
    PgVectorProvider(session, embedder=_EmbedderFake()).search([0.1] * 768, k=7)
    assert "LIMIT" in _sql(session.stmt).upper()


def test_search_devolve_ids_como_texto():
    class _Linha:
        id = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"

    session = _SessionFake([_Linha()])
    ids = PgVectorProvider(session, embedder=_EmbedderFake()).search([0.1] * 768)
    assert ids == ["3f2504e0-4f89-11d3-9a0c-0305e82c3301"]
    assert all(isinstance(i, str) for i in ids)


def test_embed_query_delega_ao_modelo():
    fake = _EmbedderFake()
    provider = PgVectorProvider(_SessionFake(), embedder=fake)

    vetor = provider.embed_query("notebook para faculdade")

    assert fake.consultas == ["notebook para faculdade"]
    assert len(vetor) == 768


def test_provider_nao_expoe_caminho_de_texto_cru():
    """A invariante 2 do módulo de embedding, verificada na superfície pública.

    Se um `embed()` genérico reaparecer aqui, volta a ser possível vetorizar
    produto pelo caminho da consulta — que é falha silenciosa, não erro.
    """
    assert not hasattr(PgVectorProvider, "embed")
    assert hasattr(PgVectorProvider, "embed_query")


def test_texto_do_produto_espelha_o_search_vector():
    """Os dois caminhos da busca têm de enxergar o mesmo produto.

    Se o texto vetorizado divergir de `name || model || description`, a união do
    D4 passa a comparar descrições diferentes do mesmo item e a diferença de
    resultado vira ruído que ninguém consegue atribuir.
    """
    from app.search.embedding import texto_do_produto

    assert texto_do_produto("Notebook X", "15IRH10", "Para estudo") == (
        "Notebook X 15IRH10 Para estudo"
    )


@pytest.mark.parametrize(
    ("nome", "modelo", "descricao", "esperado"),
    [
        ("Notebook X", None, None, "Notebook X"),
        ("Notebook X", "", "  ", "Notebook X"),
        ("Notebook X", "M1", None, "Notebook X M1"),
    ],
)
def test_texto_do_produto_ignora_campos_vazios(nome, modelo, descricao, esperado):
    """`model` e `description` são nulos em parte do seed (ADR-0008)."""
    from app.search.embedding import texto_do_produto

    assert texto_do_produto(nome, modelo, descricao) == esperado
