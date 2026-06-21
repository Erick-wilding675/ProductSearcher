# Arquitetura (resumo)

> Resumo para contexto rápido. Detalhe completo em `docs/architecture.md` e nos ADRs.

## Visão

```
[ Web App (Next.js) ]   [ Extensão Chrome ]
            \                 /
             \-- HTTP REST --/
                    |
        [ API FastAPI — monólito modular ]
        módulos: catalog | search | ai | core
                    |
           [ PostgreSQL (Supabase) ]
            FTS + pgvector + dados
                    ^
                    | escreve
          [ Worker de ingestão (seed) ]
```

IA é chamada pelo módulo `ai` **apenas quando habilitada**; o caminho crítico opera sem ela.

## Componentes

- **Web app / Extensão:** clientes da mesma API.
- **API (FastAPI):** endpoints, parsing de intenção, busca, ranking, comparação.
- **Worker:** pipeline de ingestão do seed.
- **PostgreSQL (Supabase):** persistência, FTS, pgvector.
- **AI Service:** explicações via LLM opcional, fallback determinístico.

## Contratos de interface (chave da evolução)

`IntentParser` · `SearchProvider` (FTS→OpenSearch) · `VectorProvider` (pgvector→Qdrant) · `RankingService` · `AIService` · `IngestionSource` (seed→APIFY/API).

## Endpoints (MVP)

`GET /health` · `GET /search` · `POST /compare` · `GET /products/{id}` · `GET /categories`.

## Decisões relacionadas

ADR-001 (dados), ADR-002 (Postgres-only), ADR-003 (monólito modular), ADR-004 (deploy free-tier).
