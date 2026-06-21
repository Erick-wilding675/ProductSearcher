# infra/ — Infraestrutura e deploy

Notas e artefatos de infraestrutura. Decisão de deploy em [ADR-0004](../adr/0004-deploy-free-tier.md).

## Dev local

`docker-compose.yml` (na raiz) sobe Postgres (pgvector) + API. O worker roda sob demanda.

## Produção (free-tier)

| Camada | Onde |
| --- | --- |
| Frontend | Vercel (deploy automático via Git) |
| Backend | Host sem cold start — Fly.io / Hugging Face Spaces (a confirmar) |
| Banco | Supabase (Postgres + pgvector) + keep-alive contra a pausa de 7 dias |

CI em `.github/workflows/ci.yml` (lint + test). Pipeline de deploy completo é tarefa da Fase 7.

Ver `deploy/README.md` para passos por provedor.
