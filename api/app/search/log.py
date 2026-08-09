"""Registro das consultas de busca (tabela `searches`).

Para que serve: a tabela existia no schema desde a Fase 2 e **nada escrevia
nela**. Ela é a única fonte que responde perguntas de produto que o código não
responde — quais buscas voltam vazias, quais termos o `IntentParser` não
reconhece, quais categorias o usuário procura e o catálogo não cobre. É também o
insumo para recalibrar o KPI de relevância com consulta real em vez de lista fixa.

Duas regras de projeto aqui:

1. **Registrar nunca pode derrubar a busca.** Qualquer falha ao gravar é engolida
   e logada. Analytics é secundário; a resposta ao usuário não é.
2. **Fica atrás de uma interface.** `NullSearchLog` desliga o registro sem tocar
   no `SearchService` — é o que os testes usam e o que permite desligar em
   produção se o volume incomodar.

Privacidade: gravamos o texto da consulta, sem identificação de usuário — não há
`users` no MVP, nem IP, nem sessão. Ver `docs/data-model.md`.
"""

import logging
from typing import Annotated, Any, Protocol
from uuid import uuid4

from fastapi import Depends
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.catalog.tables import searches
from app.core.db import get_session
from app.search.intent import Intent

logger = logging.getLogger(__name__)


class SearchLog(Protocol):
    def record(self, query: str, intent: Intent, result_count: int) -> None: ...


class NullSearchLog:
    """Não registra nada. Default seguro para teste e para uso sem banco."""

    def record(self, query: str, intent: Intent, result_count: int) -> None:
        return None


class SqlSearchLog:
    """Grava em `searches`. Falha em silêncio — a busca vem primeiro."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, query: str, intent: Intent, result_count: int) -> None:
        if not query or not query.strip():
            return  # busca só por filtros: não há texto que valha registrar

        try:
            self._session.execute(
                insert(searches).values(
                    id=uuid4(),
                    query_text=query.strip(),
                    parsed_intent=_intent_para_json(intent),
                    result_count=result_count,
                )
            )
            # A sessão da request é read-only no resto do fluxo; sem o commit
            # explícito o registro morreria no rollback do fim da request.
            self._session.commit()
        except Exception:  # noqa: BLE001
            logger.warning("Falha ao registrar a busca (ignorado)", exc_info=True)
            try:
                self._session.rollback()
            except Exception:  # noqa: BLE001
                pass


def get_search_log(session: Annotated[Session, Depends(get_session)]) -> SearchLog:
    """Dependency do FastAPI: registro em banco, uma sessão por request."""
    return SqlSearchLog(session)


def _intent_para_json(intent: Intent) -> dict[str, Any]:
    """O que o parser extraiu — é isto que diz se ele entendeu a consulta."""
    return {
        "category": intent.category,
        "price_max": intent.price_max,
        "attributes": intent.attributes or {},
        "text": intent.text,
    }
