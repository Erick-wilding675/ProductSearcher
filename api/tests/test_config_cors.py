"""CORS_ORIGINS vindo do ambiente: JSON, vírgula e o caso que derrubou o 1º deploy.

O formato JSON é o que o pydantic-settings espera por padrão para uma lista, mas ele
não sobrevive a um shell que interpreta aspas duplas — foi assim que a API entrou em
loop de restart no Fly, com `CORS_ORIGINS=[http://localhost:3000]` chegando ao
container. Estes testes travam os dois formatos aceitos.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_aceita_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example","https://b.example"]')
    assert Settings().cors_origins == ["https://a.example", "https://b.example"]


def test_aceita_separado_por_virgula(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert Settings().cors_origins == ["https://a.example", "https://b.example"]


def test_aceita_uma_origem_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://productsearcher.vercel.app")
    assert Settings().cors_origins == ["https://productsearcher.vercel.app"]


def test_json_sem_aspas_falha_dizendo_o_que_fazer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`[a,b]` continua inválido, mas o erro passa a apontar a saída."""
    monkeypatch.setenv("CORS_ORIGINS", "[http://localhost:3000]")
    with pytest.raises(ValidationError, match="shell removeu as aspas"):
        Settings()
