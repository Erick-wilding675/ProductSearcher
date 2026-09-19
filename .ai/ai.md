# ProductSearcher: contexto para agentes de IA

> Ponto de entrada de contexto para qualquer agente que trabalhe neste repositório.
> `CLAUDE.md` e `AGENTS.md` na raiz apontam para este arquivo.

## O que é

ProductSearcher é uma plataforma de **descoberta, comparação e análise de produtos**:
busca textual com parser de intenção determinístico, filtros por specs, ranking explicável
e comparação lado a lado. Dois clientes consomem a mesma API, um web app e uma extensão
Chrome que responde sobre a SERP do Google.

É um **projeto de portfólio** de engenharia (arquitetura, dados, IA aplicada, DevOps), não
uma startup. O objetivo é um case técnico exemplar, executável em free-tier.

**Estado:** MVP em produção desde 18/09/2026. As sete fases de construção estão fechadas.

## Princípios inegociáveis

1. **IA é complementar.** O sistema funciona 100% sem OpenAI, Gemini, Claude, LangGraph ou
   RAG. Toda IA fica atrás de interface e é plugável. Este princípio já foi testado contra
   dados: na Fase 6 a precisão@5 subiu de 16% para 68% sem que o caminho de resposta
   passasse por um modelo, e as duas peças de IA em runtime que a fase construiu saíram
   desligadas.
2. **Decisão de IA só entra com medição por cima.** Três decisões da Fase 6 (D4.1, D5.1,
   D6.1) foram recusadas pelos próprios gatilhos. Propor IA sem número é propor no vazio.
3. **Simplicidade e desacoplamento.** Monólito modular, sem complexidade prematura.
4. **Evolução incremental.** Toda decisão do MVP tem caminho de evolução documentado em ADR.
5. **Documentação como fonte de verdade.** Inconsistência entre doc e código deve ser
   sinalizada, documentada e corrigida.
6. **Acessível e observável por padrão.**

## Decisões fundacionais

| Tema | Decisão | ADR |
| --- | --- | --- |
| Dados | Dataset seed curado, sem scraping. Listagem do Apify mais enriquecimento pela API do Mercado Livre | [0001](../adr/0001-aquisicao-de-dados.md), [0009](../adr/0009-enriquecimento-pela-api-e-identidade-do-produto.md) |
| Datastore | Postgres-only (FTS mais pgvector) no Supabase; Qdrant e OpenSearch atrás de interface | [0002](../adr/0002-datastore-postgres-only.md) |
| Arquitetura | Monólito modular FastAPI mais worker; sem API Gateway nem microserviços | [0003](../adr/0003-monolito-modular.md) |
| Busca | Retrieval por `SearchProvider`, reordenação por `RankingService` com critérios expostos | [0007](../adr/0007-pipeline-busca-retrieval-ranking.md) |
| IA | LLM apenas offline, na ingestão. Vetorial e híbrido construídos e desligados por medição | [0010](../adr/0010-fase-6-onde-a-ia-entra.md) |
| Deploy | Fly.io em `gru`, Supabase em `sa-east-1`, keep-alive pelo health check, deploy após CI verde | [0011](../adr/0011-deploy-producao-fly-io.md) |
| Qualidade de dados | Oferta com preço implausível é classificada e preservada, nunca corrigida nem apagada | [0012](../adr/0012-qualidade-de-ofertas-na-ingestao.md) |
| Licença | Business Source License 1.1, converte para Apache 2.0 em 2030-07-01 | [0006](../adr/0006-licenciamento-busl.md) |

## Stack

- **Frontend:** Next.js 14, TypeScript, Tailwind, shadcn/ui
- **Backend:** FastAPI, monólito modular (`catalog`, `search`, `ai`, `core`)
- **Dados:** PostgreSQL com FTS (`unaccent`) e pgvector, no Supabase
- **Worker:** ingestão do seed (raw, normalização, qualidade, validação, upsert)
- **Extensão:** Chrome Manifest V3, cliente fino da mesma API
- **Infra:** Docker Compose em dev; Fly.io, Vercel e Supabase em produção; GitHub Actions

## Escopo

