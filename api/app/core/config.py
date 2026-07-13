"""Configuração via variáveis de ambiente (sem segredos no repositório)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/productsearcher"
    # IA é complementar (princípio do projeto): desligada por padrão.
    ai_enabled: bool = False

    # CORS. Dois clientes consomem a API (ADR-0003): o web app e a extensão de browser.
    # - `cors_origins`: origens web explícitas (dev + prod), separadas por vírgula na env.
    # - `cors_origin_regex`: casa as origens de extensão, cujo id não é fixo em dev.
    #   Extensões expõem origem `chrome-extension://<id>` (ou `moz-extension://<id>`),
    #   que não dá para listar item a item — por isso um regex.
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_origin_regex: str = r"^(chrome-extension|moz-extension)://[a-z0-9]+$"


settings = Settings()
