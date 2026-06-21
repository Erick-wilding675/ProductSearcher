# worker/ — Ingestão do catálogo (seed)

Pipeline reprodutível: **raw → normalização → validação → upsert idempotente**.
Ver [ADR-0001](../adr/0001-aquisicao-de-dados.md) e [`../docs/data-model.md`](../docs/data-model.md).

## Estrutura

```
ingestion/
  sources.py    # IngestionSource (interface) + SeedSource (lê arquivos versionados)
  normalize.py  # padroniza registros raw
  validate.py   # valida specs obrigatórias por categoria
  load.py       # upsert idempotente no Postgres
  pipeline.py   # orquestra fetch -> normalize -> validate -> load
seed/           # dados seed versionados (ver seed/README.md)
```

## Princípio

`IngestionSource` é **agnóstica à fonte**: hoje `SeedSource`; no futuro APIFY/APIs (ADR-0001) sem mudar o consumo.

## Rodar (dev)

`python -m ingestion.pipeline` (ou via serviço `worker` no docker compose).
