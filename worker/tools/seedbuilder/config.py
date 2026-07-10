"""Carrega o ``.env`` do worker para o seed-builder.

Chamado só nos entry points (CLI), nunca no import dos módulos — assim os testes
não herdam o ``DATABASE_URL``/tokens reais do ``.env``.
"""

from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def load_env() -> None:
    """Carrega o ``.env`` do worker sem sobrescrever variáveis já definidas."""
    load_dotenv(_ENV_PATH, override=False)
