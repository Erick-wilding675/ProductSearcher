"""Testes do RankingService determinístico e explicável (Fase 3, RF-30/31).

Função pura — sem banco. Fixa as garantias do ADR-0007: determinismo, pesos
renormalizados sobre fatores aplicáveis, critérios/explicação por item e
preferências explícitas por marca ou especificação.
"""

import random

from app.search.intent import Intent
from app.search.ranking import WEIGHTS, DeterministicRanking


def _hit(
    id_,
    name,
    fts_rank,
    min_price=None,
    attributes=None,
    brand_slug=None,
):
    return {
        "id": id_,
        "name": name,
        "fts_rank": fts_rank,
        "min_price": min_price,
        "attributes": attributes or {},
        "brand_slug": brand_slug,
    }


def test_hits_vazio_retorna_itens_vazios_com_criterios():
    out = DeterministicRanking().rank(
        [],
        Intent(raw="notebook", price_max=5000.0),
    )

    assert out["items"] == []

    # Os critérios são sempre descritos, mesmo sem resultados.
    assert {c["factor"] for c in out["criteria"]} == {
        "relevance",
        "price",
        "attributes",
        "preference",
    }


def test_ordenacao_deterministica_sob_embaralhamento():
    hits = [
        _hit("a", "Dell XPS", 0.9, 4800),
        _hit("b", "Dell Inspiron", 0.5, 3000),
        _hit("c", "Acer Aspire", 0.1, 2500),
    ]

    intent = Intent(
        raw="notebook dell",
        price_max=5000.0,
    )

    ordem = [
        i["id"]
        for i in DeterministicRanking().rank(hits, intent)["items"]
    ]

    for _ in range(20):
        embaralhado = hits[:]
        random.shuffle(embaralhado)

        assert [
            i["id"]
            for i in DeterministicRanking().rank(
                embaralhado,
                intent,
            )["items"]
        ] == ordem


def test_relevancia_domina_entre_elegiveis():
    # Todos dentro do teto (filtro duro é do provider);
    # relevância (peso 0.6) decide.
    hits = [
        _hit("a", "A", 0.9, 4800),
        _hit("b", "B", 0.5, 3000),
    ]

    out = DeterministicRanking().rank(
        hits,
        Intent(raw="x", price_max=5000.0),
    )

    assert [i["id"] for i in out["items"]] == [
        "a",
        "b",
    ]


def test_preco_desempata_com_relevancia_igual():
    # Mesma relevância → o mais barato dentro do orçamento vem antes.
    hits = [
        _hit("caro", "Z", 0.5, 4500),
        _hit("barato", "Z", 0.5, 1500),
    ]

    out = DeterministicRanking().rank(
        hits,
        Intent(raw="x", price_max=5000.0),
    )

    assert [i["id"] for i in out["items"]] == [
        "barato",
        "caro",
    ]


def test_cobertura_de_atributos_ordena_e_pontua():
    hits = [
        _hit(
            "full",
            "Fone",
            0.5,
            200,
            {
                "wireless": True,
                "anc": True,
            },
        ),
        _hit(
            "half",
            "Fone",
            0.5,
            200,
            {
                "wireless": True,
                "anc": False,
            },
        ),
    ]

    intent = Intent(
        raw="fone",
        attributes={
            "wireless": True,
            "anc": True,
        },
    )

    out = DeterministicRanking().rank(
        hits,
        intent,
    )

    assert [i["id"] for i in out["items"]] == [
        "full",
        "half",
    ]

    assert (
        out["items"][0]["factors"]["attributes"]["score"]
        == 1.0
    )

    assert (
        out["items"][1]["factors"]["attributes"]["score"]
        == 0.5
    )


def test_criterios_refletem_o_intent():
    out = DeterministicRanking().rank(
        [
            _hit(
                "a",
                "A",
                0.5,
                100,
            )
        ],
        Intent(
            raw="x",
            price_max=1000.0,
        ),
    )

    ativos = {
        c["factor"]: c["active"]
        for c in out["criteria"]
    }

    assert ativos == {
        "relevance": True,
        "price": True,
        "attributes": False,
        "preference": False,
    }

    # Pesos expostos batem com a política.
    assert {
        c["factor"]: c["weight"]
        for c in out["criteria"]
    } == WEIGHTS


