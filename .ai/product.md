# Produto (resumo)

> Resumo para contexto rápido. Detalhe em [`docs/prd.md`](../docs/prd.md), que inclui o
> estado de implementação de cada requisito.

## Problema

Descobrir o que comprar é fragmentado: o usuário cruza busca, reviews, fóruns,
marketplaces e avaliações, gastando horas. A oportunidade é dar resposta rápida,
contextualizada e verificável.

## Proposta

Plataforma de descoberta de produtos, não um chatbot e não um marketplace. Interpreta a
consulta, encontra produtos, rankeia com critérios expostos e compara.

## Personas

- **Consumidor topo de funil:** "melhor X para Y", ainda não escolheu o modelo.
- **Comparador:** "A vs B", já tem candidatos.
- **Curador de catálogo (interno):** mantém o dataset seed.

## Casos de uso

UC-01 Buscar · UC-02 Comparar · UC-03 Ranking explicado · UC-04 Detalhe ·
UC-05 Assistência contextual (extensão) · UC-06 Curar catálogo · UC-07 Explicação por IA.
Ver [`docs/use-cases.md`](../docs/use-cases.md).

## Prioridades (MoSCoW)

- **Must:** catálogo seed, busca textual com parser determinístico, comparação, ranking,
  web app, extensão, deploy público. Todos entregues.
- **Should:** histórico de preço, paginação e ordenação, detalhe de produto, CI/CD e
  acessibilidade, entregues. Busca semântica construída e desligada por medição.
- **Could:** explicação por LLM (recusada por medição), autocomplete e score ajustável
  (não construídos), publicação na Web Store (em aberto).
- **Won't:** RAG e agentes em produção, ingestão por scraping, autenticação, mobile nativo.

## Métricas

| Métrica | Alvo | Estado |
| --- | --- | --- |
| Latência de busca | p95 abaixo de 500 ms server-side | Medição externa com mediana de 349 ms; p95 server-side pendente |
| Relevância | 80% ou mais das queries de teste com o produto esperado no top-5 | 100% de cobertura@5 e 68% de precisão@5 na suíte da Fase 6 |
| Cobertura de catálogo | 2 categorias, 150 produtos ou mais | 235 produtos em 2 categorias |
| Disponibilidade | Sem cold start perceptível | `auto_stop_machines=false` mais health check a cada 30 s |
