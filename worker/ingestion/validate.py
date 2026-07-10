"""Validação de specs por categoria (RF-71, ADR-0005 D4/D6).

`validate_specs` é a regra unitária (required/tipo/enum). `validate` particiona um
lote em (válidos, rejeitados) contra o schema de cada categoria, aplicando a
política "rejeita, loga e segue" (D6). `read_categories` carrega o seed de
categorias (`categories.json`).
"""

import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ingestion.models import AttributeSpec, Category, NormalizedProduct, Rejection

logger = logging.getLogger(__name__)


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
        return isinstance(value, int | float) and not isinstance(value, bool)
    if spec.data_type == "boolean":
        return isinstance(value, bool)
    if spec.data_type == "enum":
        return value in (spec.allowed_values or [])
    return False


def read_categories(seed_dir: Path) -> list[Category]:
    """Lê `categories.json` do seed → lista de `Category` (slug, name, attributes)."""
    path = seed_dir / "categories.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Category.model_validate(item) for item in data]


def validate(
    products: Iterable[NormalizedProduct],
    schemas: dict[str, list[AttributeSpec]],
) -> tuple[list[NormalizedProduct], list[Rejection]]:
    """Particiona os produtos em (válidos, rejeitados) contra o schema por categoria."""
    valid: list[NormalizedProduct] = []
    rejected: list[Rejection] = []

    for product in products:
        schema = schemas.get(product.category_slug)
        if schema is None:
            reason = f"categoria desconhecida: {product.category_slug}"
            logger.warning("Produto rejeitado (%s): %s", product.name, reason)
            rejected.append(Rejection(name=product.name, reasons=[reason]))
            continue

        errors = validate_specs(product.specs, schema)
        if errors:
            logger.warning("Produto rejeitado (%s): %s", product.name, "; ".join(errors))
            rejected.append(Rejection(name=product.name, reasons=errors))
            continue

        valid.append(product)

    return valid, rejected
