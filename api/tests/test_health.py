"""Testes do GET /health (status do app + do banco).

A sessão é substituída por um fake, então testamos os dois caminhos
(banco ok / banco fora) sem precisar de um Postgres real.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_session
from app.main import app


class _FakeSession:
    def __init__(self, *, db_ok: bool) -> None:
        self._db_ok = db_ok

    def execute(self, *args, **kwargs):
        if not self._db_ok:
            raise SQLAlchemyError("banco indisponível")
        return None


def _client(*, db_ok: bool) -> TestClient:
    app.dependency_overrides[get_session] = lambda: _FakeSession(db_ok=db_ok)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _limpa_overrides():
    yield
    app.dependency_overrides.clear()


def test_health_com_banco_ok():
    resp = _client(db_ok=True).get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


def test_health_com_banco_fora():
    resp = _client(db_ok=False).get("/health")

    assert resp.status_code == 200  # sempre 200 (liveness); só o campo `db` muda
    assert resp.json()["db"] == "down"
