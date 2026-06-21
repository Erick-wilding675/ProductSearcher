"""Fontes de ingestão — interface agnóstica à fonte (ADR-0001).

MVP: SeedSource (arquivos versionados). Futuro: APIFY/APIs sob a mesma interface.
"""
from pathlib import Path
from typing import Protocol


class IngestionSource(Protocol):
    def fetch(self) -> list[dict]: ...


class SeedSource:
    """Lê registros raw do dataset seed versionado. TODO Fase 2."""

    def __init__(self, seed_dir: Path) -> None:
        self.seed_dir = seed_dir

    def fetch(self) -> list[dict]:
        raise NotImplementedError