Busca textual, comparação de 2 a 4 produtos, ranking determinístico, catálogo seed
(notebooks e fones), web app e extensão. **Fora:** autenticação, mobile nativo, cashback e
afiliados, scraping automatizado, RAG e agentes em produção.

## Como o sistema funciona

Clientes (web e extensão) chamam **uma** API. A consulta passa pelo `IntentParser`
determinístico, que extrai categoria, teto de preço, atributos e rótulos de `use_case`. O
retrieval aplica os filtros duros no Postgres e devolve um pool limitado. O
`RankingService` reordena em memória e devolve, junto dos itens, os critérios que
justificam cada posição. O worker popula o catálogo.

Contratos que permitem evoluir sem reescrita: `IntentParser`, `SearchProvider`,
`VectorProvider`, `RankingService`, `AIService`, `IngestionSource`.

## Estrutura do repositório

```
CLAUDE.md, AGENTS.md   apontam para .ai/ai.md
.ai/                   contexto para agentes (este diretório)
docs/                  documentação viva (PRD, arquitetura, dados, design, casos de uso)
adr/                   Architecture Decision Records
api/                   backend FastAPI
worker/                ingestão do catálogo seed
frontend/              web app Next.js
extension/             extensão Chrome MV3
infra/                 notas de infraestrutura e runbooks de deploy
scripts/               utilitários de medição
```

## Onde encontrar contexto

Os arquivos em `.ai/` são resumos curtos, feitos para caber em contexto. O detalhe está em
`docs/` e nos ADRs.

| Tema | Resumo | Detalhe |
| --- | --- | --- |
| Produto e requisitos | `.ai/product.md` | [`docs/prd.md`](../docs/prd.md), incluindo o estado de implementação de cada RF |
| Arquitetura | `.ai/architecture.md` | [`docs/architecture.md`](../docs/architecture.md) |
| Modelo de dados | `.ai/data-model.md` | [`docs/data-model.md`](../docs/data-model.md) |
| Design system | `.ai/design-system.md` | [`docs/design-system.md`](../docs/design-system.md) |
| Convenções de engenharia | `.ai/conventions.md` | |
| Glossário | `.ai/glossary.md` | |
| Decisões | | [`adr/README.md`](../adr/README.md) |

## Base de conhecimento

A documentação canônica vive no
[Notion](https://marmalade-linen-4f8.notion.site/ProductSearcher-3865658dda14806fba0ffe185835ea2f)
e é espelhada aqui. O Notion é a fonte de verdade sobre **estado de tarefas** (Tasks
Tracker); o repositório é a fonte de verdade sobre **o que o código faz**. Ao listar ou
reportar tarefas, consulte o Tasks Tracker do Notion em vez de inferir o backlog a partir
do PRD: o PRD descreve requisitos, não o estado corrente do trabalho.

## Regras para agentes

- Antes de implementar, entenda **por que** algo existe. Vários comportamentos que parecem
  defeito são decisão registrada: a extensão em silêncio fora de cobertura, a busca
  vetorial desligada, `reviews` vazia.
- Não introduza tecnologia sem justificar o benefício e registrar em ADR quando relevante.
- Mantenha o sistema funcionando sem IA.
- Ao mudar comportamento, atualize a documentação no mesmo trabalho, e sinalize
  inconsistências que encontrar pelo caminho.
- Migration nova exige passo manual no banco antes do deploy (ADR-0011 D7). Não existe
  `release_command`.
- Prefira modularidade, testabilidade e observabilidade.

## Armadilhas conhecidas

- **`docker compose up` sobe o banco vazio.** Nada no compose roda migrations. Sem
  `make migrate` e `make seed`, a API responde `[]` e tudo parece quebrado.
- **O job `lint` da CI commita no branch.** Ele aplica `ruff --fix`, `ruff format` e
  `prettier` e faz push. Depois de um push, `git pull` antes de continuar.
- **Escrever em `product_specs.attributes` exige merge (`||`).** Substituir a coluna apaga
  os rótulos de `use_case` e o carimbo de embedding em silêncio.
- **Recarregar o seed apaga a rotulagem de `use_case`.** O runbook de recarga tem o passo de
  re-rotular.
- **`%` na senha do banco quebra duas vezes**, no `configparser` do Alembic e como escape
  percentual na URL. Prefira senha alfanumérica.
