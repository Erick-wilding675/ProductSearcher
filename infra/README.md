# infra/ — Infraestrutura e deploy

Notas e artefatos de infraestrutura. Decisão de deploy em [ADR-0004](../adr/0004-deploy-free-tier.md).

## Dev local

`docker-compose.yml` (na raiz) sobe Postgres (pgvector) + API. O worker roda sob demanda (profile `jobs`: `docker compose run --rm worker`).

Atalhos via `Makefile` (raiz): `make up` / `make down` / `make logs`; qualidade: `make lint` / `make format` / `make test` / `make ci`.

## Produção (free-tier)

| Camada | Onde |
| --- | --- |
| Frontend | Vercel (deploy automático via Git) |
| Backend | Host sem cold start — Fly.io / Hugging Face Spaces (a confirmar) |
| Banco | Supabase (Postgres + pgvector) + keep-alive contra a pausa de 7 dias |

CI em `.github/workflows/ci.yml` (lint + format-check + test, jobs `api`/`worker`/`frontend`). Pipeline de deploy completo é tarefa da Fase 7.

Ver `deploy/README.md` para passos por provedor e `deploy/supabase.md` para o provisionamento do banco (Fase 1).
