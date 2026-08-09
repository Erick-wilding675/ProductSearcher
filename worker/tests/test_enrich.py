"""Testes do enriquecimento do seed pela API do Mercado Livre."""

from tools.seedbuilder.enrich import _ja_tentado, enriquece_produto, preenche_urls_faltantes


class _ClienteFake:
    """MLClient de mentira: devolve o que o teste mandar, sem rede."""

    def __init__(self, ficha=None, anuncios=None, usuarios=None):
        self._ficha = ficha
        self._anuncios = anuncios or []
        self._usuarios = usuarios or {}

    def product(self, product_id):
        return self._ficha

    def product_items(self, product_id):
        return self._anuncios

    def user(self, user_id):
        return self._usuarios.get(user_id)


FICHA = {
    "name": "Notebook Gamer Lenovo LOQ 15IRX9",
    "permalink": "https://produto.ml/MLB1",
    "parent_id": "MLB0",
    "short_description": {"content": "Eleve seu desempenho."},
    "attributes": [
        {"id": "MODEL", "value_name": "LOQ 15IRX9"},
        {"id": "ALPHANUMERIC_MODEL", "value_name": "83KH0001BR"},
        {"id": "RAM_MEMORY_MODULE_TOTAL_CAPACITY", "value_name": "8 GB"},
        {"id": "WEIGHT", "value_name": "2.38 kg"},
    ],
}


def _produto(**extra):
    base = {
        "external_id": "MLB1",
        "category": "notebooks",
        "name": "Notebook Gamer Lenovo Loq 15irx9 ...",
        "specs": {},
        "offers": [],
    }
    base.update(extra)
    return base


def test_preenche_model_description_e_specs():
    p = _produto()

    mudancas = enriquece_produto(p, _ClienteFake(ficha=FICHA))

    assert p["model"] == "LOQ 15IRX9"
    assert p["description"] == "Eleve seu desempenho."
    assert p["specs"]["ram_gb"] == 8
    assert p["specs"]["weight_kg"] == 2.38
    assert p["enrichment"]["status"] == "ok"
    assert "model" in mudancas


def test_nunca_sobrescreve_o_que_ja_existe():
    p = _produto(model="MODELO ANTIGO", description="descrição antiga", specs={"ram_gb": 32})

    enriquece_produto(p, _ClienteFake(ficha=FICHA))

    assert p["model"] == "MODELO ANTIGO"
    assert p["description"] == "descrição antiga"
    assert p["specs"]["ram_gb"] == 32
    # O que faltava, ainda assim entra.
    assert p["specs"]["weight_kg"] == 2.38


def test_produto_despublicado_vira_stale_e_preserva_o_titulo():
    p = _produto(specs={"cpu": "veio do título"})

    mudancas = enriquece_produto(p, _ClienteFake(ficha=None))

    assert p["enrichment"]["status"] == "stale"
    assert p["specs"] == {"cpu": "veio do título"}
    assert mudancas == []


def test_guarda_a_identidade_vinda_do_catalogo():
    p = _produto()

    enriquece_produto(p, _ClienteFake(ficha=FICHA))

    assert p["catalog_parent_id"] == "MLB0"
    assert p["catalog_sku"] == "83KH0001BR"


def test_reexecucao_pula_o_que_ja_deu_certo():
    p = _produto()
    enriquece_produto(p, _ClienteFake(ficha=FICHA))

    assert _ja_tentado(p, retry_stale=False) is True


def test_ok_de_rodada_antiga_e_reconsultado_uma_vez():
    # Carimbo anterior ao ADR-0009: não perguntou identidade, vale reconsultar.
    p = _produto(enrichment={"status": "ok", "date": "2026-08-09"})

    assert _ja_tentado(p, retry_stale=False) is False


def test_produto_sem_pai_nao_e_reconsultado_para_sempre():
    # Nem todo produto de catálogo tem pai; ter perguntado já basta.
    ficha_sem_pai = {k: v for k, v in FICHA.items() if k != "parent_id"}
    p = _produto()
    enriquece_produto(p, _ClienteFake(ficha=ficha_sem_pai))

    assert p.get("catalog_parent_id") is None
    assert _ja_tentado(p, retry_stale=False) is True


def test_stale_e_retentado_so_com_a_flag():
    p = _produto()
    enriquece_produto(p, _ClienteFake(ficha=None))

    assert _ja_tentado(p, retry_stale=False) is True
    assert _ja_tentado(p, retry_stale=True) is False


def test_acrescenta_ofertas_concorrentes_com_url_da_loja():
    p = _produto(offers=[{"store": "Loja Original", "price": "5794", "currency": "BRL"}])
    cliente = _ClienteFake(
        ficha=FICHA,
        anuncios=[
            {"item_id": "MLB9", "price": 5877, "seller_id": 1},
            {"item_id": "MLB8", "price": 5899, "seller_id": 2},
        ],
        usuarios={
            1: {"nickname": "Eletro X", "permalink": "https://perfil.ml/eletrox"},
            2: {"nickname": "Loja Y", "permalink": "https://perfil.ml/lojay"},
        },
    )

    enriquece_produto(p, cliente)

    assert len(p["offers"]) == 3
    nova = p["offers"][1]
    assert nova["store"] == "Eletro X"
    assert nova["store_url"] == "https://perfil.ml/eletrox"
    assert nova["price"] == "5877"


def test_nao_duplica_loja_que_ja_estava_no_seed():
    p = _produto(offers=[{"store": "Eletro X", "price": "5794", "currency": "BRL"}])
    cliente = _ClienteFake(
        ficha=FICHA,
        anuncios=[{"item_id": "MLB9", "price": 5877, "seller_id": 1}],
        usuarios={1: {"nickname": "Eletro X", "permalink": "https://perfil.ml/eletrox"}},
    )

    enriquece_produto(p, cliente)

    assert len(p["offers"]) == 1


def test_anuncio_sem_preco_ou_vendedor_e_ignorado():
    p = _produto()
    cliente = _ClienteFake(
        ficha=FICHA,
        anuncios=[{"item_id": "A", "price": None, "seller_id": 1}, {"item_id": "B", "price": 10}],
        usuarios={1: {"nickname": "Eletro X"}},
    )

    enriquece_produto(p, cliente)

    assert p["offers"] == []


def test_preenche_url_faltante_com_a_pagina_de_catalogo():
    p = _produto(
        offers=[{"store": "A", "price": "1"}, {"store": "B", "price": "2", "url": "https://ja/tem"}]
    )

    preenchidas = preenche_urls_faltantes(p)

    assert preenchidas == 1
    assert p["offers"][0]["url"] == "https://www.mercadolivre.com.br/p/MLB1"
    assert p["offers"][1]["url"] == "https://ja/tem"


def test_preenche_url_e_idempotente():
    p = _produto(offers=[{"store": "A", "price": "1"}])
    preenche_urls_faltantes(p)

    assert preenche_urls_faltantes(p) == 0
