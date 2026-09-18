"""Configuração via variáveis de ambiente (sem segredos no repositório)."""

import json
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    #
    # `NoDecode` + validador: sem isso, o pydantic-settings exige **JSON** para uma
    # lista vinda do ambiente, e um `CORS_ORIGINS=["https://x"]` perde as aspas em
    # qualquer shell que as interprete (PowerShell, entre outros). O resultado é
    # `[https://x]`, que não é JSON — e a API morre no import, em loop de restart,
    # exibindo um erro de parsing que não diz nada sobre aspas. Aceitar também a
    # forma separada por vírgula tira essa armadilha do caminho de quem opera o
    # deploy, sem perder a compatibilidade com o formato JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    cors_origin_regex: str = r"^(chrome-extension|moz-extension)://[a-z0-9]+$"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, valor: object) -> object:
        """Aceita `["a","b"]` (JSON), `a,b` (vírgula) ou uma lista já pronta."""
        if not isinstance(valor, str):
            return valor
        texto = valor.strip()
        if texto.startswith("["):
            try:
                return json.loads(texto)
            except json.JSONDecodeError as erro:
                # Mensagem no lugar de um "Expecting value: line 1 column 2", que não
                # diz a ninguém que o problema são as aspas comidas pelo shell.
                raise ValueError(
                    "CORS_ORIGINS começa com '[' mas não é JSON válido — provavelmente o "
                    "shell removeu as aspas duplas. Use a forma separada por vírgula: "
                    "CORS_ORIGINS=https://a.exemplo,https://b.exemplo"
                ) from erro
        return [item.strip() for item in texto.split(",") if item.strip()]

    # Busca híbrida: união textual + vetorial fundida por RRF (ADR-010 D4).
    #
    # **Desligada por decisão, não por cautela genérica.** Medido em 22/08/2026
    # sobre a suíte de D1: só FTS dá precisão@5 de 68%; com a união, 64%. O braço
    # vetorial acerta a categoria e erra a spec, e D2 já resolveu a fome de
    # resultado que D4 foi escrito para atacar — nenhuma consulta volta vazia.
    #
    # Fica construída e desligada para o dia em que `searches` tiver consulta
    # real: a suíte tem 10 casos curados, e as consultas onde o vetorial
    # ajudaria (erro de digitação, sinônimo, formulação imprevista) são as que
    # ainda não existem. Ligar só com medição nova por cima.
    hybrid_enabled: bool = False

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
