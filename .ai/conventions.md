# Convenções de engenharia

> Acordos de trabalho. Evoluem com o projeto.

## Geral

- Idioma da documentação: **português**. Código e identificadores em **inglês**.
- Tudo reprodutível via `docker compose up`.
- Sem segredos no repositório (usar `.env`, `.env.example` versionado).

## Backend (Python / FastAPI)

- Monólito modular: módulos `catalog`, `search`, `ai`, `core` com fronteiras claras.
- Dependências externas (busca, vetor, IA, ingestão) **atrás de interfaces**.
- Estilo/lint: `ruff` + `black` (ou equivalente); tipagem com type hints.
- Testes: `pytest`; cobrir lógica crítica (parser de intenção, ranking).

## Frontend (Next.js / TS)

- TypeScript estrito; componentes funcionais.
- Estilo: Tailwind + shadcn/ui; usar **tokens de design** (não hex solto).
- `eslint` + `prettier`.

## Git / fluxo

- Branches por feature; PRs com CI verde (lint + test) antes do merge.
- Mensagens de commit descritivas (sugerido: Conventional Commits).

## ADRs

- Mudanças arquiteturais relevantes geram um ADR em `adr/` (ver `adr/template.md`).
- Todo ADR documenta: contexto, decisão, benefícios, consequências, **alternativas descartadas**, **caminho de evolução / gatilho de revisão**.

## Documentação

- Markdown objetivo; explicar decisões e trade-offs; manter consistência entre `docs/`, `adr/`, `.ai/` e o Notion.
