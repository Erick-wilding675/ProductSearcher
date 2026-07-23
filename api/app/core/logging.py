"""Logging estruturado com correlação por requisição (RNF-05).

Cada log sai em JSON com um `request_id`, para amarrar todas as linhas de uma mesma
requisição (correlação em ferramentas de observabilidade). O id vem do header
`X-Request-ID` (se o cliente/proxy mandar) ou é gerado; o middleware em `main.py`
o injeta no contexto e o devolve no header da resposta.

Sem dependências externas: usa `contextvars` (seguro sob concorrência do ASGI) +
um `logging.Filter`.
"""

import logging
from contextvars import ContextVar
from uuid import uuid4

# "-" quando não há requisição no contexto (ex.: logs de startup).
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(value: str | None = None) -> str:
    """Fixa o request id do contexto atual (gera um se não vier). Devolve o id usado."""
    rid = value or uuid4().hex
    _request_id.set(rid)
    return rid


def get_request_id() -> str:
    """Request id do contexto atual ('-' fora de uma requisição)."""
    return _request_id.get()


class RequestIdFilter(logging.Filter):
    """Injeta `request_id` em todo LogRecord, para o formatter poder usá-lo."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging() -> None:
    """Configura o root logger: saída JSON de uma linha, com `request_id`."""
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter(
            '{"level":"%(levelname)s","logger":"%(name)s",'
            '"request_id":"%(request_id)s","msg":"%(message)s"}'
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
