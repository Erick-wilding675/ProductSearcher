# Deploy — passos por provedor

> Referências: [ADR-0004](../../adr/0004-deploy-free-tier.md) (topologia) e
> [ADR-0011](../../adr/0011-deploy-producao-fly-io.md) (host, região, keep-alive e CI/CD).
> Runbooks detalhados: [`fly.md`](fly.md) (backend) e [`supabase-sa-east-1.md`](supabase-sa-east-1.md) (banco).

Ordem de execução, porque uma coisa depende da outra: **banco → backend → frontend →
extensão**.

## 1. Banco — Supabase (`sa-east-1`)

Projeto em São Paulo, `pgvector` habilitado, migrations pela porta **5432** e seed
recarregado. Runtime usa a porta **6543**. Passo a passo em
[`supabase-sa-east-1.md`](supabase-sa-east-1.md).

Keep-alive contra a pausa de 7 dias: **não há cron**. Quem mantém o banco ativo é o
health check do Fly batendo em `/health`, que executa um `SELECT 1` (ADR-0011 D4).

## 2. Backend — Fly.io (`gru`)

`shared-cpu-1x`, 256 MB, sem sleep. Configuração em [`api/fly.toml`](../../api/fly.toml),
segredos em `flyctl secrets` (`DATABASE_URL`, `CORS_ORIGINS`). Deploy automático após CI
verde na `main` (`.github/workflows/deploy-backend.yml`). Passo a passo em
[`fly.md`](fly.md).

## 3. Frontend — Vercel

1. Importar o repositório com **Root Directory: `frontend/`**.
2. Variável de ambiente `NEXT_PUBLIC_API_URL` = URL pública da API
   (ex.: `https://productsearcher-api.fly.dev`).
3. Deploy automático a cada push na `main` (integração Git nativa).
4. **Anote o domínio final** e grave-o em `CORS_ORIGINS` no Fly — sem curinga
   (ADR-0011 D5). Previews não falam com a API de produção.

## 4. Extensão

`extension/src/shared/config.js` já aponta para produção, e `manifest.json` lista a
origem da API em `host_permissions`. Se as URLs mudarem, os dois arquivos mudam juntos —
trocar um sem o outro faz toda requisição falhar por permissão.

## Checklist de fechamento da Fase 7

- [ ] `/health` público respondendo `{"status":"ok", ..., "db":"ok"}`.
- [ ] Web app público buscando e comparando (smoke E2E da Fase 7).
- [ ] Popup da extensão respondendo sobre a SERP do Google, contra a API de produção.
- [ ] Deploy automático verificado: push na `main` → CI verde → release no Fly.
- [ ] Medição de latência registrada no ADR-0011 (a pendência de medição de D3).
