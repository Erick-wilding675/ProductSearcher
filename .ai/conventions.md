# Convenções de engenharia

> Acordos de trabalho. Evoluem com o projeto.

## Geral

- Idioma da documentação: **português**. Código e identificadores em **inglês**.
- Ambiente local reprodutível por `docker compose` mais `make migrate` e `make seed`. O
  compose sozinho não prepara o banco.
- Nenhum segredo no repositório. Só `.env.example` é versionado; o `.gitignore` cobre
  `.env` e seus backups (`.env.*`).
- Comandos unificados na raiz pelo `Makefile`: `make lint`, `make format`, `make test`,
  `make ci`.

## Backend (Python, FastAPI)

- Monólito modular: `catalog`, `search`, `ai`, `core`, com fronteiras claras.
- Dependências externas (busca, vetor, IA, ingestão) **atrás de `Protocol`**.
- Lint e formatação com `ruff` (o `ruff format` substitui o black, ferramenta única).
  Tipagem com type hints.
- Testes com `pytest`. A lógica crítica (parser de intenção, ranking, qualidade de dados,
  upsert) tem cobertura direta.
- Testes que dependem de banco se **pulam** quando não há banco, em vez de falhar em falso.
  O KPI de relevância é o caso principal.

## Frontend (Next.js, TypeScript)

- TypeScript estrito, componentes funcionais.
- Tailwind e shadcn/ui, sempre por **tokens de design**, nunca hex solto.
- `eslint` e `prettier`.
- Fluxo principal coberto por Playwright (`npm run test:e2e`).

## Banco e migrations

- Toda mudança de schema entra como migration do Alembic, com `down_revision` encadeado.
- **Migration não roda no deploy** (ADR-0011 D7). É passo manual do runbook, executado
  antes do deploy do código que depende dela.
- DDL e carga do seed usam o pooler de **sessão** (porta 5432); o runtime usa o de
  **transação** (6543) com `prepare_threshold=None`.

## Git e fluxo

- Branch por feature, PR com CI verde antes do merge. A `main` é a única branch de longa
  duração; branches de feature são apagadas depois do merge.
- Mensagens de commit descritivas, no padrão Conventional Commits.
- O job `lint` da CI aplica correções de estilo e **commita no branch**. Depois de um push,
  faça `git pull` antes de continuar, ou o próximo push é rejeitado por non-fast-forward.

## ADRs

- Mudança arquitetural relevante gera um ADR em `adr/`, seguindo o
  [`template.md`](../adr/template.md).
- Todo ADR documenta contexto, decisão, benefícios, consequências, **alternativas
  descartadas** e **caminho de evolução ou gatilho de revisão**.
- ADR de fase inclui registro de construção: o que foi medido, o que a execução desmentiu e
  o que foi recusado.

## Documentação

- Markdown objetivo, técnico e específico. Explique a decisão e o trade-off, não a
  tecnologia genérica.
- Prefira dois-pontos, vírgula ou parênteses a travessão.
- Comportamento que parece defeito e é decisão precisa estar escrito como tal, com o
  porquê.
- Mantenha consistência entre `docs/`, `adr/`, `.ai/`, os READMEs de módulo e o Notion.
  Ao mudar comportamento, atualize a documentação no mesmo trabalho.
