# infra: infraestrutura e deploy

Notas e artefatos de infraestrutura. A topologia de produção e o porquê de cada escolha
estão no [ADR-0011](../adr/0011-deploy-producao-fly-io.md), que fecha o ponto que o
[ADR-0004](../adr/0004-deploy-free-tier.md) deixou em aberto.

## Dev local

O `docker-compose.yml` na raiz sobe Postgres com pgvector e a API. O worker roda sob
demanda, no profile `jobs`:

```bash
docker compose run --rm worker
```

Atalhos no `Makefile` da raiz: `make up`, `make down`, `make logs` para o ciclo do compose;
`make migrate` e `make seed` para preparar o banco; `make lint`, `make format`, `make test`
e `make ci` para qualidade.

> O compose **não** aplica migrations nem carrega o seed. Um banco recém-criado sobe vazio,
> e uma API contra banco vazio responde `[]` em tudo.

`python infra/check_db.py` testa a conexão lendo o `DATABASE_URL` do `.env` da raiz, sem
imprimir a senha. Sai com código 0 quando a conexão funciona.

## Produção

| Camada | Onde | Configuração |
| --- | --- | --- |
| Frontend | Vercel | Root directory `frontend/`; `NEXT_PUBLIC_API_URL` aponta para o Fly; deploy a cada push na `main` |
| Backend | Fly.io, região `gru` | `shared-cpu-1x` com 256 MB, sem sleep. `api/fly.toml`; segredos por `flyctl secrets` |
| Banco | Supabase, região `sa-east-1` | Colado no backend para tirar a travessia de continente do caminho crítico |
| Keep-alive | Health check do próprio Fly | Sonda `/health` a cada 30 s; como o endpoint executa `SELECT 1`, a mesma sondagem evita a pausa do Supabase free. Não há cron externo |

## CI/CD

| Workflow | Quando roda | O que faz |
| --- | --- | --- |
| `.github/workflows/ci.yml` | Push na `main` e toda PR | Cinco jobs: `lint` (corrige estilo e commita), depois `api`, `worker`, `frontend` e `extension`. Os jobs de api e worker sobem Postgres com pgvector, aplicam migrations e carregam o seed |
| `.github/workflows/deploy-backend.yml` | `workflow_run` da CI concluído com sucesso, em push na `main` | `flyctl deploy --remote-only` sobre o commit exato que a CI aprovou, seguido de smoke no `/health` exigindo `"db":"ok"` |

O deploy escuta o `workflow_run` em vez de `push` de propósito: com `push`, o deploy
correria em paralelo com os testes e poderia publicar um commit que a suíte reprova minutos
depois.

**Migrations não entram no deploy** (ADR-0011 D7). O DDL do Alembic exige o pooler de
sessão (5432) e o runtime usa o de transação (6543); embutir a migration no deploy
obrigaria a carregar uma segunda credencial no host só para isso. Toda migration é passo
manual do runbook, executado antes do deploy que depende dela.

## Medição de cold start

```bash
./scripts/measure-cold-start.sh https://productsearcher-api.fly.dev
```

Mede a **primeira** requisição a `/health` e a `/search?q=notebook` e compara com o teto de
2 s da RNF-02. Sai com código diferente de zero quando algum dos dois estoura, o que o
torna utilizável em pipeline. Sem argumento, aponta para `http://localhost:8000`.

O que ele mede é tempo total visto de fora, incluindo a travessia da internet, então serve
de **teto**. Ele não substitui o p95 medido dentro do servidor, que continua pendente
(ADR-0011).

## Runbooks

- [`deploy/README.md`](deploy/README.md): ordem de execução e o que cada provedor exige.
- [`deploy/fly.md`](deploy/fly.md): backend no Fly, passo a passo.
- [`deploy/supabase-sa-east-1.md`](deploy/supabase-sa-east-1.md): provisionamento do banco
  atual.
- [`deploy/supabase.md`](deploy/supabase.md): procedimento genérico de provisionamento e o
  histórico do projeto anterior em `us-east-1`, hoje desativado.
