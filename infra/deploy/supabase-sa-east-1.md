# Mover o banco para `sa-east-1` (runbook)

> Decisão: [ADR-0011](../../adr/0011-deploy-producao-fly-io.md) D3. Substitui a região registrada em [`supabase.md`](supabase.md) (us-east-1, Fase 1).
> **Por quê:** uma busca faz de 3 a 5 idas ao banco. Com a API em `gru` e o banco na Virgínia, só a rede consumiria 400 a 600 ms, mais do que os 500 ms de orçamento da RNF-01.

Não é migração de dados: **é reconstrução**. O catálogo é reproduzível pela ingestão
(ADR-0001/0009) e `searches` ainda não tem consulta real (ADR-0010). Ninguém precisa de
`pg_dump`.

## Passo a passo

1. **Criar o projeto novo**
   - <https://supabase.com/dashboard> → **New project**.
   - Name: `productsearcher-sa`. **Region: `South America (São Paulo)` / `sa-east-1`.**
   - Gere a senha do banco e guarde no gerenciador de senhas (ela não vai para o Git).
   - O plano Free permite 2 projetos ativos, então dá para criar o novo antes de remover o
     antigo.

2. **Habilitar `pgvector`** (SQL Editor):

   ```sql
   create extension if not exists vector;
   select extname, extversion from pg_extension where extname = 'vector';
   ```

3. **Aplicar as migrations**, da sua máquina, com o **pooler de sessão (5432)**, porque
   o de transação quebra DDL:

   ```bash
   cd api
   # .env local, temporariamente na 5432:
   # DATABASE_URL=postgresql+psycopg://postgres.<ref>:<senha>@aws-1-sa-east-1.pooler.supabase.com:5432/postgres
   alembic upgrade head
   ```

4. **Recarregar o seed** (ainda na 5432):

   ```bash
   cd ../worker
   python -m ingestion.pipeline
   ```

5. **Conferir o que entrou:**

   ```sql
   select count(*) from products;
   select count(*) from offers;
   ```

   **Compare com as mesmas contagens no projeto antigo** (`us-east-1`), que é a
   referência viva: o seed no repositório tem 279 entradas de produto e 1596 de oferta
   antes da deduplicação da ingestão, então o número final não é o do YAML. Se destoar do
   banco atual, pare aqui: deploy sobre catálogo incompleto derruba o KPI de relevância
   sem deixar rastro óbvio.

6. **Re-rotular `use_case`**, passo obrigatório, não opcional:

   ```bash
   # ainda em worker/, ainda na 5432
   python -m tools.seedbuilder.label_use_cases --executar
   ```

   Os rótulos de `use_case` (ADR-010 D2) vivem **só no banco**: o YAML do seed não
   os tem, e o upsert de `product_specs` substitui `attributes` inteiro. Sem este
   passo, o filtro de `use_case` não casa com nada, e a falha é **silenciosa**:
   consultas de uma palavra ("notebook") respondem, mas "notebook gamer" e
   "melhor notebook para programação" voltam com **zero resultados**, porque o
   parser transforma "gamer" em filtro duro. É exatamente a consulta do pitch do
   produto. Leva ~25 min e é grátis no plano da Groq (exige `GROQ_API_KEY` no
   `worker/.env`).

   Conferir depois:

   ```sql
   select count(*) from product_specs where attributes ? 'use_case';
   ```

7. **Trocar os consumidores para a 6543** (pooler de transação, runtime):
   - Fly: `flyctl secrets set DATABASE_URL='postgresql+psycopg://postgres.<ref>:<senha>@aws-1-sa-east-1.pooler.supabase.com:6543/postgres'`
   - `.env` local: volte para a 6543 no uso normal da API.

8. **Aposentar o projeto antigo (`us-east-1`)**, só depois de o `/health` de produção
   responder `"db":"ok"` e uma busca real voltar com resultado. Pausar antes de apagar dá
   caminho de volta.

## Depois

- Atualize a seção "Valores deste projeto" de [`supabase.md`](supabase.md) com o novo
  `ref` e a nova região (a senha, não).
- O keep-alive passa a ser o health check do Fly (ADR-0011 D4): nada de cron.
- Se o projeto novo pausar mesmo assim, é o risco registrado em D4: troque o `SELECT 1`
  por uma escrita periódica e registre no ADR.

## Critério de conclusão (definition of done)

- [ ] Projeto `sa-east-1` ativo, com `vector` habilitado.
- [ ] `alembic upgrade head` aplicado pela 5432.
- [ ] Seed recarregado, com as contagens conferidas.
- [ ] `use_case` re-rotulado (`select count(*) from product_specs where attributes ? 'use_case';` > 0) e uma busca de duas palavras conferida.
- [ ] `DATABASE_URL` (6543) trocada no Fly e no `.env` local.
- [ ] Projeto `us-east-1` pausado (e apagado depois da demo estabilizar).
