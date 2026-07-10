"""Testes do OAuth do Mercado Livre (urlopen mockado — sem rede)."""

import io
import json

from tools.seedbuilder import ml_auth


def test_authorization_url():
    url = ml_auth.authorization_url("APPID", "https://cb.exemplo/callback")
    assert url.startswith(ml_auth.AUTH_URL)
    assert "response_type=code" in url
    assert "client_id=APPID" in url
    assert "redirect_uri=https%3A%2F%2Fcb.exemplo%2Fcallback" in url


def _fake_urlopen(payload: dict):
    body = json.dumps(payload).encode("utf-8")

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _open(request, timeout=20):
        assert request.data  # deve ser POST com corpo
        return _Resp(body)

    return _open


def test_exchange_code():
    tokens = ml_auth.exchange_code(
        "id",
        "sec",
        "TG-1",
        "cb",
        urlopen=_fake_urlopen({"access_token": "APP_USR-x", "refresh_token": "r-1"}),
    )
    assert tokens["access_token"] == "APP_USR-x"
    assert tokens["refresh_token"] == "r-1"


def test_refresh_access_token():
    tokens = ml_auth.refresh_access_token(
        "id", "sec", "r-1", urlopen=_fake_urlopen({"access_token": "APP_USR-y"})
    )
    assert tokens["access_token"] == "APP_USR-y"
