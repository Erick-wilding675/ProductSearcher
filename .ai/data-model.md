# Modelo de dados (resumo)

> Resumo para contexto rápido. Detalhe em [`docs/data-model.md`](../docs/data-model.md).

## Tabelas

| Tabela | Conteúdo |
| --- | --- |
| `categories` | Categorias de produto |
| `category_attribute_schema` | Quais specs existem por categoria, com tipo, unidade, valores permitidos e obrigatoriedade |
| `brands` | Marcas |
| `products` | Produto base, com `search_vector` (tsvector) e `embedding` (pgvector, 768 dimensões) |
| `product_specs` | Specs em JSONB |
| `stores` | Lojas e varejistas |
| `offers` | Oferta de um produto numa loja, com `quality_status` e `quality_reason` |
| `price_history` | Histórico de preço por oferta |
| `reviews` | Avaliações resumidas; vazia por decisão no MVP |
| `searches` | Log de buscas (analytics e relevância) |

## Princípios

- Postgres-only: FTS e pgvector no mesmo banco.
- Specs flexíveis em JSONB, validadas contra `category_attribute_schema`.
- Comparação só entre produtos da mesma categoria.
- Sem `users`: não há autenticação.
- IDs `uuid`, timestamps `timestamptz`.

## `product_specs.attributes` tem três donos

Specs da ficha técnica (ingestão), `use_case` (rotulagem offline por LLM, ADR-0010 D2) e
`_embedding` (carimbo da carga de vetores). **Toda escrita precisa ser merge (`||`), nunca
substituição:** substituir a coluna apaga o trabalho dos outros donos sem erro e sem log.
Já aconteceu em produção e deixou "notebook gamer" voltando vazio.

## Qualidade de ofertas

`quality_status` vale `valid` ou `rejected`. A triagem é estatística, por categoria, na
ingestão; nada é corrigido nem apagado. Busca, detalhe e comparação filtram por `valid`.
Ver [ADR-0012](../adr/0012-qualidade-de-ofertas-na-ingestao.md).

## Estado

`products.embedding` está **vazia** no banco atual (0 de 235, medido em 19/09/2026): a
carga de vetores da Fase 6 ficou no projeto Supabase antigo, que foi substituído em 18/09.
Sem impacto enquanto `vector_enabled=false`, mas ligar a busca vetorial exige rodar
`python -m app.search.vector_load` antes. `searches` recebe escrita a cada busca com texto, sem
identificação de usuário. `reviews` está vazia por decisão: a API do Mercado Livre não
expõe avaliação para token de aplicação.

## Em aberto

Expurgo por idade em `searches`; granularidade de `reviews` quando for povoada; Apify como
fonte futura de `offers` e `price_history`.
