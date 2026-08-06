"""CORS e correlação por requisição — o contrato HTTP que os dois clientes usam.

Cobre as entregas de CORS (web app + extensão) e de `X-Request-ID`, que não tinham
teste: ambas são configuração de middleware, o tipo de coisa que quebra em silêncio
e só aparece no browser.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_session
from app.main import app

WEB_APP = "http://localhost:3000"
EXTENSAO = "chrome-extension://abcdefghijklmnopqrstuvwxyz123456"


class _FakeSession:
    """`/health` só executa SELECT 1 — não precisa de Postgres para testar headers."""

    def execute(self, *args, **kwargs):
        return None


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_session] = _FakeSession
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_origem_do_web_app_e_permitida(client: TestClient) -> None:
    resp = client.get("/health", headers={"Origin": WEB_APP})
    assert resp.headers["access-control-allow-origin"] == WEB_APP


def test_origem_de_extensao_e_permitida_por_regex(client: TestClient) -> None:
    """O id da extensão muda a cada carga em dev, então a origem casa por regex."""
    resp = client.get("/health", headers={"Origin": EXTENSAO})
    assert resp.headers["access-control-allow-origin"] == EXTENSAO


def test_origem_desconhecida_nao_recebe_liberacao(client: TestClient) -> None:
    resp = client.get("/health", headers={"Origin": "https://site-qualquer.com"})
    assert "access-control-allow-origin" not in resp.headers


def test_request_id_e_exposto_ao_javascript(client: TestClient) -> None:
    """Regressão: sem `expose_headers`, o browser esconde o header do JS em
    resposta cross-origin e o cliente não consegue citar o id ao reportar erro."""
    resp = client.get("/health", headers={"Origin": WEB_APP})
    expostos = resp.headers.get("access-control-expose-headers", "")
    assert "X-Request-ID" in expostos


def test_request_id_e_gerado_quando_o_cliente_nao_manda(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.headers.get("X-Request-ID")


def test_request_id_do_cliente_e_preservado(client: TestClient) -> None:
    """Preservar o id recebido é o que permite correlacionar de ponta a ponta."""
    resp = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert resp.headers["X-Request-ID"] == "trace-123"


def test_cada_requisicao_recebe_um_id_distinto(client: TestClient) -> None:
    primeiro = client.get("/health").headers["X-Request-ID"]
    segundo = client.get("/health").headers["X-Request-ID"]
    assert primeiro != segundo
