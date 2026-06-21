# Modelo de dados (resumo)

> Esquema **provisório e aberto** (pode ganhar/perder colunas). Detalhe em `docs/data-model.md`.

## Tabelas

- `categories` — categorias de produto
- `category_attribute_schema` — quais specs existem por categoria (specs *category-aware*)
- `brands` — marcas
- `products` — produto base; inclui `search_vector` (tsvector/FTS) e `embedding` (pgvector)
- `product_specs` — specs do produto em **JSONB** (flexível)
- `stores` — lojas/varejistas
- `offers` — oferta de um produto numa loja (preço, link, moeda, timestamp)
- `price_history` — histórico de preço por oferta
- `reviews` — avaliações resumidas (opcional no MVP)
- `searches` — log de buscas (analytics/relevância)

## Princípios

- **Postgres-only**: FTS + pgvector no mesmo banco.
- Specs flexíveis via JSONB, validadas contra `category_attribute_schema`.
- Comparação só entre produtos da **mesma categoria**.
- Sem `users` no MVP (sem auth).
- IDs `uuid`, timestamps `timestamptz`.

## Em aberto

`product_specs` separado vs. embutido em `products`; granularidade de `reviews`; índices (GIN/IVFFlat/HNSW). APIFY como possível fonte futura de `offers`/`price_history`.
