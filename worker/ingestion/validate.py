"""Validação de specs obrigatórias por categoria (RF-71). TODO Fase 2.

Valida cada produto contra o `category_attribute_schema`. Produtos inválidos são
rejeitados/sinalizados (não entram no catálogo).
"""


def validate(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Retorna (válidos, rejeitados)."""
    raise NotImplementedError
