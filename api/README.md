# api: backend FastAPI (monólito modular)

Ver [`../docs/architecture.md`](../docs/architecture.md) e
[ADR-0003](../adr/0003-monolito-modular.md).

## Estrutura

```
app/
  main.py          entrypoint, CORS, correlação por requisição, GET /health
  core/
    config.py      Settings por variável de ambiente, com as flags de IA
    db.py          engine e sessão (pooler de transação, prepare_threshold=None)
    logging.py     logging estruturado com X-Request-ID
  catalog/
    tables.py      definição das tabelas
    repository.py  leitura de categorias, marcas, produto e comparação
    router.py      GET /categories, /brands, /products/{id}
  search/
    intent.py      RuleBasedIntentParser (categoria, preço, atributos, use_case)
    providers.py   FtsSearchProvider, PgVectorProvider, HybridSearchProvider
    ranking.py     RankingService determinístico e os pesos
    comparison.py  alinhamento de specs e marcação de diferenças
    log.py         escrita em searches, tolerante a falha
    embedding.py   embedder ONNX (só carrega com vector_enabled)
    vector_load.py carga offline dos vetores dos produtos
    router.py      GET /search, GET /spec-options, POST /compare
  ai/
    service.py     AIService: DeterministicAIService e o desenho do LLMAIService
alembic/           migrations
tests/             testes
```

## Princípios

- Módulos com fronteiras claras. Dependências externas ficam atrás de `Protocol`, o que
  permite trocar implementação sem tocar em quem consome.
- IA é opcional: a API sobe e serve tudo com `AI_ENABLED=false`, que é o padrão.
- Nenhum endpoint chama modelo. O que existe de IA no runtime está atrás de flag desligada.

## Configuração

Todas as opções vêm de variável de ambiente, com default no `app/core/config.py`. Ver
[`.env.example`](.env.example). As que mais importam:

| Variável | Default | Observação |
| --- | --- | --- |
| `DATABASE_URL` | Postgres do compose | Em produção, pooler de transação (6543) |
| `CORS_ORIGINS` | `http://localhost:3000` | Origens exatas, separadas por vírgula ou em JSON. Curinga não funciona: o middleware compara string |
| `CORS_ORIGIN_REGEX` | `^(chrome-extension\|moz-extension)://[a-z0-9]+$` | Serve às extensões, cujo id não é fixo em dev |
| `AI_ENABLED` | `false` | |
| `VECTOR_ENABLED` | `false` | Ligado, importa o runtime de inferência e carrega o modelo |
| `HYBRID_ENABLED` | `false` | União FTS mais vetorial por RRF |
| `SEARCH_CANDIDATE_POOL` | `200` | Candidatos que o retrieval devolve para o ranking reordenar |
| `EMBEDDING_THREADS` | `1` | **Deixe em 1.** Com o pool no default, em 1 vCPU, o p95 vai a 804 ms e fura a RNF-01 sozinho |

## Rodar em dev

```bash
# pela raiz do repo, com banco no compose
docker compose up -d db
export DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/productsearcher'
make migrate && make seed
docker compose up -d api

# ou direto, contra o DATABASE_URL do .env
uvicorn app.main:app --reload --port 8000 --app-dir api
```

> **Exporte a `DATABASE_URL` antes de `make migrate` e `make seed`.** Sem ela, o Alembic
> lê `api/.env` e a ingestão lê `worker/.env`, que numa máquina que já operou produção
> apontam para o **Supabase**. O comando que parece preparar o banco local aplica DDL e
> recarrega o catálogo em produção, sem confirmar nada. A variável exportada vence os dois
> `.env`, e isso foi verificado nos dois caminhos.

> Já existe um Postgres na 5432? Use `DB_PORT=5433 docker compose up -d db api` e aponte a
> `DATABASE_URL` para essa porta. Sem isso o cliente fala com o Postgres do host, não com o
> do compose.

> O serviço `api` do compose aponta para o Postgres do próprio compose e **ignora** o
> `DATABASE_URL` do `.env`. Misturar as duas formas é a maneira mais fácil de acabar com
> uma API conectada a um banco vazio.

## Testes

`pytest -q` roda a suíte inteira sem depender de banco: ela usa fakes e SQL compilado.

Duas exceções, que se **pulam** em vez de falhar em falso quando o ambiente não as suporta:

| Suíte | Exige | Comportamento sem o requisito |
| --- | --- | --- |
| `tests/test_relevance.py` | Postgres com o seed carregado | Pulada. Mede o KPI de relevância top-5 do PRD |
| `tests/test_embedding_real.py` | Pesos ONNX presentes | Pulada. Ver [`README-vector.md`](README-vector.md) |

Para exercitar o KPI de verdade:

```bash
docker compose up -d db                      # ou DB_PORT=5433 docker compose up -d db
export DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/productsearcher'
cd api    && alembic upgrade head            # cria o schema
cd worker && python -m ingestion.pipeline    # carrega o seed
cd api    && pytest -q                       # agora a relevância roda
```

A mesma exportação vale aqui, e por um motivo a mais: **`pytest` também lê `api/.env`**.
Sem a variável, a suíte de relevância mede o catálogo de produção em vez do local.

Ao trocar o seed, recalibre os casos de `test_relevance.py`. Um produto esperado que saiu
do catálogo derruba o KPI sem que a busca tenha piorado.

## Migrations

```bash
cd api && alembic upgrade head
```

O DDL exige o **pooler de sessão (porta 5432)**, não o de transação. Migrations **não**
rodam no deploy (ADR-0011 D7): são passo manual, executado antes do deploy do código que
depende delas.

Senha do banco com `%` quebra duas vezes, no `configparser` do `alembic.ini` e como escape
percentual na URL. O `env.py` já escapa o `%`, e o `.env.example` recomenda senha
alfanumérica.

## Busca vetorial

Desligada por padrão e documentada à parte, em [`README-vector.md`](README-vector.md):
imagem `:vector`, carga offline dos vetores, carimbo de modelo e a nota sobre threads.
