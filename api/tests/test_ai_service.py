"""Explicação determinística do ranking (ADR-0010 D6).

O que estes testes protegem não é a redação — é a **fidelidade**: a frase não
pode afirmar nada que o `context` não trouxe, nem omitir que um critério ficou
de fora. É a mesma regra que a versão por LLM terá de obedecer, e é por isso que
ela está escrita como teste e não como comentário.
"""

import pytest

from app.ai.service import DeterministicAIService, LLMAIService


def _fatores(**scores: float) -> dict:
    """Fatores no formato do ranking: os citados são aplicáveis, o resto não."""
    todos = ("relevance", "price", "attributes", "preference")
    return {nome: {"score": scores.get(nome, 0.0), "applicable": nome in scores} for nome in todos}


@pytest.fixture
def service() -> DeterministicAIService:
    return DeterministicAIService()


def test_cita_posicao_nome_e_consulta(service: DeterministicAIService) -> None:
    texto = service.explain(
        {
            "query": "notebook gamer",
            "position": 1,
            "item": {"name": "Notebook Acer Nitro V15", "factors": _fatores(relevance=1.0)},
        }
    )

    assert "Notebook Acer Nitro V15" in texto
    assert "1º" in texto
    assert "notebook gamer" in texto


def test_traduz_preco_em_folga_verificavel(service: DeterministicAIService) -> None:
    """Com preço e teto no context, a frase dá reais — não o score do fator."""
    texto = service.explain(
        {
            "query": "notebook até 5000",
            "position": 2,
            "item": {
                "name": "Notebook X",
                "min_price": 4299.0,
                "factors": _fatores(relevance=0.8, price=0.14),
            },
            "intent": {"price_max": 5000.0},
        }
    )

    assert "R$ 4.299,00" in texto
    assert "R$ 701,00" in texto
    assert "R$ 5.000,00" in texto


def test_sem_teto_no_context_nao_inventa_valor(service: DeterministicAIService) -> None:
    """Preço aplicável mas sem `intent.price_max`: cai na frase genérica."""
    texto = service.explain(
        {
            "item": {"name": "Notebook X", "min_price": 4299.0, "factors": _fatores(price=0.5)},
        }
    )

    assert "R$" not in texto
    assert "teto" in texto


def test_lista_apenas_os_atributos_que_o_item_tem(service: DeterministicAIService) -> None:
    texto = service.explain(
        {
            "item": {
                "name": "Notebook X",
                "specs": {"ram_gb": 16, "storage_type": "SSD"},
                "factors": _fatores(attributes=0.5),
            },
            "intent": {"attributes": {"ram_gb": 16, "anc": True}},
        }
    )

    assert "ram_gb = 16" in texto
    # `anc` foi pedido e o item não tem: não pode ser citado como atendido.
    assert "anc" not in texto
    # `storage_type` o item tem, mas não foi pedido: não é razão da posição.
    assert "storage_type" not in texto
    # Metade dos pedidos atendida não pode ser dita como se fosse tudo.
    assert "parte do que você pediu" in texto


def test_atributo_com_valor_divergente_nao_conta_como_atendido(
    service: DeterministicAIService,
) -> None:
    """Chave presente com outro valor não é atributo atendido (regra do ranking)."""
    texto = service.explain(
        {
            "item": {
                "name": "Notebook X",
                "specs": {"ram_gb": 8},
                "factors": _fatores(attributes=0.0),
            },
            "intent": {"attributes": {"ram_gb": 16}},
        }
    )

    assert "ram_gb" not in texto


def test_relevancia_parcial_nao_vira_frase_absoluta(service: DeterministicAIService) -> None:
    """`relevance` é normalizada pelo melhor do conjunto: 0.62 não é "o melhor"."""
    parcial = service.explain({"item": {"name": "Notebook X", "factors": _fatores(relevance=0.62)}})
    melhor = service.explain({"item": {"name": "Notebook X", "factors": _fatores(relevance=1.0)}})

    assert "mais se aproxima" not in parcial
    assert "62% do melhor casamento" in parcial
    assert "mais se aproxima" in melhor


