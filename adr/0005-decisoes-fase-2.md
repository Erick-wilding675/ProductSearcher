# ADR-0005 — Decisões técnicas da Fase 2 (schema + ingestão)

- **Status:** Aceito
- **Data:** 2026-06-27 (atualizado em 2026-07-08 após a implementação)
- **Decisor:** Erick
- **Relacionado:** ADR-0001, ADR-0002, ADR-0003, ADR-0004

## Contexto

A **Fase 2** entrega o pipeline de dados de ponta a ponta: migrations do schema, índices, interface de ingestão, `category_attribute_schema`, validação de specs, worker de ingestão e o **dataset seed curado**. Várias dessas tasks compartilham contratos — a migration define o schema que o worker escreve; a validação lê o `category_attribute_schema`; o seed precisa do formato dos atributos.

O schema é **provisório e aberto** (ver Modelagem de Dados), mas a Fase 2 exige **congelar um v1** dessas decisões transversais, senão cada pessoa trabalha contra um alvo móvel. Este ADR agrupa as decisões que **bloqueiam mais de uma task** e precisam estar fechadas antes de codar.

Restrições herdadas: **free-tier**, **Postgres-only** (ADR-0002), **IA opcional e desacoplada**, **monólito modular** com dependências externas atrás de interfaces (ADR-0003), documentação em PT e código em inglês.

## Decisão

| # | Tema | Decisão | Bloqueia |
| --- | --- | --- | --- |
| D1 | Ferramenta de migrations | **Alembic** | Migrations, índices |
| D2 | Dimensão do embedding | **`vector(768)`** — modelo open-source multilíngue local (e5-base / nomic) | Migrations, índice vetorial |
| D3 | Chave natural de upsert | **`products.slug`** (UNIQUE existente) | Worker (idempotência) |
| D4 | `data_type` em `category_attribute_schema` | **`text`, `number`, `boolean`, `enum`** | Schema de atributos, validação, seed |
| D5 | Formato e local do dataset seed | **YAML versionado** em **`worker/seed/`** | Seed |
| D6 | Falha na validação de specs | **Rejeita, loga e segue** (pula o registro inválido) | Validação, worker |
| D7 | Geração de UUID | **Na aplicação** (`uuid4` no worker) | Worker (load) |
| D8 | `search_vector` | **Coluna GERADA** (`to_tsvector('portuguese', …)` STORED) | Busca (Fase 3) |
| D9 | Obrigatoriedade de `screen_in` (notebooks) | **Opcional** — tela vem da API do ML (fallback de título é conservador) | Seed, validação |

### D1 — Ferramenta de migrations: Alembic

Versionar o schema com **Alembic**, par natural do SQLAlchemy. Migrations versionadas e reprodutíveis. O `env.py` lê `DATABASE_URL` do ambiente (produção/Supabase ou dev fora do Docker), com o `alembic.ini` só como fallback — sem credencial versionada.

**Alternativas descartadas:** SQL puro versionado (manual, sem autogenerate); `create_all` (não versiona evolução).

### D2 — Dimensão do embedding: `vector(768)`

`products.embedding` será **`vector(768)`**, alimentada por **modelo open-source multilíngue local**. Fixada na migration mesmo com a IA desligada. 768 dá margem sobre 384 sem custo de vendor e folgado no free-tier; multilíngue porque produtos e buscas são em PT-BR.

**Alternativas descartadas:** `vector(384)` (suficiente, mas menos margem); `vector(1536)` OpenAI (API paga que amarra a OpenAI).

### D3 — Chave natural de upsert: `products.slug`

O upsert idempotente usa **`products.slug`** como chave de conflito (`ON CONFLICT (slug) DO UPDATE`). O slug é derivado de forma determinística (marca + modelo normalizados; cai para marca + nome se não houver modelo). Rodar o seed N vezes converge ao mesmo estado. O mesmo vale para `brands`/`categories`/`stores` (por `slug`), `product_specs` (por `product_id`) e `offers` (por `(product_id, store_id)`).

**Alternativas descartadas:** chave composta `(category_id, brand_id, model)`; id externo da fonte (o seed curado não tem id estável — reavaliar com fonte externa).

### D4 — `data_type` em `category_attribute_schema`: `text`, `number`, `boolean`, `enum`

Conjunto fechado. `enum` carrega `allowed_values`; `number` usa `unit`. Cobre notebooks e fones com validação efetiva e baixa complexidade.

**Alternativas descartadas:** só `text/number/boolean` (sem enum); conjunto rico (+ `array`, `range`) — complexidade cedo demais.

### D5 — Formato e local do dataset seed: YAML em `worker/seed/`

O seed curado vive como **YAML versionado** em **`worker/seed/products/*.yaml`**, com os specs já no formato do `category_attribute_schema` (mapeados para `product_specs.attributes` em JSONB). O `category_attribute_schema` fica em `worker/seed/categories.json`.

> **Nota (2026-07-08):** a decisão original apontava `data/seed/`. Ajustado para **`worker/seed/`** porque o seed é a entrada do worker e precisa estar no contexto de build do container (`worker/Dockerfile`); `data/seed/` na raiz ficaria fora do `COPY` do worker.

**Alternativas descartadas:** JSON (casa 1:1 com JSONB, mas menos amigável de editar à mão — usado só para o schema de categorias); CSV (inadequado para specs aninhadas).

### D6 — Falha na validação de specs: rejeita, loga e segue

Registro que falha na validação de specs (ou de normalização — sem marca, preço inválido) é **rejeitado, logado e o lote continua**. Para um seed curado, um item malformado não deve derrubar a ingestão.

