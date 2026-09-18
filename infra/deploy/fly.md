# Backend em produção — Fly.io (runbook)

> Decisão: [ADR-0011](../../adr/0011-deploy-producao-fly-io.md). Configuração versionada em [`api/fly.toml`](../../api/fly.toml).
> **Nenhum segredo entra no Git.** `DATABASE_URL` e `CORS_ORIGINS` vivem em `flyctl secrets`; o token do Fly, nas secrets do GitHub.

## Pré-requisitos

- Conta no Fly.io com cartão cadastrado (o free tier acabou; o serviço custa ~US$2/mês).
- `flyctl` instalado (`iwr https://fly.io/install.ps1 -useb | iex` no Windows) e `flyctl auth login`.
- Projeto Supabase em **sa-east-1** já provisionado, com migrations e seed aplicados —
  ver [`supabase-sa-east-1.md`](supabase-sa-east-1.md). Faça isso **antes** do primeiro deploy.

## Primeiro deploy

1. **Criar o app sem subir nada ainda** (o `fly.toml` já está no repositório; não deixe o
   `launch` reescrevê-lo):

   ```bash
   cd api
   flyctl apps create productsearcher-api
   ```

   Se o nome já estiver tomado, escolha outro e ajuste `app` em `api/fly.toml`, a URL do
   smoke em `.github/workflows/deploy-backend.yml`, `NEXT_PUBLIC_API_URL` na Vercel e
   `API_BASE_URL` da extensão.

2. **Gravar os segredos** (o `<...>` é literal — substitua):

   ```bash
   flyctl secrets set \
     DATABASE_URL='postgresql+psycopg://postgres.<ref>:<senha>@aws-1-sa-east-1.pooler.supabase.com:6543/postgres' \
     CORS_ORIGINS='["https://productsearcher.vercel.app"]'
   ```

   - **Porta 6543** (pooler de *transação*) para o runtime. O 5432 é para migration
     (ADR-0011 D7).
   - `CORS_ORIGINS` é uma lista JSON e recebe **a origem exata** do web app, sem curinga
     (ADR-0011 D5). Confirme o domínio que a Vercel atribuiu antes de gravar.
   - `CORS_ORIGIN_REGEX` não precisa ser definido: o default do código já cobre
     `chrome-extension://` e `moz-extension://`.

3. **Deploy:**

   ```bash
   flyctl deploy --remote-only
   ```

4. **Conferir:**

   ```bash
   curl https://productsearcher-api.fly.dev/health
   # {"status":"ok","ai_enabled":false,"db":"ok"}
   ```

   `db":"down"` = app no ar e banco inacessível: confira a `DATABASE_URL` (porta, senha,
   região) com `flyctl logs`.

5. **Automatizar:** gere um token de deploy (`flyctl tokens create deploy -x 999999h`) e
   grave como secret **`FLY_API_TOKEN`** no GitHub (Settings → Secrets and variables →
   Actions). A partir daí, todo push na `main` com CI verde republica o backend
   (`.github/workflows/deploy-backend.yml`).

## Operação do dia a dia

| Situação | Comando |
| --- | --- |
| Ver logs | `flyctl logs -a productsearcher-api` |
| Estado das máquinas | `flyctl status -a productsearcher-api` |
| Reiniciar | `flyctl apps restart productsearcher-api` |
| Voltar versão | `flyctl releases -a productsearcher-api` e `flyctl deploy --image <imagem da release anterior>` |
| Trocar um segredo | `flyctl secrets set CHAVE='valor'` (reinicia a máquina) |
| Subir para 512 MB | editar `memory` em `api/fly.toml` e `flyctl deploy` (gatilho do ADR-0011 D2) |

## O que NÃO fazer aqui

- **Não rodar migration no deploy.** O DDL do Alembic quebra no pooler de transação; use
  a porta 5432 a partir da sua máquina (ADR-0011 D7 e o runbook do Supabase).
- **Não ligar `vector_enabled` em produção.** A imagem de produção não tem o modelo
  (ADR-0010 / ADR-0011 D1); ligar a flag derruba a busca.
- **Não usar `Dockerfile.vector` aqui.** Ele é de teste, pesa ~886 MB em disco e exige
  1 GB de RAM.
- **Não pedir IPv4 dedicado** (US$2/mês): o compartilhado atende.

## Critério de conclusão (definition of done)

- [ ] App `productsearcher-api` criado na região `gru`.
- [ ] Segredos `DATABASE_URL` (6543) e `CORS_ORIGINS` gravados.
- [ ] `/health` respondendo `{"status":"ok", ..., "db":"ok"}` pela URL pública.
- [ ] Health check do Fly ativo (`flyctl status` mostra a máquina *passing*) — é ele que
      segura a pausa do Supabase (ADR-0011 D4).
- [ ] `FLY_API_TOKEN` no GitHub e um deploy automático verificado ponta a ponta.