def test_ordena_do_que_mais_pesou_para_o_que_menos(service: DeterministicAIService) -> None:
    """Preferência tem peso 2.0 e domina por construção — tem que vir primeiro."""
    texto = service.explain(
        {
            "item": {"name": "Notebook X", "factors": _fatores(relevance=1.0, preference=1.0)},
        }
    )

    assert texto.index("preferência") < texto.index("texto do anúncio")


def test_declara_os_criterios_que_ficaram_de_fora(service: DeterministicAIService) -> None:
    """Omitir a ausência faria o usuário supor um cuidado que o ranking não teve."""
    texto = service.explain({"item": {"name": "Notebook X", "factors": _fatores(relevance=1.0)}})

    assert "Fora da conta" in texto
    assert "não informou um teto" in texto
    assert "não pediu nenhuma" in texto


def test_pontuou_zero_em_tudo_e_dito_sem_elogio(service: DeterministicAIService) -> None:
    texto = service.explain(
        {"item": {"name": "Notebook X", "factors": _fatores(relevance=0.0, price=0.0)}}
    )

    assert "Nenhum dos critérios" in texto
    assert "não por se destacar" in texto


def test_consulta_sem_criterio_ativo(service: DeterministicAIService) -> None:
    texto = service.explain({"item": {"name": "Notebook X", "factors": _fatores()}})

    assert "ordem é a padrão do catálogo" in texto
    # Sem critério algum ativo, listar as ausências uma a uma seria ruído.
    assert "Fora da conta" not in texto


def test_context_vazio_nao_quebra(service: DeterministicAIService) -> None:
    """A explicação é acessório: não pode derrubar quem a chama."""
    texto = service.explain({})

    assert texto
    assert "Este produto" in texto


def test_deterministico(service: DeterministicAIService) -> None:
    context = {
        "query": "notebook até 5000",
        "position": 3,
        "item": {
            "name": "Notebook X",
            "min_price": 4299.0,
            "specs": {"ram_gb": 16},
            "factors": _fatores(relevance=0.7, price=0.14, attributes=1.0),
        },
        "intent": {"price_max": 5000.0, "attributes": {"ram_gb": 16}},
    }

    assert service.explain(context) == service.explain(context)


def test_llm_ainda_nao_existe_e_diz_por_que() -> None:
    """RF-61 é condicional (ADR-0010 D6): a mensagem aponta o caminho certo."""
    with pytest.raises(NotImplementedError, match="DeterministicAIService"):
        LLMAIService().explain({})


def test_faixa_atendida_e_citada_com_o_valor_do_produto(
    service: DeterministicAIService,
) -> None:
    """A faixa pesa no score, então tem de poder ser dita — senão a prosa
    esconde o motivo da posição. E cita o valor do produto (40h), não o piso."""
    texto = service.explain(
        {
            "item": {
                "name": "Fone X",
                "specs": {"battery_h": 40},
                "factors": _fatores(attributes=1.0),
            },
            "intent": {"attribute_ranges": {"battery_h": {"min": 30.0}}},
        }
    )

    assert "battery_h = 40" in texto


def test_faixa_nao_atendida_nao_e_citada(service: DeterministicAIService) -> None:
    """Mesma regra do atributo divergente (D6): 10h não atende a "30h ou mais",
    e dizer que atende é exatamente a mentira que o contrato de `explain` proíbe."""
    texto = service.explain(
        {
            "item": {
                "name": "Fone X",
                "specs": {"battery_h": 10},
                "factors": _fatores(attributes=0.0),
            },
            "intent": {"attribute_ranges": {"battery_h": {"min": 30.0}}},
        }
    )

    assert "battery_h" not in texto
