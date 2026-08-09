"""Autenticação OAuth do Mercado Livre para o seed-builder (offline).

Os segredos vêm de variáveis de ambiente (nunca versionados):
``ML_CLIENT_ID``, ``ML_CLIENT_SECRET``, ``ML_REDIRECT_URI`` e — após o 1º login —
``ML_REFRESH_TOKEN``.

Dois caminhos:

* **client_credentials** (mais simples, sem navegador): ``token`` — funciona se o app
  tiver o fluxo *Client Credentials* habilitado e o recurso permitir token de app.
* **authorization_code** (login do usuário):
  1. ``url``      → abra, autorize, copie o ``code=TG-...`` da URL de retorno.
  2. ``exchange --code TG-...``  → imprime ``access_token`` (~6h) e ``refresh_token``.
  3. ``refresh``  → renova o access token via ``ML_REFRESH_TOKEN``.

Em todos os casos: ``export ML_ACCESS_TOKEN=<access_token>`` e rode o ``build_seed``.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable

AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


def authorization_url(client_id: str, redirect_uri: str) -> str:
    """URL para o usuário autorizar o app e receber o ``code``."""
    query = urllib.parse.urlencode(
        {"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri}
    )
    return f"{AUTH_URL}?{query}"


def _post_token(data: dict, *, urlopen: Callable = urllib.request.urlopen) -> dict:
    request = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(data).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def client_credentials_token(
    client_id: str, client_secret: str, *, urlopen: Callable = urllib.request.urlopen
) -> dict:
    """Token de app (client_credentials) — sem navegador nem redirect."""
    return _post_token(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        urlopen=urlopen,
    )


def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    *,
    urlopen: Callable = urllib.request.urlopen,
) -> dict:
    """Troca o ``code`` (authorization_code) por ``access_token`` + ``refresh_token``."""
    return _post_token(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        urlopen=urlopen,
    )


def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    urlopen: Callable = urllib.request.urlopen,
) -> dict:
    """Gera um novo ``access_token`` a partir do ``refresh_token``."""
    return _post_token(
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        urlopen=urlopen,
    )


def access_token_from_env(*, urlopen: Callable = urllib.request.urlopen) -> str:
    """Devolve um access token, sem exigir passo manual.

    Ordem: ``ML_ACCESS_TOKEN`` explícito → **client_credentials** → refresh token.

    O `client_credentials` no meio é o que faz diferença: ele resolve sozinho,
    sem navegador e sem redirect (token de 6h), e cobre tudo que o enriquecimento
    precisa (`/products`, `/products/{id}/items`, `/users`). O fluxo
    `authorization_code` continua existindo para o dia em que for preciso um
    recurso de usuário — hoje, não é.
    """
    token = (os.environ.get("ML_ACCESS_TOKEN") or "").strip()
    if token:
        return token

    client_id = _env("ML_CLIENT_ID")
    client_secret = _env("ML_CLIENT_SECRET")
    try:
        return client_credentials_token(client_id, client_secret, urlopen=urlopen)["access_token"]
    except Exception as exc:  # noqa: BLE001
        refresh = (os.environ.get("ML_REFRESH_TOKEN") or "").strip()
        if not refresh:
            raise RuntimeError(
                "Não foi possível obter um token do ML. Defina ML_ACCESS_TOKEN ou "
                "confira ML_CLIENT_ID/ML_CLIENT_SECRET."
            ) from exc
        return refresh_access_token(client_id, client_secret, refresh, urlopen=urlopen)[
            "access_token"
        ]


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Defina a variável de ambiente {name}.")
    return value


def main(argv: list[str] | None = None) -> None:
    from tools.seedbuilder.config import load_env

    load_env()
    parser = argparse.ArgumentParser(description="OAuth do Mercado Livre (seed-builder).")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("token", help="Token de app (client_credentials).")
    sub.add_parser("url", help="Imprime a URL de autorização.")
    exchange = sub.add_parser("exchange", help="Troca o code por tokens.")
    exchange.add_argument("--code", required=True)
    sub.add_parser("refresh", help="Renova o access token via refresh token.")
    args = parser.parse_args(argv)

    if args.command == "token":
        tokens = client_credentials_token(_env("ML_CLIENT_ID"), _env("ML_CLIENT_SECRET"))
        print(json.dumps(tokens, indent=2, ensure_ascii=False))
    elif args.command == "url":
        print(authorization_url(_env("ML_CLIENT_ID"), _env("ML_REDIRECT_URI")))
    elif args.command == "exchange":
        tokens = exchange_code(
            _env("ML_CLIENT_ID"), _env("ML_CLIENT_SECRET"), args.code, _env("ML_REDIRECT_URI")
        )
        print(json.dumps(tokens, indent=2, ensure_ascii=False))
    elif args.command == "refresh":
        tokens = refresh_access_token(
            _env("ML_CLIENT_ID"), _env("ML_CLIENT_SECRET"), _env("ML_REFRESH_TOKEN")
        )
        print(json.dumps(tokens, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