def test_desempate_estavel_por_nome_depois_id():
    # Fatores idênticos → desempate objetivo:
    # nome asc, depois id asc.
    hits = [
        _hit("2", "B", 0.5, 100),
        _hit("1", "A", 0.5, 100),
        _hit("0", "B", 0.5, 100),
    ]

    out = DeterministicRanking().rank(
        hits,
        Intent(raw="x", price_max=1000.0),
    )

    assert [i["id"] for i in out["items"]] == [
        "1",
        "0",
        "2",
    ]


def test_renormalizacao_quando_so_um_fator_e_aplicavel():
    # Sem query e sem atributos: só 'price' é aplicável
    # → score == score de preço puro.
    hits = [
        _hit(
            "a",
            "A",
            0.0,
            2500,
        )
    ]

    out = DeterministicRanking().rank(
        hits,
        Intent(
            raw="",
            price_max=5000.0,
        ),
    )

    item = out["items"][0]

    assert item["factors"]["price"]["applicable"] is True
    assert item["factors"]["relevance"]["applicable"] is False
    assert item["factors"]["preference"]["applicable"] is False

    # (5000-2500)/5000 = 0.5,
    # sem diluição pelos pesos inaplicáveis.
    assert item["score"] == 0.5


def test_sem_sinais_score_zero_mas_ordena_por_desempate():
    # Nada aplicável → score 0,
    # ordem apenas por nome/id.
    hits = [
        _hit("b", "Beta", 0.0),
        _hit("a", "Alfa", 0.0),
    ]

    out = DeterministicRanking().rank(
        hits,
        Intent(raw=""),
    )

    assert all(
        i["score"] == 0.0
        for i in out["items"]
    )

    assert [i["id"] for i in out["items"]] == [
        "a",
        "b",
    ]


def test_preferencia_por_marca_leva_matches_para_cima():
    hits = [
        _hit(
            "acer",
            "Acer",
            0.2,
            3000,
            brand_slug="acer",
        ),
        _hit(
            "dell",
            "Dell",
            1.0,
            3000,
            brand_slug="dell",
        ),
    ]

    out = DeterministicRanking().rank(
        hits,
        Intent(raw="notebook"),
        rank_by="brand",
        rank_brand="acer",
    )

    assert [i["id"] for i in out["items"]] == [
        "acer",
        "dell",
    ]

    assert (
        out["items"][0]["factors"]["preference"]["score"]
        == 1.0
    )

    assert (
        out["items"][1]["factors"]["preference"]["score"]
        == 0.0
    )


def test_preferencia_por_spec_leva_matches_para_cima():
    hits = [
        _hit(
            "4050",
            "Notebook RTX 4050",
            0.2,
            4000,
            {
                "gpu": "RTX 4050",
            },
        ),
        _hit(
            "3050",
            "Notebook RTX 3050",
            1.0,
            3500,
            {
                "gpu": "RTX 3050",
            },
        ),
    ]

    out = DeterministicRanking().rank(
        hits,
        Intent(raw="notebook gamer"),
        rank_by="spec",
        rank_spec="gpu",
        rank_spec_value="RTX 4050",
    )

    assert [i["id"] for i in out["items"]] == [
        "4050",
        "3050",
    ]

    assert (
        out["items"][0]["factors"]["preference"]["score"]
        == 1.0
    )

    assert (
        out["items"][1]["factors"]["preference"]["score"]
        == 0.0
    )


def test_preferencia_por_spec_e_case_insensitive():
    hits = [
        _hit(
            "match",
            "Notebook",
            0.1,
            attributes={
                "gpu": "RTX 4050",
            },
        )
    ]

    out = DeterministicRanking().rank(
        hits,
        Intent(raw="notebook"),
        rank_by="spec",
        rank_spec="gpu",
        rank_spec_value="rtx 4050",
    )

    assert (
        out["items"][0]["factors"]["preference"]["score"]
        == 1.0
    )


def test_sem_preferencia_preserva_ranking_anterior():
    hits = [
        _hit(
            "a",
            "A",
            0.9,
            4000,
            brand_slug="acer",
        ),
        _hit(
            "b",
            "B",
            0.3,
            3000,
            brand_slug="dell",
        ),
    ]

    intent = Intent(raw="notebook")

    antigo = DeterministicRanking().rank(
        hits,
        intent,
    )

    explicito = DeterministicRanking().rank(
        hits,
        intent,
        rank_by="relevance",
    )

    assert [i["id"] for i in antigo["items"]] == [
        i["id"]
        for i in explicito["items"]
    ]

    assert all(
        item["factors"]["preference"]["applicable"] is False
        for item in explicito["items"]
    )