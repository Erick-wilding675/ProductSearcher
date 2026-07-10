"""Fontes de ingestão — interface agnóstica à fonte (ADR-0001).

MVP: SeedIngestionSource (YAML versionado). Futuro: APIFY/APIs sob a mesma interface.
"""

import logging
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml
from pydantic import ValidationError

from ingestion.models import RawProduct

logger = logging.getLogger(__name__)


@runtime_checkable
class IngestionSource(Protocol):
    """Contrato agnóstico à fonte: seed, APIFY, APIs — todas cabem aqui."""

    def fetch(self) -> Iterable[RawProduct]:
        """Produz os produtos crus da fonte, um a um."""
        ...


class SeedIngestionSource:
    """Lê produtos crus do dataset seed em YAML (ADR-005 D5)."""

    def __init__(self, seed_dir: Path) -> None:
        self._seed_dir = seed_dir

    def fetch(self) -> Iterator[RawProduct]:
        products_dir = self._seed_dir / "products"
        if not products_dir.exists():
            logger.warning("Diretório de produtos do seed não encontrado: %s", products_dir)
            return
        for path in sorted(products_dir.glob("*.y*ml")):  # .yaml e .yml
            records = yaml.safe_load(path.read_text(encoding="utf-8")) or []
            for record in records:
                try:
                    yield RawProduct.model_validate(record)
                except ValidationError as exc:
                    # Registro estruturalmente inválido: loga e segue (não derruba o lote).
                    logger.warning("Registro cru inválido em %s, pulando: %s", path.name, exc)
