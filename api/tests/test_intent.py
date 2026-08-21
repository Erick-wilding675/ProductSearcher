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
        ("notebook gamer ate R$ 8.000", "notebook"),
        ("fone com anc até 300", "fone com anc"),
        # "gamer" também sai, mas por outro motivo: virou o filtro use_case=jogos
        # (ADR-010 D2). A regra é a mesma do preço — o que virou filtro duro não
        # pode continuar obrigatório no AND.
        ("notebook gamer", "notebook"),
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
        ("melhores notebooks para trabalho", "notebooks para"),  # "trabalho" virou use_case
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


# --- faixas numéricas (ADR-0010, D2) ----------------------------------------


@pytest.mark.parametrize(
    ("query", "esperado"),
    [
        # comparador antes do número
        ("fone com pelo menos 30 horas de bateria", {"battery_h": {"min": 30.0}}),
        ("fone com no minimo 20h", {"battery_h": {"min": 20.0}}),
        ("fone a partir de 25 horas", {"battery_h": {"min": 25.0}}),
        ("fone acima de 40 horas", {"battery_h": {"min": 40.0}}),
        # comparador depois do número
        ("fone 40h ou mais", {"battery_h": {"min": 40.0}}),
        ("notebook 16gb de ram ou mais", {"ram_gb": {"min": 16.0}}),
        # teto
        ("fone ate 20 horas de bateria", {"battery_h": {"max": 20.0}}),
        ("notebook ate 1,5kg", {"weight_kg": {"max": 1.5}}),
        ("notebook menos de 2kg", {"weight_kg": {"max": 2.0}}),
        # as duas pontas na mesma consulta
        ("notebook acima de 14 polegadas e menos de 2kg",
         {"screen_in": {"min": 14.0}, "weight_kg": {"max": 2.0}}),
        # armazenamento precisa da palavra ao lado; "gb" sozinho é ambíguo
        ("notebook a partir de 512gb de ssd", {"storage_gb": {"min": 512.0}}),
        # sem comparador não é faixa
        ("notebook com 16gb de ram", {}),
        ("notebook gamer", {}),
    ],
)  # fmt: skip
def test_extrai_faixa_numerica(parser: RuleBasedIntentParser, query: str, esperado: dict) -> None:
    assert parser.parse(query).attribute_ranges == esperado


def test_faixa_e_atributo_exato_nao_disputam_a_mesma_chave(
    parser: RuleBasedIntentParser,
) -> None:
    """ "no mínimo 16GB" é piso, não igualdade — senão exclui as máquinas de 32GB.

    Guarda de regressão: o `_RAM_PATTERN` casa a mesma frase e, se ainda gravasse
    `ram_gb = 16`, o containment `@>` andaria junto do `>=` e o filtro voltaria
    a ser exato sem ninguém perceber.
    """
    intent = parser.parse("notebook com no minimo 16gb de ram")

    assert intent.attribute_ranges == {"ram_gb": {"min": 16.0}}
    assert "ram_gb" not in intent.attributes


@pytest.mark.parametrize(
    ("query", "preco", "faixa"),
    [
        # o número tem unidade: é medida, não preço
        ("fone ate 20 horas de bateria", None, {"battery_h": {"max": 20.0}}),
        ("notebook ate 1,5kg", None, {"weight_kg": {"max": 1.5}}),
        # sem unidade continua sendo teto de preço
        ("notebook ate 5000", 5000.0, {}),
        ("notebook ate R$ 5.000", 5000.0, {}),
        # as duas coisas cabem na mesma consulta
        ("fone ate R$300 com pelo menos 30 horas", 300.0, {"battery_h": {"min": 30.0}}),
    ],
)
def test_unidade_impede_que_a_medida_vire_teto_de_preco(
    parser: RuleBasedIntentParser, query: str, preco: float | None, faixa: dict
) -> None:
    """ "até 20 horas" não é R$ 20.

    O defeito era silencioso e fatal: nenhum fone custa R$ 20, então a consulta
    voltava vazia sem nada indicar que o parser tinha confundido as coisas. Em
    "até 1,5kg" era pior — a conversão de preço lê "." como milhar e virava R$ 15.
    """
    intent = parser.parse(query)

    assert intent.price_max == preco
    assert intent.attribute_ranges == faixa


