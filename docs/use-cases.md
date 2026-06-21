# Casos de uso

> Diagramas em Mermaid (renderizados pelo GitHub/Notion). Complementa o [PRD](prd.md).

## Atores

| Ator | Tipo | Descrição |
| --- | --- | --- |
| Consumidor (topo de funil) | Primário | "melhor X para Y"; não decidiu o modelo |
| Comparador | Primário | "A vs B"; já tem candidatos |
| Curador de catálogo | Interno | Mantém o dataset seed |
| Google SERP | Externo | Origem da query da extensão |
| LLM | Externo (opcional) | Explicações quando habilitado |

## Catálogo de casos de uso

| UC | Nome | Ator | RF |
| --- | --- | --- | --- |
| UC-01 | Buscar produtos | Consumidor | RF-10/11/12 |
| UC-02 | Comparar produtos | Comparador | RF-20/21/22 |
| UC-03 | Ver ranking explicado | Consumidor | RF-30/31 |
| UC-04 | Ver detalhe do produto | Consumidor/Comparador | RF-42 |
| UC-05 | Assistência contextual (extensão) | Consumidor | RF-50/51/52 |
| UC-06 | Curar catálogo (seed) | Curador | RF-70/71/72 |
| UC-07 | Explicar recomendação via IA | Consumidor | RF-61 |

## Diagrama de casos de uso

```mermaid
flowchart LR
  consumidor["👤 Consumidor"]
  comparador["👤 Comparador"]
  curador["👤 Curador"]
  google["🔎 Google SERP"]
  llm["🤖 LLM (opcional)"]
  subgraph PS["ProductSearcher"]
    UC01(["UC-01 Buscar"])
    UC02(["UC-02 Comparar"])
    UC03(["UC-03 Ranking"])
    UC04(["UC-04 Detalhe"])
    UC05(["UC-05 Assistência contextual"])
    UC06(["UC-06 Curar catálogo"])
    UC07(["UC-07 Explicar (IA)"])
  end
  consumidor --> UC01
  consumidor --> UC04
  consumidor --> UC05
  comparador --> UC02
  comparador --> UC04
  curador --> UC06
  google --> UC05
  UC01 -. include .-> UC03
  UC05 -. include .-> UC01
  UC03 -. extend .-> UC07
  UC07 --> llm
```

## UC-01 — Buscar produtos

```mermaid
sequenceDiagram
  actor U as Consumidor
  participant W as Web App
  participant API as API
  participant P as Intent Parser
  participant S as Search (Postgres)
  participant R as Ranking
  U->>W: "melhor notebook até R$5000"
  W->>API: GET /search?q=...
  API->>P: extrair intenção
  P-->>API: categoria, preço_max, atributos
  API->>S: consulta FTS
  S-->>API: candidatos
  API->>R: ordenar
  R-->>API: ranking + critérios
  API-->>W: resultados
  W-->>U: lista rankeada
```

## UC-02 — Comparar produtos

```mermaid
sequenceDiagram
  actor U as Comparador
  participant W as Web App
  participant API as API
  participant C as Catálogo
  U->>W: seleciona 2-4 / "A vs B"
  W->>API: POST /compare {ids}
  API->>C: specs por id
  C-->>API: specs
  API->>API: alinhar + destacar diferenças
  API-->>W: tabela comparativa
  W-->>U: comparação
```

## UC-05 — Assistência contextual (extensão)

```mermaid
sequenceDiagram
  actor U as Usuário
  participant G as Google SERP
  participant E as Extensão
  participant API as API
  participant P as Intent Parser
  participant S as Search + Ranking
  U->>G: "melhor fone bluetooth"
  G-->>E: query na URL
  E->>API: GET /search?q=...
  API->>P: extrair categoria
  alt categoria coberta
    P-->>API: válida
    API->>S: buscar + rankear
    S-->>API: top-N
    API-->>E: resultados
    E-->>U: popup na SERP
  else não coberta
    API-->>E: vazio
    E-->>U: silêncio
  end
```

## UC-06 — Curar catálogo (ingestão)

```mermaid
sequenceDiagram
  actor C as Curador
  participant F as Seed files
  participant WK as Worker
  participant V as Validação
  participant DB as Postgres
  C->>F: edita produtos/specs/ofertas
  C->>WK: roda pipeline
  WK->>WK: raw -> normalização
  WK->>V: validar specs
  alt válido
    V-->>WK: ok
    WK->>DB: upsert idempotente
    DB-->>WK: ok
  else inválido
    V-->>WK: erros
    WK-->>C: itens sinalizados
  end
```
