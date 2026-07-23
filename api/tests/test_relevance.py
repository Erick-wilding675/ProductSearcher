"""
Suíte de avaliação de relevância (Top-5).

Objetivo:
Garantir que pelo menos 80% das consultas de teste retornem o
produto esperado entre os cinco primeiros resultados.

Esta suíte mede o KPI de relevância da busca.
"""

from app.search.repository import SearchRepository


TEST_CASES = [
    {
        "query": "lenovo loq",
        "expected": "Notebook Gamer Lenovo Loq 15irx9",
    },
    {
        "query": "alienware",
        "expected": "Notebook Gamer Dell Alienware M16 R2",
    },
    {
        "query": "asus tuf",
        "expected": "Notebook Gamer Asus TUF Gaming F15",
    },
    {
        "query": "acer nitro",
        "expected": "Notebook Gamer Acer Nitro V15",
    },
    {
        "query": "sony xm5",
        "expected": "Sony WH-1000XM5",
    },
    {
        "query": "jbl tune",
        "expected": "JBL Tune 770NC",
    },
    {
        "query": "edifier w820",
        "expected": "Edifier W820NB Plus",
    },
    {
        "query": "qcy h3",
        "expected": "QCY H3 ANC",
    },
]


def test_relevancia_top5(search_repository: SearchRepository):
    """
    Pelo menos 80% das consultas devem retornar o produto esperado
    entre os cinco primeiros resultados.
    """

    hits = 0

    for case in TEST_CASES:

        response = search_repository.search(
            q=case["query"],
            page=1,
        )

        top5 = response.results[:5]

        nomes = {
            item.name.lower()
            for item in top5
        }

        esperado = case["expected"].lower()

        if any(esperado in nome for nome in nomes):
            hits += 1

    score = hits / len(TEST_CASES)

    assert score >= 0.80