"""Verifica a conexão com o banco lendo DATABASE_URL do .env da raiz.

Uso (com o .venv ativo, a partir da raiz do projeto):
    python infra/check_db.py

Não imprime a senha. Sai com código 0 se a conexão funcionar.
"""

from __future__ import annotations

import sys
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def read_database_url() -> str:
    if not ENV_FILE.exists():
        sys.exit(f"Arquivo não encontrado: {ENV_FILE}")
    # utf-8-sig remove eventual BOM no início do arquivo.
    for raw_line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "DATABASE_URL":
            # remove aspas acidentais ao redor do valor
            return value.strip().strip('"').strip("'")
    sys.exit("DATABASE_URL não encontrado no .env")


def main() -> None:
    url = read_database_url()
    # psycopg conecta com o esquema postgresql:// (o +psycopg é só para o SQLAlchemy).
    dsn = url.replace("+psycopg", "")
    if not dsn.startswith(("postgresql://", "postgres://")):
        sys.exit(f"DATABASE_URL não parece uma URL Postgres válida: começa com {dsn[:15]!r}")

    import psycopg

    try:
        with psycopg.connect(dsn, connect_timeout=10) as conn:
            version = conn.execute("select version()").fetchone()[0]
            has_vector = conn.execute(
                "select count(*) from pg_extension where extname = 'vector'"
            ).fetchone()[0]
    except Exception as exc:  # noqa: BLE001 - script de diagnóstico
        sys.exit(f"Falha ao conectar: {type(exc).__name__}: {exc}")

    print("Conexão OK ->", version[:60])
    print("pgvector habilitado:", "sim" if has_vector else "NÃO")


if __name__ == "__main__":
    main()
