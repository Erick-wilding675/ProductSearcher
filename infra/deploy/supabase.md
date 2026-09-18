# Provisionamento do Supabase (Postgres + pgvector)

> Tarefa Fase 1 · Referência: [ADR-0002](../../adr/0002-datastore-postgres-only.md) e [ADR-0004](../../adr/0004-deploy-free-tier.md).
> Banco gerenciado free-tier com `pgvector`. **Nenhum segredo entra no Git** — a connection string vai só no `.env` local / nas secrets do provedor.

## Pré-requisitos

- Conta no Supabase (login com GitHub é o caminho mais rápido).
- Plano Free é suficiente para o MVP.

## Passo a passo

1. **Criar o projeto**
   - Acesse <https://supabase.com/dashboard> → **New project**.
   - Organização: a sua. **Name**: `productsearcher`.
   - **Database Password**: gere uma forte e **guarde no seu gerenciador de senhas** (ela compõe a connection string; não será commitada).
   - **Region**: a mais próxima dos usuários/da demo (ex.: `South America (São Paulo)`).
   - **Create new project** e aguarde o provisionamento (~2 min).

2. **Habilitar a extensão `pgvector`**
   - Menu lateral → **Database** → **Extensions**.
   - Busque por `vector`, habilite a extensão **`vector`** (é o `pgvector`).
   - Alternativa via SQL (**SQL Editor** → New query):
     ```sql
     create extension if not exists vector;
     ```

3. **Obter a connection string**
   - Topo do dashboard → **Connect** (ou **Project Settings → Database → Connection string**).
   - Use a string do **Connection pooler** (modo *Transaction*, porta `6543`) — recomendada para free-tier (limite de conexões e compatibilidade IPv4).
   - Formato típico:
     ```
     postgres://postgres.<ref>:<SUA_SENHA>@aws-0-<region>.pooler.supabase.com:6543/postgres
     ```

4. **Adaptar o driver para o nosso stack (psycopg v3)**
   - O código usa SQLAlchemy + `psycopg` v3, então troque o esquema `postgres://` por `postgresql+psycopg://`:
     ```
     postgresql+psycopg://postgres.<ref>:<SUA_SENHA>@aws-0-<region>.pooler.supabase.com:6543/postgres
     ```

5. **Gravar no `.env` (sem commitar)**
   - Na raiz do repo, copie o exemplo e edite:
     ```bash
     cp .env.example .env
     ```
   - Em `.env`, defina `DATABASE_URL` com a string adaptada acima.
   - `.env` já está no `.gitignore` — confirme com `git status` que ele **não** aparece.

## Critério de conclusão (definition of done)

- [ ] Projeto Supabase `productsearcher` ativo.
- [ ] Extensão `vector` habilitada (`select * from pg_extension where extname='vector';` retorna 1 linha).
- [ ] Connection string (pooler) adaptada para `postgresql+psycopg://` e gravada no `.env` local.
- [ ] Segredo fora do Git (`.env` ignorado).

> ⚠️ **Obsoleto desde 18/09/2026.** O projeto abaixo (`us-east-1`) foi substituído por
> um em **`sa-east-1`**, junto do backend no Fly ([ADR-0011](../../adr/0011-deploy-producao-fly-io.md) D3).
> A reconstrução está em [`supabase-sa-east-1.md`](supabase-sa-east-1.md). O que segue vale como
> histórico e como referência do procedimento de provisionamento — **a connection string não vale mais**.

## Valores deste projeto (provisionado em 24/06/2026)

Projeto Supabase reaproveitado (org `Erick-wilding675's Org`, Free Plan), região **us-east-1**. `pgvector` confirmado: `vector` v0.8.0.

Conexão via **Transaction pooler** (porta 6543):

| Campo | Valor |
| --- | --- |
| host | `aws-1-us-east-1.pooler.supabase.com` |
| port | `6543` |
| database | `postgres` |
| user | `postgres.fzbaamyeyffnprinrkva` |

`DATABASE_URL` para o `.env` (driver psycopg v3 — substitua `[SUA_SENHA]` pela senha do banco; **não commitar**):

```
postgresql+psycopg://postgres.fzbaamyeyffnprinrkva:[SUA_SENHA]@aws-1-us-east-1.pooler.supabase.com:6543/postgres
```

> Esqueceu a senha do banco? **Connect → Reset password** (ou Project Settings → Database). Guarde no gerenciador de senhas.

> **Nota para Fase 2/3 (pgbouncer):** o Transaction pooler roda o pgbouncer em modo *transaction*, que não suporta prepared statements persistentes. Ao conectar via SQLAlchemy/psycopg em `api/app/core/db.py`, desabilite o cache de prepared statements (psycopg v3: `connect_args={"prepare_threshold": None}`). Para migrations (Alembic), prefira a **Direct connection** (porta 5432).

## Keep-alive (free-tier) — decidido na Fase 7

O Supabase Free **pausa o projeto após 7 dias de inatividade**. A escolha está no
[ADR-0011](../../adr/0011-deploy-producao-fly-io.md) D4: **não há cron**. Quem mantém o
banco ativo é o health check do Fly batendo em `/health` a cada 30 s — endpoint que já
executa um `SELECT 1`, então a mesma sondagem serve de prova de vida do serviço e de
atividade no banco, sem serviço extra nem segredo.

## Notas de evolução

- Migrations (Alembic) e registro de tipos pgvector no SQLAlchemy entram na Fase 2/3 (ver `api/app/core/db.py`).
- Direct connection (porta `5432`) pode ser usada em ambientes com IPv6; para CI/free-tier, prefira o pooler.
