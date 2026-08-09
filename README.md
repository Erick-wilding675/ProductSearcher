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
docker compose up -d db          # sobe só o Postgres (pgvector)
make migrate                     # cria o schema (alembic upgrade head)
make seed                        # carrega o catálogo seed
docker compose up -d api         # sobe a API já com dados
# Frontend:
cd frontend && npm install && npm run dev
```

- API: http://localhost:8000 (`/health`)
- Web: http://localhost:3000

> **Não pule `make migrate` e `make seed`.** O `docker compose up` sobe o banco
> **vazio** — nada no compose roda migrations. Com o banco vazio a API responde
> `[]` em `/categories`, a busca não acha nada e a extensão fica calada, o que
> parece defeito e não é.

Para conferir se o catálogo entrou: `curl localhost:8000/categories` deve listar
as categorias com `product_count > 0`.

### Sem Docker (venv local, Python 3.11+)

Para rodar/lint/test o backend fora do Docker, use um virtualenv único na raiz:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e "./api[dev]" -e "./worker[dev]"
```

`.venv/` está no `.gitignore`. Atalhos de qualidade na raiz: `make lint` / `make format` / `make test`.

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

## Licença

Distribuído sob a **Business Source License 1.1 (BUSL-1.1)** — ver [`LICENSE`](LICENSE).

Resumo (não substitui o texto da licença): uso **não-produção** (avaliação, desenvolvimento, teste) é livre; uso em **produção** é permitido apenas de forma **não-comercial**. Em **2030-07-01** (Change Date), converte automaticamente para **Apache License 2.0**. Para uso comercial antes dessa data, contate o Licensor. A BUSL **não** é uma licença OSI open-source. Motivação e trade-offs em [ADR-0006](adr/0006-licenciamento-busl.md).
