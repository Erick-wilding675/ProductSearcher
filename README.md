# ProductSearcher

Plataforma de **descoberta, comparação e análise de produtos**: busca textual com parser
de intenção determinístico, filtros estruturados por specs, ranking explicável e
comparação lado a lado. Dois clientes consomem a mesma API: um web app e uma extensão
Chrome que responde sobre a SERP do Google.

É um projeto de portfólio de engenharia (arquitetura, dados, IA aplicada, DevOps),
executado inteiro em free-tier.

> **IA é complementar.** Nenhum caminho de resposta passa por um LLM. A Fase 6 mediu
> isso: a precisão@5 da suíte de relevância subiu de 16% para 68% com trabalho de
> configuração de FTS e rotulagem offline, e as duas peças de IA em runtime que a fase
> construiu terminaram desligadas por medição. Ver [ADR-0010](adr/0010-fase-6-onde-a-ia-entra.md).

## No ar

| | |
| --- | --- |
| **Web app** | <https://product-searcher-tawny.vercel.app> |
| **API** | <https://productsearcher-api.fly.dev> ([`/health`](https://productsearcher-api.fly.dev/health)) |
| **Extensão** | carregada sem compactação a partir de `extension/` (ver [`extension/README.md`](extension/README.md)) |

Topologia: backend no Fly.io em `gru` (`shared-cpu-1x`, 256 MB, sem sleep), banco
Supabase em `sa-east-1` colado no backend, frontend na Vercel. O keep-alive do Supabase
é o próprio health check do Fly, que executa um `SELECT 1` a cada 30 s. O porquê de cada
escolha está no [ADR-0011](adr/0011-deploy-producao-fly-io.md); os runbooks, em
[`infra/deploy/`](infra/deploy/README.md).

## Base de conhecimento

A documentação canônica do projeto vive no Notion e é espelhada neste repositório, que
versiona o conhecimento junto ao código:

