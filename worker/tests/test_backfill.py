"""Testes do backfill do seed (re-derivação a partir do título já coletado)."""

from tools.seedbuilder.backfill import backfill_produto


def test_backfill_preenche_marca_e_formato_ausentes():
    produto = {
        "category": "headphones",
        "name": "Fone De Ouvido Sem Fio Havit Tw982 Enc Bluetooth 5.4 Cor Preto",
        "brand": None,
        "specs": {"anc": True},
    }

    mudancas = backfill_produto(produto)

    assert produto["brand"] == "Havit"
    assert produto["specs"]["type"] == "earbuds"
    assert mudancas


def test_backfill_nunca_sobrescreve_dado_da_api():
    # Valor vindo do marketplace vale mais que o inferido do título.
    produto = {
        "category": "headphones",
        "name": "Headphone Dapon H02D Over-ear Bluetooth 5.1",
        "brand": "Marca Oficial",
        "specs": {"type": "on-ear"},
    }

    backfill_produto(produto)

    assert produto["brand"] == "Marca Oficial"
    assert produto["specs"]["type"] == "on-ear"


def test_backfill_e_idempotente():
    produto = {
        "category": "headphones",
        "name": "Fone de Ouvido Davely A520 In-Ear Bluetooth",
        "brand": None,
        "specs": {},
    }

    primeira = backfill_produto(produto)
    segunda = backfill_produto(produto)

    assert primeira
    assert segunda == []


def test_backfill_nao_inventa_marca_de_anuncio_generico():
    produto = {
        "category": "headphones",
        "name": "Fone De Ouvido Bluetooth 5.0 A Prova De Suor Preto",
        "brand": None,
        "specs": {},
    }

    backfill_produto(produto)

    assert not produto["brand"]
