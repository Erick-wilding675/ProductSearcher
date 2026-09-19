# Deploy: passos por provedor

> Referências: [ADR-0011](../../adr/0011-deploy-producao-fly-io.md) (host, região,
> keep-alive e CI/CD) e [ADR-0004](../../adr/0004-deploy-free-tier.md) (topologia
> original). Runbooks detalhados: [`fly.md`](fly.md) para o backend e
> [`supabase-sa-east-1.md`](supabase-sa-east-1.md) para o banco.

Ordem de execução, porque uma coisa depende da outra: **banco, backend, frontend,
extensão**.

## 1. Banco: Supabase em `sa-east-1`

Projeto em São Paulo, `pgvector` habilitado, migrations pela porta **5432** (pooler de
sessão) e seed carregado. O runtime usa a porta **6543** (pooler de transação). Passo a
passo em [`supabase-sa-east-1.md`](supabase-sa-east-1.md).

Keep-alive contra a pausa de 7 dias do plano free: **não há cron**. Quem mantém o banco
ativo é o health check do Fly batendo em `/health`, que executa um `SELECT 1`
(ADR-0011 D4).

> Depois de recarregar o seed, **re-rotule o `use_case`**. O upsert de `product_specs`
> substitui os atributos derivados, e sem esse passo "notebook" responde e "notebook
> gamer" volta vazio.

## 2. Backend: Fly.io em `gru`

`shared-cpu-1x` com 256 MB, sem sleep. Configuração em [`api/fly.toml`](../../api/fly.toml),
segredos por `flyctl secrets` (`DATABASE_URL` e `CORS_ORIGINS`). Deploy automático após CI
verde na `main`. Passo a passo em [`fly.md`](fly.md).

## 3. Frontend: Vercel

1. Importar o repositório com **Root Directory `frontend/`**.
2. Definir `NEXT_PUBLIC_API_URL` com a URL pública da API
   (`https://productsearcher-api.fly.dev`).
3. Deploy automático a cada push na `main`, pela integração Git nativa.
4. **Anotar o domínio final** e gravá-lo em `CORS_ORIGINS` no Fly, sem curinga
   (ADR-0011 D5). Previews da Vercel não falam com a API de produção, por decisão.

## 4. Extensão

`extension/src/shared/config.js` já aponta para produção e `manifest.json` lista a origem
da API em `host_permissions`. Se as URLs mudarem, os dois arquivos mudam juntos: trocar um
sem o outro faz toda requisição falhar por permissão, com erro que não menciona o manifest.

## Aplicar uma migration nova

O deploy **não** roda migrations (ADR-0011 D7). Toda migration é passo manual, e a ordem
importa: código que lê uma coluna inexistente quebra em produção.

```bash
# 1. DATABASE_URL apontando para o pooler de SESSÃO (porta 5432)
cd api && alembic upgrade head

# 2. confirme a revisão aplicada
alembic current

# 3. só então faça o merge na main que publica o código que depende dela
```

Se a migration mudar o formato do catálogo, recarregue o seed e re-rotule o `use_case`
antes de considerar o deploy concluído.

## Fechamento da Fase 7 (18/09/2026)

| Item | Estado |
| --- | --- |
| `/health` público respondendo com `"db":"ok"` | Confirmado |
| Web app público buscando e comparando | Confirmado, com smoke E2E em Playwright |
| Popup da extensão respondendo sobre a SERP contra a API de produção | Confirmado |
| Medição de latência registrada no ADR-0011 | Confirmado: `/search` com mediana de 349 ms, medido de fora |
| Deploy automático verificado ponta a ponta | **Pendente.** O workflow existe, mas falta gravar `FLY_API_TOKEN` no GitHub e observar um ciclo completo de CI verde até release no Fly |

Pendência operacional herdada, registrada no ADR-0011: **rotacionar a senha do banco**. Ela
chegou a entrar numa imagem publicada antes de existir o `.dockerignore` da `api/`. O
registro do Fly é privado e o risco é baixo, mas a higiene pede trocar a senha e atualizar
apenas o secret do Fly, que não vai para a imagem.
