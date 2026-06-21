# ProductSearcher

Plataforma inteligente de **descoberta, comparação e análise de produtos**. Projeto de portfólio de engenharia (arquitetura moderna, dados, IA aplicada, DevOps), executável em **free-tier**.

> IA é complementar: o sistema funciona sem qualquer LLM. Ver [`.ai/ai.md`](.ai/ai.md).

## Monorepo

```
api/         # Backend FastAPI (monólito modular: catalog | search | ai | core)
worker/      # Ingestão do catálogo seed (raw → normalização → validação → upsert)
frontend/    # Web App (Next.js + Tailwind, tokens violet, light/dark)
infra/       # Notas de infraestrutura e deploy
docs/        # Documentação viva (PRD, arquitetura, design, casos de uso, dados)
adr/         # Architecture Decision Records
.ai/         # Contexto para agentes de IA
```

## Começar (dev)

Pré-requisito: Docker.

```bash
cp .env.example .env
docker compose up            # sobe db (pgvector) + api
docker compose run --rm worker   # roda a ingestão do seed (quando implementada)
# Frontend:
cd frontend && npm install && npm run dev
```

- API: http://localhost:8000 (`/health`)
- Web: http://localhost:3000

## Documentação

- Visão geral e contexto: [`.ai/ai.md`](.ai/ai.md)
- Requisitos: [`docs/prd.md`](docs/prd.md)
- Arquitetura: [`docs/architecture.md`](docs/architecture.md) · Decisões: [`adr/`](adr/README.md)
- Modelo de dados: [`docs/data-model.md`](docs/data-model.md)
- Design system: [`docs/design-system.md`](docs/design-system.md)

## Stack

Next.js · FastAPI · PostgreSQL (FTS + pgvector, Supabase) · Docker · free-tier deploy (Vercel + host sem cold start).

## Status

Scaffold inicial. Backlog de construção por fases no Notion (Tasks Tracker).
