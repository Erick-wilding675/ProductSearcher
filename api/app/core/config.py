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

    # --- Busca vetorial (ADR-010 D3) -------------------------------------
    # Desligada por padrão, como toda IA aqui: com `false` a API não importa o
    # runtime de inferência nem carrega o modelo, e o FTS serve sozinho.
    vector_enabled: bool = False

    # Onde os pesos ONNX quantizados moram. A imagem de produção os embute neste
    # caminho (ver api/Dockerfile); em dev, aponte para um diretório exportado.
    embedding_model_dir: str = "/model"

    # Identidade do modelo, usada para carimbar os vetores dos produtos. É só
    # **fallback**: o valor real vem do arquivo `MODEL_ID` gravado junto aos
    # pesos no export. Ver `app/search/embedding.py`.
    embedding_model_id: str = "intfloat/multilingual-e5-base"

    # Threads de inferência. **Deixe em 1.** Medido no ADR-010 D3.3: em 1 vCPU,
    # o pool no default leva o p95 a 804 ms e fura a RNF-01 sozinho, porque o
    # runtime conta as CPUs que enxerga e não as que o cgroup concede. Só faz
    # sentido subir num host com vários vCPUs dedicados à API.
    embedding_threads: int = 1

    # Quantos vizinhos o retrieval vetorial devolve. Menor que o pool do FTS de
    # propósito: o HNSW devolve os mais próximos, e a cauda longa de "meio
    # parecido" é ruído que a fusão do D4 teria de descartar depois.
    vector_top_k: int = 50

    # Quantos candidatos o retrieval devolve para o ranking reordenar em memória
    # (ADR-0007). O que passar disso não entra no ranking nem na paginação, então o
    # pool precisa cobrir o catálogo: com ~170 produtos no seed, 200 não corta nada.
    # Gatilho de revisão: se o catálogo crescer, mover parte do ranking para o banco.
    search_candidate_pool: int = 200


settings = Settings()
