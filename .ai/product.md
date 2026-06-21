# Produto (resumo)

> Resumo de produto para contexto rápido. Detalhe completo em `docs/prd.md`.

## Problema

Descobrir o que comprar é fragmentado: o usuário cruza busca, reviews, fóruns, marketplaces e avaliações, gastando horas. Oportunidade: respostas rápidas, contextualizadas e confiáveis.

## Proposta

Plataforma de **descoberta inteligente de produtos** (não um chatbot, não um marketplace). Compreende intenção, encontra produtos, sintetiza, compara e explica.

## Personas

- **Consumidor topo de funil:** "melhor X para Y", não decidiu o modelo.
- **Comparador:** "A vs B", já tem candidatos.
- **Curador de catálogo (interno):** mantém o dataset seed.

## Casos de uso (ver `docs/use-cases.md`)

UC-01 Buscar · UC-02 Comparar · UC-03 Ranking explicado · UC-04 Detalhe · UC-05 Assistência contextual (extensão) · UC-06 Curar catálogo · UC-07 Explicação via IA (opcional).

## Prioridades (MoSCoW) — destaque

- **Must:** catálogo seed, busca textual + parser determinístico, comparação, ranking, web app, extensão de demonstração, deploy público.
- **Should:** histórico de preço, busca semântica (pgvector), detalhe de produto, CI/CD, acessibilidade.
- **Could:** explicações via LLM, autocomplete, score ponderado.
- **Won't (agora):** RAG/agentes em produção, ingestão por scraping, auth, mobile nativo.

## Métricas de sucesso

Busca p95 < 500ms · ≥80% das queries de teste com o produto esperado no top-5 · ≥150 produtos em 2 categorias · demo pública sem cold start perceptível.
