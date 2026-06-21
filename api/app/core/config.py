"""Configuração via variáveis de ambiente (sem segredos no repositório)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/productsearcher"
    # IA é complementar (princípio do projeto): desligada por padrão.
    ai_enabled: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
