# Architecture Decision Records (ADRs)

Registro das decisões arquiteturais do ProductSearcher. Cada ADR documenta **contexto,
decisão, benefícios, consequências, alternativas descartadas** e **caminho de evolução ou
gatilho de revisão**.

| # | Decisão | Status |
| --- | --- | --- |
| [0001](0001-aquisicao-de-dados.md) | Aquisição de dados do catálogo (seed curado) | Aceito |
| [0002](0002-datastore-postgres-only.md) | Datastore: Postgres-only (FTS + pgvector) | Aceito |
| [0003](0003-monolito-modular.md) | Arquitetura de backend: monólito modular | Aceito |
| [0004](0004-deploy-free-tier.md) | Deploy e infraestrutura (free-tier) | Aceito; ponto em aberto fechado pelo 0011 |
| [0005](0005-decisoes-fase-2.md) | Decisões técnicas da Fase 2 (schema e ingestão) | Aceito |
| [0006](0006-licenciamento-busl.md) | Licenciamento: Business Source License 1.1 | Aceito |
| [0007](0007-pipeline-busca-retrieval-ranking.md) | Pipeline de busca: retrieval (`SearchProvider`) e ranking (`RankingService`) | Aceito |
| [0008](0008-cobertura-do-seed-parser-e-specs-opcionais.md) | Cobertura do seed: parser de título e specs opcionais | Aceito; parcialmente revisto pelo 0009 |
| [0009](0009-enriquecimento-pela-api-e-identidade-do-produto.md) | Enriquecimento pela API do Mercado Livre e identidade do produto | Aceito |
| [0010](0010-fase-6-onde-a-ia-entra.md) | Fase 6: onde a IA entra (e onde não entra) | Aceito; fase fechada em 28/08/2026 |
| [0011](0011-deploy-producao-fly-io.md) | Deploy de produção: Fly.io em `gru`, banco em `sa-east-1`, keep-alive por health check | Aceito; executado em 18/09/2026 |
| [0012](0012-qualidade-de-ofertas-na-ingestao.md) | Qualidade de ofertas na ingestão: classificar, não descartar | Aceito |
| [0013](0013-kpi-de-relevancia-fora-da-ci.md) | O KPI de relevância sai da CI enquanto os rótulos não forem reproduzíveis | Aceito, com gatilho de revisão |

## Como ler estes documentos

Os ADRs de fase (0005, 0010, 0011) trazem, além da decisão, um **registro de construção**:
o que foi medido, o que a execução desmentiu e o que foi recusado por não passar no próprio
gatilho. É onde está o raciocínio que não cabe em um commit.

Dois hábitos que valem a leitura, porque se repetem: decisão de IA só entra com medição por
cima (ADR-0010 D4.1, D5.1, D6.1), e toda flag desligada tem um gatilho escrito para ser
religada.

## Convenções

- Novos ADRs seguem o [`template.md`](template.md), com numeração sequencial de quatro
  dígitos.
- Mudança arquitetural relevante gera ADR. Se a decisão substitui outra, a substituída
  ganha nota no topo e status atualizado nesta tabela.
- A mesma decisão existe no Document Hub do
  [Notion](https://marmalade-linen-4f8.notion.site/ProductSearcher-3865658dda14806fba0ffe185835ea2f),
  onde os ADRs são numerados com três dígitos (ADR-006 lá é `0006-*.md` aqui).
