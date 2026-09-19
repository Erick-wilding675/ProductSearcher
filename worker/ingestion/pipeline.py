"""Orquestra a ingestão ponta a ponta (RF-70):
fetch → normalize → data quality → validate → load.

A URL do banco vem de ``DATABASE_URL`` (mesma convenção do Alembic/env.py);
em dev com o docker compose o padrão já aponta para o serviço ``db``.
"""

import logging
import os
from pathlib import Path

import sqlalchemy as sa

from ingestion.data_quality import detect_price_outliers
from ingestion.load import load
from ingestion.normalize import normalize
from ingestion.sources import SeedIngestionSource
from ingestion.validate import read_categories, validate

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@db:5432/productsearcher"


def run(
    seed_dir: Path = SEED_DIR,
    database_url: str | None = None,
) -> dict:
    """Executa o pipeline e devolve um relatório de carga."""

    database_url = database_url or os.environ.get(
        "DATABASE_URL",
        DEFAULT_DATABASE_URL,
    )

    categories = read_categories(seed_dir)
    schemas = {category.slug: category.attributes for category in categories}

    raw = SeedIngestionSource(seed_dir).fetch()

    normalized, rejected_norm = normalize(raw)

    checked, rejected_prices = detect_price_outliers(normalized)

    valid, rejected_specs = validate(checked, schemas)

    engine = sa.create_engine(database_url, future=True)

    try:
        with engine.begin() as conn:
            report = load(
                conn,
                valid,
                categories,
                rejected_prices,
            )
    finally:
        engine.dispose()

    report["rejected"] = len(rejected_norm) + len(rejected_specs)

    report["rejected_offers"] = len(rejected_prices)

    logger.info(
        "Ingestão concluída: %s",
        report,
    )

    return report


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(
        Path(__file__).resolve().parents[1] / ".env",
        override=False,
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    print(run())