**[ProductSearcher no Notion](https://marmalade-linen-4f8.notion.site/ProductSearcher-3865658dda14806fba0ffe185835ea2f)**

O hub do Notion concentra o Document Hub (PRD, ADRs, arquitetura, design), o Tasks
Tracker (backlog por fases, com responsável e status) e a base de Comunicados. Quando o
repositório e o Notion divergirem, o Notion é a fonte de verdade sobre **estado de
tarefas**; o repositório é a fonte de verdade sobre **o que o código faz**.

## Monorepo

```
api/         Backend FastAPI (monólito modular: catalog | search | ai | core)
worker/      Ingestão do catálogo seed (raw, normalização, validação, upsert)
frontend/    Web app (Next.js + TypeScript + Tailwind, tokens violet, light/dark)
extension/   Extensão Chrome MV3, cliente fino da mesma API
infra/       Notas de infraestrutura e runbooks de deploy
docs/        Documentação viva (PRD, arquitetura, dados, design, casos de uso)
adr/         Architecture Decision Records
.ai/         Contexto para agentes de IA
scripts/     Utilitários de medição (cold start)
```

## Começar (dev)

Pré-requisito: Docker.

```bash
cp .env.example .env
docker compose up -d db          # sobe só o Postgres (pgvector)

# DATABASE_URL explícita: veja o aviso logo abaixo antes de rodar
export DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/productsearcher'
make migrate                     # cria o schema (alembic upgrade head)
make seed                        # carrega o catálogo seed

docker compose up -d api         # sobe a API já com dados
cd frontend && npm install && npm run dev
```

No PowerShell, a terceira linha é `$env:DATABASE_URL = 'postgresql+psycopg://postgres:postgres@localhost:5432/productsearcher'`.

- API: <http://localhost:8000> (`/health`)
- Web: <http://localhost:3000>

> ### Rode `make migrate` e `make seed` com a `DATABASE_URL` explícita
>
> Os dois alvos **não** falam com o Postgres do compose por padrão. `make migrate` lê
> `api/.env` e `make seed` lê `worker/.env`, e numa máquina que já operou produção esses
> arquivos apontam para o **Supabase**. Sem a variável exportada, o comando que você
> acha que está preparando o banco local aplica DDL e recarrega o catálogo **em
> produção**, sem pedir confirmação.
>
> Recarregar o seed em produção não é reversível por desfazer: ele reescreve
> `product_specs.attributes` e apaga os rótulos de `use_case`, o que faz "notebook gamer"
> voltar vazio até alguém re-rotular.
>
> A variável exportada vence o `.env`, porque os dois lados usam `override=False`.

> **Não pule `make migrate` e `make seed`.** O `docker compose up` sobe o banco **vazio**,
> porque nada no compose roda migrations. Com o banco vazio a API responde `[]` em
> `/categories`, a busca não acha nada e a extensão fica calada por decisão de projeto
> (RF-51), o que parece defeito e não é.

Confira que o catálogo entrou antes de seguir. As categorias devem vir com
`product_count > 0`:

```bash
curl localhost:8000/categories
```

### Porta 5432 ocupada

```bash
DB_PORT=5433 docker compose up -d db api
```

Dentro da rede do compose os serviços continuam falando com `db:5432`. A variável muda
apenas a porta publicada no host.

### Sem Docker (venv na raiz, Python 3.11+)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e "./api[dev]" -e "./worker[dev]"
```

`.venv/` está no `.gitignore`.

## Comandos

`make help` lista todos. Os principais:

| Comando | O que faz |
| --- | --- |
| `make ci` | Reproduz a CI localmente (lint mais testes de api e worker) |
| `make lint` / `make format` | `ruff` no backend, `eslint` e `prettier` no frontend |
| `make test` | `pytest` em `api/` e `worker/` |
| `make migrate` | `alembic upgrade head` contra o `DATABASE_URL` do ambiente |
| `make seed` | Carrega o catálogo seed |
| `make up` / `make down` / `make logs` | Ciclo do docker compose |

## Testes

| Suíte | Como rodar | Observação |
| --- | --- | --- |
| API | `cd api && pytest -q` | Roda sem banco, com fakes e SQL compilado |
| KPI de relevância | `cd api && pytest -q tests/test_relevance.py` | Exige Postgres com o seed carregado. Sem banco a suíte se pula em vez de falhar em falso |
| Worker | `cd worker && pytest -q` | Normalização, validação, qualidade de dados e upsert |
| Frontend | `cd frontend && npm run lint && npm run build` | |
| E2E | `cd frontend && npm run test:e2e` | Playwright sobre o fluxo busca, seleção e comparação. `npm run test:e2e:headed` acompanha no navegador |
| Extensão | `cd extension && node --test` | Runner nativo do Node, sem dependências |

A CI (`.github/workflows/ci.yml`) roda lint, api, worker, frontend e extensão. Os jobs de
api e worker sobem um Postgres com pgvector, aplicam as migrations e carregam o seed, para
que o KPI de relevância do PRD seja medido de verdade a cada merge.

> O job `lint` da CI aplica `ruff --fix`, `ruff format` e `prettier` e **commita o
> resultado no branch**. Depois de um push, faça `git pull` antes de continuar.

## Deploy

Push na `main` com CI verde dispara `flyctl deploy` (`.github/workflows/deploy-backend.yml`),
que publica exatamente o commit aprovado pela CI e confirma o `/health` com o campo `db`
em `ok`. O frontend segue a integração Git nativa da Vercel.

> **Migrations não rodam no deploy** ([ADR-0011](adr/0011-deploy-producao-fly-io.md) D7).
> O DDL do Alembic exige o pooler de sessão (porta 5432) enquanto o runtime usa o de
> transação (6543). Toda migration é passo manual do runbook, executado **antes** do
> deploy que depende dela.

## Documentação

Índice completo em [`docs/README.md`](docs/README.md). Os principais:

### Especificação e arquitetura

| Documento | Conteúdo |
| --- | --- |
| [`docs/prd.md`](docs/prd.md) | Requisitos priorizados por MoSCoW, métricas, regras de negócio e estado de implementação de cada RF |
| [`docs/use-cases.md`](docs/use-cases.md) | Atores, catálogo de casos de uso e diagramas de sequência |
| [`docs/architecture.md`](docs/architecture.md) | Camadas, módulos, contratos de interface e endpoints |
| [`docs/data-model.md`](docs/data-model.md) | Esquema relacional, JSONB de specs e colunas derivadas |
| [`docs/design-system.md`](docs/design-system.md) | Paleta violet, tokens light/dark, tipografia e acessibilidade |
| [`docs/wireframes.md`](docs/wireframes.md) | Telas do MVP e o que cada uma cobre |
| [`docs/plano-dados-completos.md`](docs/plano-dados-completos.md) | Levantamento de 2026-08-09 sobre a completude do catálogo e as decisões que saíram dele |
| [`adr/README.md`](adr/README.md) | Índice das decisões arquiteturais, com status |

### Por módulo

| Módulo | Documento |
| --- | --- |
| Backend | [`api/README.md`](api/README.md); busca vetorial em [`api/README-vector.md`](api/README-vector.md) |
| Ingestão | [`worker/README.md`](worker/README.md); dataset em [`worker/seed/README.md`](worker/seed/README.md); gerador offline em [`worker/tools/seedbuilder/README.md`](worker/tools/seedbuilder/README.md) |
| Web app | [`frontend/README.md`](frontend/README.md) |
| Extensão | [`extension/README.md`](extension/README.md) |
| Infraestrutura | [`infra/README.md`](infra/README.md); runbooks em [`infra/deploy/`](infra/deploy/README.md) |
| Agentes de IA | [`.ai/ai.md`](.ai/ai.md) |

## Stack

Next.js · React · TypeScript · Tailwind · shadcn/ui · Playwright · FastAPI · SQLAlchemy ·
Alembic · PostgreSQL com Full Text Search e pgvector · Docker · Fly.io · Supabase ·
Vercel · GitHub Actions.

## Status

MVP no ar desde 18/09/2026. As sete fases de construção estão fechadas: infraestrutura,
schema e ingestão, API de busca, web app, extensão, IA e deploy. Cada uma tem registro em
ADR. O backlog corrente vive no Tasks Tracker do Notion.

Construído e desligado por decisão medida, não por falta de tempo: a busca vetorial
(`vector_enabled=false`) e a fusão híbrida por RRF (`hybrid_enabled=false`). As duas
esperam a tabela `searches` acumular consulta real de produção antes de serem
reavaliadas. O racional está em [ADR-0010](adr/0010-fase-6-onde-a-ia-entra.md) D4 e D4.1.

## Licença

Distribuído sob a **Business Source License 1.1 (BUSL-1.1)**, em [`LICENSE`](LICENSE).

Resumo que não substitui o texto da licença: uso não-produção (avaliação, desenvolvimento,
teste) é livre; uso em produção é permitido apenas de forma não-comercial. Em
**2030-07-01** a licença converte automaticamente para Apache License 2.0. Para uso
comercial antes dessa data, contate o Licensor. A BUSL não é uma licença OSI
open-source. Motivação e trade-offs em [ADR-0006](adr/0006-licenciamento-busl.md).
