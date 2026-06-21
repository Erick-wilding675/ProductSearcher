# ADR-0002 — Datastore: Postgres-only (FTS + pgvector)

- **Status:** Aceito (MVP)
- **Data:** 2026-06-21
- **Decisor:** Erick

## Contexto

O produto precisa de **busca textual** e, futuramente, **busca vetorial** (semântica). Opções: PostgreSQL (FTS + extensão **pgvector**); OpenSearch/Elasticsearch; bancos vetoriais dedicados (Qdrant, Chroma). Restrições: free-tier, equipe pequena, simplicidade, evitar serviços extras.

## Decisão

Usar **PostgreSQL como único datastore** no MVP: **FTS** para busca textual e **pgvector** para embeddings, provido pelo **Supabase** (free inclui pgvector). Embeddings gerados por **modelo open-source local** (sem custo de API). Acesso encapsulado por **`SearchProvider`** e **`VectorProvider`**.

## Benefícios

- Um único serviço (menos ops, menos pontos de falha, menos custo).
- Gratuito e suficiente para a escala do seed.
- Mantém o princípio "funciona sem IA" (FTS independe de embeddings).
- Demonstra modelagem sólida (bom para portfólio).
- Embeddings locais → sem gasto de API.

## Consequências negativas

- pgvector tem limites de escala/recall frente a bancos vetoriais dedicados.
- FTS do Postgres é menos sofisticado que OpenSearch para relevância avançada/facets.
- Índices (GIN; IVFFlat/HNSW) exigem tuning.

## Alternativas descartadas

| Alternativa | Por que não (agora) |
| --- | --- |
| Qdrant / Chroma (vetorial dedicado) | Serviço extra, mais ops/custo, desnecessário na escala atual. **Atrás de interface.** |
| OpenSearch / Elasticsearch | Forte em relevância/facets, mas pesado/caro para free-tier. **Futuro.** |

## Caminho de evolução / gatilho de revisão

Migrar busca vetorial para **Qdrant** quando volume/recall exigir; adotar **OpenSearch** para relevância avançada/facets em escala. Gatilhos: latência p95 estourando metas (RNF-01), recall insatisfatório, catálogo crescendo ordens de magnitude. As interfaces `SearchProvider`/`VectorProvider` permitem a troca sem reescrever o core.

## Impacto futuro

O schema já prevê `search_vector` (`tsvector`) e `embedding` (`vector`) em `products`; resta definir os índices. Mantém o sistema simples agora e portável depois.
