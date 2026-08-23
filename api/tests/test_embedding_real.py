"""Testes que exercitam o **modelo de verdade** (ADR-010 D3.3).

Pulados quando o extra `vector` ou os pesos não estão presentes — é o mesmo
critério da suíte de relevância, que pula sem banco: medir onde há o que medir,
em vez de falhar por ausência de artefato.

Para rodar localmente, ver `api/README-vector.md`.

O que estes testes protegem é a coisa que **não dá erro quando quebra**: a
assimetria do e5. Um vetor gerado sem prefixo, ou com o prefixo errado, tem 768
dimensões, norma 1 e passa por qualquer verificação de forma — só entrega
resultado pior. Por isso as asserções aqui são sobre *ordenação semântica*, não
sobre a forma do vetor.
"""

from __future__ import annotations

import math

import pytest

from app.core.config import settings


@pytest.fixture(scope="module")
def embedder():
    from pathlib import Path

    if not Path(settings.embedding_model_dir).is_dir():
        pytest.skip(f"Pesos ausentes em {settings.embedding_model_dir} — ver README-vector.md")
    try:
        from app.search.embedding import DependenciaAusente, get_embedder
    except ImportError:  # pragma: no cover
        pytest.skip("extra `vector` não instalado")
    try:
        return get_embedder()
    except DependenciaAusente:
        pytest.skip("extra `vector` não instalado")


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_dimensao_e_768(embedder):
    """768 é a largura da coluna. Divergir aqui quebra a gravação, não o ranking."""
    assert len(embedder.embed_query("notebook gamer")) == 768


def test_vetor_sai_normalizado(embedder):
    """Norma 1 é o que torna `<=>` (cosseno) equivalente a produto interno."""
    vetor = embedder.embed_query("geladeira frost free")
    assert math.isclose(math.sqrt(sum(v * v for v in vetor)), 1.0, rel_tol=1e-4)


def test_consulta_aproxima_do_produto_certo(embedder):
    """O teste que justifica D3: casar necessidade com produto SEM termo comum.

    "para faculdade" não aparece no texto do notebook de estudo, e é justamente
    isso que o FTS não resolve — o caso que sobrou vermelho depois de D2.
    """
    certo = embedder.embed_products(
        ["Notebook Lenovo IdeaPad Slim 3 i3 8GB 256GB leve para estudo e trabalho do dia a dia"]
    )[0]
    errado = embedder.embed_products(
        ["Geladeira Brastemp Frost Free Duplex 375 litros inox com prateleiras ajustaveis"]
    )[0]
    consulta = embedder.embed_query("notebook para faculdade de engenharia")

    assert _cos(consulta, certo) > _cos(consulta, errado)


def test_prefixos_mudam_o_vetor(embedder):
    """Prova que a assimetria é real, e não decoração.

    Se consulta e produto produzissem o mesmo vetor para o mesmo texto, os
    prefixos seriam inócuos e a invariante 2 do módulo não teria motivo. Este
    teste é o que faz falhar quem "simplificar" removendo os prefixos.
    """
    texto = "notebook para edicao de video"
    como_consulta = embedder.embed_query(texto)
    como_produto = embedder.embed_products([texto])[0]

    assert _cos(como_consulta, como_produto) < 0.999


def test_carga_de_produto_e_deterministica(embedder):
    """O default da carga (`batch_size=1`) tem de dar sempre o mesmo vetor.

    É a garantia que sustenta o carimbo `_embedding`: se o vetor variasse entre
    execuções, "já vetorizado com este modelo" deixaria de significar algo.
    """
    a = embedder.embed_products(["Monitor Dell 27 polegadas IPS 4K"])[0]
    b = embedder.embed_products(["Monitor Dell 27 polegadas IPS 4K"])[0]

    # Igualdade elemento a elemento, e não cosseno ~1: somar 768 produtos em
    # float acumula erro suficiente para mascarar uma diferença real de vetor.
    assert a == b


def test_lote_maior_que_um_muda_o_vetor(embedder):
    """Documenta, em teste, por que `embed_products` usa lote de 1.

    A quantização int8 é dinâmica: a escala das ativações sai do tensor inteiro,
    isto é, do lote. O vetor de um produto passa então a depender de quem estava
    no lote ao lado — inclusive sem padding algum.

    Este teste **afirma o defeito**, não a ausência dele. Se algum dia o runtime
    passar a ser invariante ao lote, ele fica vermelho e avisa que o default de
    `batch_size=1` deixou de ser necessário.
    """
    sozinho = embedder.embed_products(["Monitor Dell 27 polegadas IPS 4K"])[0]
    em_lote = embedder.embed_products(
        [
            "Monitor Dell 27 polegadas IPS 4K",
            "Smart TV LG 55 polegadas 4K UHD ThinQ AI HDR10 para sala grande",
        ],
        batch_size=2,
    )[0]

    similaridade = _cos(sozinho, em_lote)
    # Perto, mas não igual: perto o bastante para não ser bug de pooling,
    # diferente o bastante para não gravar vetor dependente de vizinho.
    assert 0.95 < similaridade < 0.999


def test_model_id_vem_dos_pesos(embedder):
    """O carimbo dos vetores tem de refletir o que foi realmente carregado."""
    assert embedder.model_id
    assert isinstance(embedder.model_id, str)