def test_expressao_por_extenso_vira_faixa_na_categoria_certa(
    parser: RuleBasedIntentParser,
) -> None:
    """ "o dia todo" é quantidade dita sem número — e é do parser, não do LLM.

    A guarda de categoria não é detalhe: `battery_h` não existe no schema de
    notebooks, então inferir a chave ali zeraria a busca por uma adivinhação do
    parser. Com número digitado o usuário assume a consequência; adivinhando, não.
    """
    fone = parser.parse("fone com bateria para o dia todo")
    assert fone.attribute_ranges == {"battery_h": {"min": 30.0}}

    notebook = parser.parse("notebook com bateria para o dia todo")
    assert notebook.attribute_ranges == {}


def test_numero_dito_vence_a_expressao_por_extenso(parser: RuleBasedIntentParser) -> None:
    """Quem escreveu "15 horas" pediu 15, mesmo dizendo "dia todo" na mesma frase."""
    intent = parser.parse("fone para o dia todo com pelo menos 15 horas")
    assert intent.attribute_ranges == {"battery_h": {"min": 15.0}}


@pytest.mark.parametrize(
    ("query", "fora_do_texto"),
    [
        ("fone com pelo menos 30 horas de bateria", ["30", "horas", "menos"]),
        ("fone com bateria para o dia todo", ["dia", "todo"]),
        ("notebook ate 1,5kg", ["1,5", "kg"]),
    ],
)
def test_texto_para_fts_sai_sem_a_faixa(
    parser: RuleBasedIntentParser, query: str, fora_do_texto: list[str]
) -> None:
    """O que virou filtro sai do texto — mesma razão do preço.

    `plainto_tsquery` combina com AND: "dia" sobrando exigiria a palavra "dia" no
    anúncio e zeraria justamente a busca que o filtro acabou de tornar possível.
    """
    texto = parser.parse(query).text
    for termo in fora_do_texto:
        assert termo not in texto, f"{termo!r} deveria ter saído de {texto!r}"


# ---- use_case: necessidade vira filtro duro (ADR-010 D2, metade de runtime) ----


@pytest.mark.parametrize(
    ("query", "categoria", "esperado"),
    [
        ("notebook para jogos", "notebooks", ["jogos"]),
        ("notebook para faculdade", "notebooks", ["estudo"]),
        ("notebook leve para viagem", "notebooks", ["portabilidade"]),
        ("fone para academia", "headphones", ["esporte"]),
        ("fone para correr", "headphones", ["esporte"]),
        ("fone para viagem de aviao", "headphones", ["viagem"]),
        # Mesma palavra, catálogos diferentes: "viagem" em notebook é peso; em
        # fone é ruído de cabine. É o motivo de o vocabulário ser por categoria.
        ("fone para reuniao online", "headphones", ["chamadas"]),
    ],
)
def test_necessidade_vira_use_case(
    parser: RuleBasedIntentParser, query: str, categoria: str, esperado: list[str]
) -> None:
    intent = parser.parse(query)
    assert intent.category == categoria
    assert intent.attributes["use_case"] == esperado


def test_sem_categoria_nao_rotula(parser: RuleBasedIntentParser) -> None:
    """"para viagem" sozinho é ambíguo entre `portabilidade` e `viagem`.

    Chutar traria filtro duro errado — pior que filtro nenhum, porque o
    containment JSONB não perdoa: o produto certo simplesmente não volta.
    """
    intent = parser.parse("algo para viagem")
    assert "use_case" not in intent.attributes


def test_termo_de_uso_sai_do_texto_do_fts(parser: RuleBasedIntentParser) -> None:
    """O rótulo cobre a necessidade; a palavra não pode continuar no AND.

    "faculdade" não aparece em nenhum dos 235 anúncios do catálogo: mantê-la no
    texto faria o filtro acertar e o `plainto_tsquery` zerar em seguida.
    """
    intent = parser.parse("notebook para faculdade")

    assert intent.attributes["use_case"] == ["estudo"]
    assert "faculdade" not in intent.text


def test_uso_convive_com_preco_e_faixa(parser: RuleBasedIntentParser) -> None:
    """Os três filtros saem do texto pelo mesmo mecanismo de trechos consumidos."""
    intent = parser.parse("fone para academia ate R$300 com pelo menos 20 horas de bateria")

    assert intent.attributes["use_case"] == ["esporte"]
    assert intent.price_max == 300.0
    assert intent.attribute_ranges == {"battery_h": {"min": 20.0}}
    assert "academia" not in intent.text
    assert "300" not in intent.text
