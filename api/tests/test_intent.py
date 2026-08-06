"""Testes do IntentParser determinístico (Fase 3, RF-11)."""

import pytest

from app.search.intent import RuleBasedIntentParser


@pytest.fixture
def parser() -> RuleBasedIntentParser:
    return RuleBasedIntentParser()


def test_parses_category_and_price(parser: RuleBasedIntentParser) -> None:
    intent = parser.parse("melhor notebook até R$5000")
    assert intent.category == "notebooks"
    assert intent.price_max == 5000


@pytest.mark.parametrize(
    ("query", "esperado"),
    [
        ("notebook para trabalho", "notebooks"),
        ("melhores notebooks", "notebooks"),
        ("laptop para faculdade", "notebooks"),
        ("fone bluetooth", "headphones"),
        ("fones com cancelamento", "headphones"),
        ("headset gamer", "headphones"),
        ("geladeira duplex", None),  # fora das categorias cobertas
    ],
)
def test_extrai_categoria(parser: RuleBasedIntentParser, query: str, esperado: str | None) -> None:
    assert parser.parse(query).category == esperado


def test_categoria_usa_slug_do_catalogo(parser: RuleBasedIntentParser) -> None:
    """O slug precisa casar com `categories.slug`; divergir vira zero resultado.

    Guarda de regressão: o parser já devolveu "notebook"/"headphone" (singular)
    enquanto o seed grava "notebooks"/"headphones".
    """
    assert parser.parse("notebook").category == "notebooks"
    assert parser.parse("fone").category == "headphones"


def test_categoria_vence_o_termo_mais_a_esquerda(parser: RuleBasedIntentParser) -> None:
    """Em "fone para notebook" o assunto é o fone, não o notebook."""
    assert parser.parse("fone bluetooth para notebook").category == "headphones"
    assert parser.parse("notebook com fone incluso").category == "notebooks"


@pytest.mark.parametrize(
    ("query", "esperado"),
    [
        ("notebook até 5000", 5000.0),
        ("notebook até R$5000", 5000.0),
        ("notebook até R$ 5.000", 5000.0),
        ("notebook ate R$5.000,99", 5000.99),  # sem acento + separadores pt-BR
        ("notebook barato", None),  # sem teto declarado
    ],
)
def test_extrai_preco_maximo(
    parser: RuleBasedIntentParser, query: str, esperado: float | None
) -> None:
    assert parser.parse(query).price_max == esperado


@pytest.mark.parametrize(
    ("query", "esperado"),
    [
        ("notebook 16gb ram", {"ram_gb": 16}),
        ("notebook ram 8gb", {"ram_gb": 8}),
        ("notebook 16 gb de ram", {"ram_gb": 16}),
        ("notebook com ssd", {"storage_type": "SSD"}),
        ("notebook hdd barato", {"storage_type": "HDD"}),
        ("fone com anc", {"anc": True}),
        ("fone com cancelamento de ruído", {"anc": True}),
        ("notebook 16gb ram ssd", {"ram_gb": 16, "storage_type": "SSD"}),
        ("notebook bom", {}),  # nada estruturado a extrair
    ],
)
def test_extrai_atributos(parser: RuleBasedIntentParser, query: str, esperado: dict) -> None:
    assert parser.parse(query).attributes == esperado


def test_armazenamento_nao_vira_memoria(parser: RuleBasedIntentParser) -> None:
    """ "512gb ssd" é armazenamento — só conta como RAM se estiver colado em "ram"."""
    atributos = parser.parse("notebook 512gb ssd").attributes
    assert "ram_gb" not in atributos
    assert atributos["storage_type"] == "SSD"


def test_preserva_query_original(parser: RuleBasedIntentParser) -> None:
    """`raw` guarda o que o usuário digitou (log/UI), sem normalização."""
    query = "Melhor NOTEBOOK até R$5000"
    assert parser.parse(query).raw == query


@pytest.mark.parametrize(
    ("query", "esperado"),
    [
        ("notebook gamer ate R$ 8.000", "notebook gamer"),
        ("fone com anc até 300", "fone com anc"),
        ("notebook gamer", "notebook gamer"),  # sem preço, texto intacto
    ],
)
def test_texto_para_fts_sai_sem_o_preco(
    parser: RuleBasedIntentParser, query: str, esperado: str
) -> None:
    """`plainto_tsquery` faz AND dos termos: deixar "até R$5000" no texto exigiria
    "ate"/"r"/"5000" no produto e devolveria zero. O preço vira filtro, não texto."""
    assert parser.parse(query).text == esperado


@pytest.mark.parametrize(
    ("query", "esperado"),
    [
        ("melhor notebook", "notebook"),
        ("melhores notebooks para trabalho", "notebooks para trabalho"),
        ("notebook bom e barato", "notebook e"),
        ("quero um fone ótimo", "um fone"),
        ("melhor notebook até R$5000", "notebook"),  # preço + filler juntos
    ],
)
def test_texto_para_fts_sai_sem_palavras_de_intencao(
    parser: RuleBasedIntentParser, query: str, esperado: str
) -> None:
    """ "melhor"/"barato" não aparecem em título de produto e, no AND do FTS,
    zerariam o resultado. O dicionário PT-BR não as remove — o parser remove."""
    assert parser.parse(query).text == esperado


@pytest.mark.parametrize("query", ["até R$5000", "melhor custo benefício", "quero o melhor"])
def test_texto_nunca_fica_vazio(parser: RuleBasedIntentParser, query: str) -> None:
    """Se a limpeza consumir tudo, sobra texto: busca ampla > busca vazia."""
    assert parser.parse(query).text


def test_e_deterministico(parser: RuleBasedIntentParser) -> None:
    """Mesmo input ⇒ mesma saída (princípio do projeto, ADR-0007)."""
    query = "fone até R$800"
    primeiro, segundo = parser.parse(query), parser.parse(query)
    assert (primeiro.category, primeiro.price_max) == (segundo.category, segundo.price_max)
