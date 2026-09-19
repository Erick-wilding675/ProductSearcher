# worker: ingestão do catálogo

Pipeline reprodutível e idempotente:
**fetch, normalize, data quality, validate, load** (RF-70 a RF-72). Ver
[ADR-0001](../adr/0001-aquisicao-de-dados.md),
[ADR-0005](../adr/0005-decisoes-fase-2.md),
[ADR-0012](../adr/0012-qualidade-de-ofertas-na-ingestao.md) e
[`../docs/data-model.md`](../docs/data-model.md).

## Estrutura

```
ingestion/
  sources.py       IngestionSource (Protocol) e SeedIngestionSource
  models.py        RawProduct, NormalizedProduct, OfferRejection
  normalize.py     padroniza os registros brutos
  data_quality.py  classifica ofertas com preço implausível (ADR-0012)
  validate.py      cobra as specs obrigatórias declaradas por categoria
  schema.py        tabelas usadas pela carga
  load.py          upsert idempotente, ofertas, lojas e price_history
  pipeline.py      orquestra tudo e devolve o relatório de carga
seed/              dataset versionado (ver seed/README.md)
tools/             utilitários offline, fora do runtime (ver abaixo)
tests/
```

## Princípio

`IngestionSource` é **agnóstica à fonte**. Hoje existe `SeedIngestionSource`, que lê os
arquivos versionados; amanhã pode ser Apify ou uma API de marketplace, sem mudar quem
consome.

O pipeline **detecta, mas não inventa**. Registro que não passa na validação é rejeitado e
reportado; oferta com preço implausível é gravada com marca de qualidade, nunca corrigida
nem apagada. Corrigir dado automaticamente produziria um catálogo que nenhuma loja pratica.

## Rodar

```bash
# pela raiz, com o DATABASE_URL do ambiente
make seed

# ou direto
cd worker && python -m ingestion.pipeline

# ou pelo compose (profile jobs, roda sob demanda)
docker compose run --rm worker
```

O relatório de carga devolve, entre outros, `rejected` (registros descartados na
normalização e na validação) e `rejected_offers` (ofertas classificadas como suspeitas, que
continuam no banco).

> **Recarregar o seed apaga a rotulagem de `use_case`.** Os rótulos vivem em
> `product_specs.attributes`, que a carga sobrescreve. Depois de qualquer recarga, rode a
> re-rotulagem: ver [`../infra/deploy/supabase-sa-east-1.md`](../infra/deploy/supabase-sa-east-1.md).

## Ferramentas offline (`tools/`)

Não fazem parte do runtime e não são chamadas pela ingestão.

| Ferramenta | Para quê |
| --- | --- |
| [`tools/seedbuilder/`](tools/seedbuilder/README.md) | Gera o dataset seed a partir do CSV do Apify, com enriquecimento pela API do Mercado Livre e parser de título como fallback |
| `tools/seedbuilder/label_use_cases.py` | Rotula `use_case` por LLM, offline (ADR-0010 D2) |
| `tools/cleanup_orphans.py` | Remove produtos que o seed atual não produz mais. Existe porque o ADR-0009 mudou a chave natural, e o upsert por slug deixou as linhas antigas ao lado das novas. Rode com `--dry-run` primeiro |
| `tools/search_insights.py` | Lê a tabela `searches` e mostra o que volta vazio e o que o `IntentParser` não entende. É a única régua externa contra a suíte de relevância, que é calibrada pela nossa imaginação |

## Testes

```bash
cd worker && pytest -q
```

A suíte roda sem banco, com exceção de `test_load.py` (idempotência do upsert), que exige o
schema aplicado e se pula sozinho quando não há banco.
