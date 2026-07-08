"""Validação de specs obrigatórias por categoria (RF-71). TODO Fase 2.

Valida cada produto contra o `category_attribute_schema`. Produtos inválidos são
rejeitados/sinalizados (não entram no catálogo).
"""
from typing import Any

from ingestion.models import AttributeSpec


def validate_specs(attributes: dict[str, Any], schema: list[AttributeSpec]) -> list[str]:
    """Valida os specs de um produto contra o schema da categoria.

    Retorna a lista de motivos de rejeição (lista vazia = válido).
    """
    errors: list[str] = []
    by_key = {spec.attribute_key: spec for spec in schema}

    # 1) required presentes
    for spec in schema:
        if spec.required and spec.attribute_key not in attributes:
            errors.append(f"atributo obrigatório ausente: {spec.attribute_key}")

    # 2) tipo compatível + 3) enum dentro da lista (para os atributos presentes)
    for key, value in attributes.items():
        spec = by_key.get(key)
        if spec is None:
            continue  # atributo que o schema não conhece: ignora
        if not _tipo_ok(spec, value):
            errors.append(f"tipo incompatível em '{key}': esperado {spec.data_type}")

    return errors


def _tipo_ok(spec: AttributeSpec, value: Any) -> bool:
    if spec.data_type == "text":
        return isinstance(value, str)
    if spec.data_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if spec.data_type == "boolean":
        return isinstance(value, bool)
    if spec.data_type == "enum":
        return value in (spec.allowed_values or [])
    return False


def validate(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Retorna (válidos, rejeitados)."""
    raise NotImplementedError
