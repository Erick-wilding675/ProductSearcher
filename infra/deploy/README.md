# Deploy (free-tier) — passos por provedor

> Referência: [ADR-0004](../../adr/0004-deploy-free-tier.md). Limites de free-tier verificados em jun/2026 (podem mudar).

## Frontend — Vercel

1. Importar o repositório (root: `frontend/`).
2. Definir `NEXT_PUBLIC_API_URL` apontando para o backend.
3. Deploy automático a cada push na `main`.

## Backend — host sem cold start (a confirmar: Fly.io / HF Spaces)

- Evitar Render free (cold start de 30–60s prejudica a demo e o popup da extensão).
- Configurar variáveis: `DATABASE_URL`, `AI_ENABLED`, `CORS_ORIGINS`.
- Healthcheck em `/health`.

## Banco — Supabase

1. Projeto Postgres com extensão `pgvector` habilitada.
2. Aplicar migrations.
3. **Keep-alive**: cron/ping periódico para evitar a pausa após 7 dias de inatividade.

## Decisão em aberto

Host definitivo do backend (Fly.io vs HF Spaces) após teste prático de cold start/limites.
