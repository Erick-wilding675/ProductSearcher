"""Orquestra a ingestão: fetch -> normalize -> validate -> load (RF-70). TODO Fase 2."""

from pathlib import Path

from ingestion.load import load
from ingestion.normalize import normalize
from ingestion.sources import SeedIngestionSource
from ingestion.validate import validate

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


def run(seed_dir: Path = SEED_DIR) -> dict:
    source = SeedIngestionSource(seed_dir)
    raw = source.fetch()
    normalized = normalize(raw)
    valid, rejected = validate(normalized)
    report = load(valid)
    return {"loaded": report, "rejected": len(rejected)}


if __name__ == "__main__":
    print(run())