**Alternativas descartadas:** fail-fast; quarentena em tabela à parte (evolução natural quando o volume justificar).

### D7 — Geração de UUID: na aplicação

As colunas `id` não têm `server_default`; o worker gera **`uuid4`** ao inserir. Em conflito (upsert), o `id` existente é preservado. Evita depender de `pgcrypto`/`gen_random_uuid()` no banco e mantém a migration original intacta.

**Alternativas descartadas:** `server_default gen_random_uuid()` (exigiria alterar a migration inicial já aplicada; adiável).

### D8 — `search_vector` como coluna gerada

`products.search_vector` passa a ser **`GENERATED ALWAYS AS (to_tsvector('portuguese', name || model || description)) STORED`** — sempre coerente, sem trigger nem escrita pelo worker. Alimenta o índice GIN de FTS (usado na Fase 3).

**Alternativas descartadas:** trigger (mais partes móveis); popular no worker (acopla ingestão à busca).

### D9 — `screen_in` opcional e cobertura de specs do seed

O seed de notebooks é gerado offline pelo seed-builder (ADR-0001) a partir do CSV do Apify. A ficha técnica estruturada vem da **API do ML**; o **parser de título** é fallback determinístico. Medição sobre 79 notebooks reais: CPU 78/79, RAM 76/79, armazenamento 75/79, mas **tela apenas 55/79** — porque a polegada raramente aparece explícita no título e os números soltos (`A15`, `15irx9`, `16 Aurora`) são **código de modelo**, não a tela.

Decisão: **`screen_in` passa a `required: false`** para notebooks. Forçá-la obrigatória com base em título ou (a) rejeitaria ~⅓ do catálogo, ou (b) exigiria adivinhar a tela de códigos de modelo — inventando dado errado, pior que ausente. O parser só extrai a tela de **marcadores confiáveis** (unidade explícita, `Tela N`, decimal `N,N`); o enriquecimento definitivo da tela fica para a **API do ML** (`DISPLAY_SIZE`), coerente com o ADR-0001. Resultado: **74/79 (94%) válidos** por título, sem token. Os 5 restantes têm o título genuinamente incompleto (sem RAM ou armazenamento) e são corretamente rejeitados (D6); podem ser enriquecidos depois via SKU.

**Alternativas descartadas:** manter `screen_in` obrigatória (rejeita muito do catálogo no MVP); heurística de tela por código de modelo (risco alto de dado incorreto).

A mesma lógica vale para **fones**: `battery_h` (horas de bateria) raramente vem no título (cobertura ~17%) → **`battery_h: required=false`**. Já `anc` (boolean) é **sempre preenchido**: ausência de menção a cancelamento de ruído significa `false`, não "desconhecido" — assim o campo nunca rejeita por ausência. A marca vem de uma **lista curada de marcas reconhecíveis** (globais + BR estabelecidas); o long-tail sem-nome é rejeitado de propósito para manter o catálogo credível. O seed-builder também aceita **múltiplos CSVs** por categoria e filtra por `produtoDomainID` + descarta acessórios (suportes, espumas, earpads). Resultado das 4 buscas do Apify (notebook gamer + home office, fone bluetooth + headset gamer): **167 produtos válidos** (96 notebooks, 71 fones).

## Correções de schema aplicadas (migration `c1a2b3d4e5f6`)

Após a migration inicial, uma migration de correções fecha lacunas necessárias para o upsert e a performance:

- `UNIQUE (category_id, attribute_key)` em `category_attribute_schema`, `UNIQUE (product_id)` em `product_specs`, `UNIQUE (product_id, store_id)` em `offers` — habilitam os upserts idempotentes (D3).
- `stores.url` e `offers.url` passam a **nullable** (nem toda loja/oferta traz URL canônica).
- Índices nas FKs (`products.category_id`, `products.brand_id`, `offers.store_id`, `price_history.offer_id`, `reviews.product_id`, `category_attribute_schema.category_id`).
- `search_vector` recriado como coluna gerada (D8).

`price_history` recebe um ponto **apenas quando o preço muda** — reprocessar o mesmo seed não gera histórico duplicado.

## Consequências negativas

Congelar um v1 sobre um schema "aberto" cria custo de mudança: alterar D2 (dimensão) ou D3 (chave) exige recriar coluna/índice e reprocessar. `enum` (D4) exige manter listas de valores. "Rejeita e segue" (D6) pode mascarar problemas se os logs não forem monitorados. UUID na aplicação (D7) significa que inserts fora do worker também precisam gerar o id.

## Caminho de evolução / gatilho de revisão

**D2:** revisar dimensão/modelo se a qualidade semântica não satisfizer — encapsulado por `VectorProvider` (ADR-0002). **D3:** ao introduzir fonte externa (`IngestionSource`), reavaliar id externo como chave. **D4:** estender tipos (`array`, `range`) sob demanda. **D6:** migrar para quarentena quando o volume justificar. **D7:** adotar `gen_random_uuid()` no banco se surgir escrita fora da aplicação. Gatilhos gerais: metas de latência (RNF-01), recall insatisfatório, crescimento do catálogo, entrada de fontes externas.

## Impacto futuro

**Código:** o worker implementa `raw → normalização → validação → upsert` (por `slug`), com UUID na aplicação; `catalog/models.py` mapeará as tabelas na Fase 3 (com `embedding vector(768)`). **Dados:** `worker/seed/` em YAML; índices GIN (FTS/JSONB) e HNSW (vetorial); `search_vector` gerado. **Interfaces:** `IngestionSource` permanece agnóstica à fonte. **Relacionado:** ADR-0001, ADR-0002, ADR-0003.
