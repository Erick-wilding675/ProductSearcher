# ProductSearcher — Contexto para IAs

> Ponto de entrada de contexto para qualquer agente de IA (Claude e outros) que trabalhe neste repositório.
> `CLAUDE.md` e `AGENTS.md` na raiz apontam para este arquivo.

## O que é

ProductSearcher é uma **plataforma inteligente de descoberta, comparação e análise de produtos** para consumidores em jornada de compra. Entrega ranking, comparação e explicações em um só lugar — via **web app** e via **extensão Chrome contextual** que responde sobre a SERP do Google.

É um **projeto de portfólio** de engenharia (arquitetura moderna, dados, IA aplicada, DevOps), **não** uma startup. O objetivo é um case técnico exemplar, executável em **free-tier**.

## Princípios inegociáveis

1. **IA é complementar.** O sistema funciona 100% sem OpenAI/Gemini/Claude/LangGraph/RAG. IA fica atrás de interface, plugável.
2. **Simplicidade e desacoplamento.** Monólito modular, sem complexidade prematura nem microserviços desnecessários.
3. **Evolução incremental.** Decisões do MVP têm caminho de evolução documentado (ADRs).
4. **Documentação como fonte de verdade.** Inconsistências entre doc e código devem ser sinalizadas, documentadas e corrigidas.
5. **Acessível e observável por padrão.**

## Decisões fundacionais (ver ADRs)

- **Dados:** dataset **seed curado** no MVP (sem scraping). APIFY a validar no futuro. → `adr/0001-aquisicao-de-dados.md`
- **Datastore:** **Postgres-only** (FTS + pgvector) no Supabase; Qdrant/OpenSearch atrás de interface. → `adr/0002-datastore-postgres-only.md`
- **Arquitetura:** **monólito modular** FastAPI + worker; sem API Gateway/microserviços no MVP. → `adr/0003-monolito-modular.md`
- **Deploy:** Vercel (front) + backend sem cold start (Fly.io/HF) + Supabase, free-tier. → `adr/0004-deploy-free-tier.md`

## Stack-alvo (MVP)

- **Frontend:** Next.js + TypeScript + Tailwind + shadcn/ui
- **Backend:** FastAPI (Python), monólito modular (módulos `catalog`, `search`, `ai`, `core`)
- **Dados:** PostgreSQL (FTS + pgvector) via Supabase
- **Worker:** ingestão do seed (raw → normalização → validação → upsert)
- **Extensão:** Chrome Manifest V3 (cliente fino da mesma API)
- **Infra:** Docker Compose (dev); deploy em free-tier

## Escopo do MVP

Busca textual, comparação (2–4 produtos), ranking determinístico, catálogo seed (**notebooks + fones**), web app e extensão de demonstração. **Fora:** auth, mobile nativo, cashback/afiliados, scraping automatizado, RAG/agentes em produção.

## Como o sistema funciona (resumo)

Clientes (web + extensão) → **uma API** (FastAPI) → parsing **determinístico** de intenção → busca (FTS, opc. pgvector) → ranking explicável → resposta. Worker popula o catálogo. IA (explicações) só quando habilitada.

Contratos-chave (permitem evolução sem reescrita): `IntentParser`, `SearchProvider`, `VectorProvider`, `RankingService`, `AIService`, `IngestionSource`.

## Estrutura do repositório

```
/CLAUDE.md, /AGENTS.md      → apontam para .ai/ai.md
/.ai/                       → contexto para IAs (este diretório)
/docs/                      → documentação viva (PRD, arquitetura, design, etc.)
/adr/                       → Architecture Decision Records
/frontend/                  → web app (Next.js)        [a criar — Fase 4]
/api/                       → backend FastAPI           [a criar — Fase 3]
/worker/                    → ingestão do seed          [a criar — Fase 2]
/infra/                     → docker, deploy, CI        [a criar — Fase 1]
```

## Onde encontrar contexto

- Produto/requisitos: `.ai/product.md` · detalhe em `docs/prd.md`
- Arquitetura: `.ai/architecture.md` · detalhe em `docs/architecture.md`
- Modelo de dados: `.ai/data-model.md` · detalhe em `docs/data-model.md`
- Design system: `.ai/design-system.md` · detalhe em `docs/design-system.md`
- Convenções de engenharia: `.ai/conventions.md`
- Glossário: `.ai/glossary.md`
- Decisões: `adr/`

> A fonte de verdade canônica também vive no Notion (Document Hub). Estes arquivos espelham e versionam o conhecimento junto ao código.

## Regras para agentes de IA

- Antes de implementar, entenda **por que** algo existe e os trade-offs (ver ADRs).
- Não introduza tecnologia sem justificar benefício e registrar (ADR, se relevante).
- Mantenha o sistema funcionando **sem IA**.
- Atualize a documentação quando mudar comportamento; sinalize inconsistências.
- Prefira modularidade, testabilidade e observabilidade.
