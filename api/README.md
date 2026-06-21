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
