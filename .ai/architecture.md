# Arquitetura (resumo)

> Resumo para contexto rápido. Detalhe completo em [`docs/architecture.md`](../docs/architecture.md)
> e nos ADRs.

## Visão

```
[ Web app (Next.js, Vercel) ]   [ Extensão Chrome MV3 ]
              \                        /
               \------ HTTP REST -----/
                          |
          [ API FastAPI, monólito modular, Fly.io gru ]
          módulos: catalog | search | ai | core
                          |
             [ PostgreSQL, Supabase sa-east-1 ]
              FTS com unaccent + pgvector
                          ^
                          | escreve
              [ Worker de ingestão (seed) ]
```

O caminho crítico opera sem modelo. O embedder existe e está desligado por flag
(`vector_enabled=false`), por medição registrada no ADR-0010 D4.

## Componentes

- **Web app e extensão:** clientes da mesma API. A extensão decide cobertura localmente e
  envia apenas o `q` da SERP.
- **API:** endpoints, parsing de intenção, retrieval, ranking, comparação, log de buscas.
- **Worker:** pipeline de ingestão do seed, com triagem de qualidade de ofertas.
- **PostgreSQL:** persistência, FTS, pgvector.
- **AI Service:** explicação determinística. O provider de LLM tem o desenho fechado e foi
  recusado por medição (ADR-0010 D6.1).

## Contratos de interface

`IntentParser` · `SearchProvider` (FTS, com híbrido construído e desligado) ·
`VectorProvider` (pgvector, desligado) · `RankingService` · `AIService` · `IngestionSource`
(seed, evoluindo para Apify ou APIs).

## Endpoints

`GET /health` · `GET /search` · `GET /spec-options` · `POST /compare` ·
`GET /products/{id}` · `GET /categories` · `GET /brands`.

Parâmetros de `/search`: `q`, `category`, `price_max`, `brand`, `attrs` (objeto JSON),
`rank_by` (`relevance` | `price` | `brand` | `spec`), `rank_brand`, `rank_spec`,
`rank_spec_value`, `sort`, `page`. Preferência de ranking reordena, não filtra.

Pesos do ranking: `relevance` 0.6, `price` 0.3, `attributes` 0.1, `preference` 2.0. O peso
da preferência é maior que a soma dos demais de propósito, para que um item pedido
explicitamente vença mesmo perdendo em todo o resto.

## Decisões relacionadas

ADR-0002 (Postgres-only) · ADR-0003 (monólito modular) · ADR-0007 (pipeline de busca) ·
ADR-0010 (onde a IA entra) · ADR-0011 (deploy de produção) · ADR-0012 (qualidade de
ofertas).
