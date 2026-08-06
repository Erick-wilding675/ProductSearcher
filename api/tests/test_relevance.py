"""Suíte de avaliação de relevância (Top-5) — KPI do PRD.

Meta: **≥80%** das consultas de teste devem trazer o produto esperado entre os
cinco primeiros resultados (docs/prd.md §5).

Não é teste unitário: mede a qualidade real do retrieval (Postgres FTS PT-BR)
contra o **seed carregado**. Exige banco — a fixture `search_repository`
(`conftest.py`) pula a suíte quando não há Postgres ou o catálogo está vazio.

Os casos usam produtos que existem no seed e consultas no formato que o usuário
digita (marca + modelo, ou linguagem natural). `expected` é o trecho **distintivo**
do nome — os títulos do seed vêm de marketplace e são longos/ruidosos demais para
casar por igualdade.

Ao trocar o seed, recalibre os casos: um `expected` que não existe mais no catálogo
mede zero e derruba o KPI sem que a busca tenha piorado.
"""

import pytest

from app.search.repository import SearchRepository

# (consulta do usuário, trecho que identifica o produto esperado)
TEST_CASES: list[tuple[str, str]] = [
    # Notebooks
    ("notebook gamer acer nitro rtx", "Nitro V15"),
    ("acer predator helios", "Predator Helios"),
    ("dell latitude i7", "Latitude 5531"),
    ("notebook asus tuf gamer", "TUF Gam"),
    ("acer aspire go 15", "Aspire Go 15"),
    ("hp pavilion gamer", "Pavilion Gamer"),
    ("lenovo loq", "LOQ"),
    # Fones
    ("fone bluetooth anker soundcore com cancelamento", "Q20i"),
    ("fone aiwa bluetooth", "AWS-EB"),
    ("headset gamer havit", "Havit"),
    ("fone samsung galaxy buds", "Buds"),
    ("qcy h3", "QCY H3"),
]

TOP_N = 5
META = 0.80


def _acertou(repo: SearchRepository, query: str, esperado: str) -> bool:
    """True se `esperado` aparece no nome de algum dos TOP_N resultados."""
    resposta = repo.search(q=query, page=1)
    alvo = esperado.lower()
    return any(alvo in item.name.lower() for item in resposta.results[:TOP_N])


def test_relevancia_top5(search_repository: SearchRepository) -> None:
    """KPI agregado: ≥80% das consultas com o produto esperado no top-5."""
    faltaram = [
        f"{query!r} (esperava {esperado!r})"
        for query, esperado in TEST_CASES
        if not _acertou(search_repository, query, esperado)
    ]

    score = 1 - len(faltaram) / len(TEST_CASES)
    assert score >= META, (
        f"Relevância top-{TOP_N}: {score:.0%} (meta {META:.0%}). "
        f"Consultas sem o esperado: " + "; ".join(faltaram)
    )


@pytest.mark.parametrize(("query", "esperado"), TEST_CASES, ids=lambda v: v)
def test_consulta_individual(
    search_repository: SearchRepository, query: str, esperado: str
) -> None:
    """Cada consulta isolada — aponta exatamente qual regrediu."""
    assert _acertou(search_repository, query, esperado), (
        f"{esperado!r} não apareceu no top-{TOP_N} de {query!r}"
    )
