# api/ — Backend (FastAPI, monólito modular)

Ver [`../docs/architecture.md`](../docs/architecture.md) e [ADR-0003](../adr/0003-monolito-modular.md).

## Estrutura

```
app/
  main.py        # entrypoint + GET /health
  core/          # config, db, logging
  catalog/       # produtos, categorias, specs, ofertas (módulo de dados)
  search/        # intent parser, providers (FTS/vetorial), ranking
  ai/            # AIService (opcional, plugável)
tests/           # testes
```

## Princípios

- Módulos com fronteiras claras; dependências externas **atrás de interfaces** (Protocols).
- IA é **opcional**: a API funciona com `AI_ENABLED=false`.

## Rodar (dev)

- Via raiz do repo: `docker compose up`.
- Local: dentro de `api/`, `uvicorn app.main:app --reload`.

> Já tem um Postgres na 5432? Suba com `DB_PORT=5433 docker compose up` e aponte a
> `DATABASE_URL` para essa porta — sem isso o cliente fala com o Postgres do host.

## Testes

`pytest -q` roda tudo sem depender de banco: a suíte usa fakes e SQL compilado.

A exceção é `tests/test_relevance.py`, que mede o **KPI de relevância top-5** (PRD §5)
e por isso exige Postgres **com o seed carregado** — sem banco ou com catálogo vazio
ela é pulada, nunca falha em falso:

```bash
docker compose up -d db                      # ou DB_PORT=5433 docker compose up -d db
cd api    && alembic upgrade head            # cria o schema
cd worker && python -m ingestion.pipeline    # carrega o seed
cd api    && pytest -q                       # agora a relevância roda de verdade
```

Ao trocar o seed, recalibre os casos de `test_relevance.py`: um produto esperado que
saiu do catálogo derruba o KPI sem que a busca tenha piorado.
