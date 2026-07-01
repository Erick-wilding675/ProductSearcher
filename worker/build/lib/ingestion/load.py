"""Persistência idempotente (upsert) no Postgres (RF-72). TODO Fase 2.

Rodar duas vezes não deve duplicar produtos/ofertas.
"""


def load(records: list[dict]) -> dict:
    """Faz upsert dos registros válidos. Retorna um relatório de carga."""
    raise NotImplementedError
