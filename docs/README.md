# Documentação do ProductSearcher

Documentação viva do projeto. Espelha e versiona, junto ao código, o conhecimento que
também vive no Notion.

> **Base de conhecimento:** [ProductSearcher no Notion](https://marmalade-linen-4f8.notion.site/ProductSearcher-3865658dda14806fba0ffe185835ea2f)
>
> O hub do Notion concentra o Document Hub (PRD, ADRs, arquitetura, design), o Tasks
> Tracker e a base de Comunicados. Ele é a fonte de verdade sobre **estado de tarefas**;
> os arquivos abaixo são a fonte de verdade sobre **o que o código faz**. Os ADRs do
> Notion usam numeração de três dígitos (ADR-006) e os do repositório, quatro
> (`adr/0006-*.md`); é o mesmo documento.

## Especificação

| Documento | Conteúdo |
| --- | --- |
| [prd.md](prd.md) | Requisitos funcionais e não-funcionais priorizados por MoSCoW, métricas de sucesso, regras de negócio e o estado de implementação de cada RF |
| [use-cases.md](use-cases.md) | Atores, catálogo de casos de uso (UC-01 a UC-07) e diagramas de sequência |
| [wireframes.md](wireframes.md) | Telas do MVP, o que cada uma cobre e o que ficou fora |

## Arquitetura e dados

| Documento | Conteúdo |
| --- | --- |
| [architecture.md](architecture.md) | Camadas, módulos da API, contratos de interface, endpoints e como os RNFs são atendidos |
| [data-model.md](data-model.md) | Esquema relacional, specs em JSONB, colunas derivadas e o que está intencionalmente vazio |
| [plano-dados-completos.md](plano-dados-completos.md) | Levantamento de 2026-08-09 sobre a completude do catálogo em produção, com as quatro decisões que saíram dele |
| [`../adr/README.md`](../adr/README.md) | Índice dos Architecture Decision Records, com status |

## Design

| Documento | Conteúdo |
| --- | --- |
| [design-system.md](design-system.md) | Paleta violet, neutros, semânticas, tokens light/dark, tipografia, forma e acessibilidade |

## Documentação por módulo

Cada diretório de código tem o seu próprio README, com o que é específico dele:

- [`../api/README.md`](../api/README.md) e [`../api/README-vector.md`](../api/README-vector.md)
- [`../worker/README.md`](../worker/README.md), [`../worker/seed/README.md`](../worker/seed/README.md) e [`../worker/tools/seedbuilder/README.md`](../worker/tools/seedbuilder/README.md)
- [`../frontend/README.md`](../frontend/README.md)
- [`../extension/README.md`](../extension/README.md)
- [`../infra/README.md`](../infra/README.md) e [`../infra/deploy/README.md`](../infra/deploy/README.md)

## Contexto para agentes de IA

[`../.ai/ai.md`](../.ai/ai.md) é o ponto de entrada. `CLAUDE.md` e `AGENTS.md` na raiz
apontam para ele. Os arquivos em `.ai/` são resumos curtos, feitos para caber em uma
janela de contexto; o detalhe está aqui em `docs/`.

## Documentos de origem (discovery)

- [`../product-vision.md`](../product-vision.md), visão inicial do produto
- [`../architecture-proposal.md`](../architecture-proposal.md), proposta inicial de arquitetura

Os dois foram o ponto de partida e não são mantidos. O conteúdo consolidado e revisado
está nos documentos acima; quando divergirem, valem os documentos acima.
