# ADR-0005 — Decisões técnicas da Fase 2 (schema + ingestão)

- **Status:** Aceito
- **Data:** 2026-06-27
- **Decisor:** Erick
- **Relacionado:** ADR-0001, ADR-0002, ADR-0003, ADR-0004

## Contexto

A **Fase 2** entrega o pipeline de dados de ponta a ponta: migrations do schema, índices, interface de ingestão, `category_attribute_schema`, validação de specs, worker de ingestão e o **dataset seed curado** (~150 produtos, 2 categorias). Várias dessas tasks compartilham contratos — a migration define o schema que o worker escreve; a validação lê o `category_attribute_schema`; o seed precisa do formato dos atributos.

O schema é **provisório e aberto** (ver Modelagem de Dados), mas a Fase 2 exige **congelar um v1** dessas decisões transversais, senão cada pessoa trabalha contra um alvo móvel — gerando retrabalho e handoffs no pior ponto da cadeia. Este ADR agrupa as decisões que **bloqueiam mais de uma task** e precisam estar fechadas antes de codar.

Restrições herdadas: **free-tier**, **Postgres-only** (ADR-0002), **IA opcional e desacoplada** (o caminho crítico opera sem OpenAI/Gemini/Claude), **monólito modular** com dependências externas atrás de interfaces (ADR-0003), documentação em PT e código em inglês.

## Decisão

| # | Tema | Decisão | Bloqueia |
| --- | --- | --- | --- |
| D1 | Ferramenta de migrations | **Alembic** | Migrations, índices |
| D2 | Dimensão do embedding | **`vector(768)`** — modelo open-source multilíngue local (e5-base / nomic) | Migrations, índice vetorial |
| D3 | Chave natural de upsert | **`products.slug`** (UNIQUE existente) | Worker (idempotência) |
| D4 | `data_type` em `category_attribute_schema` | **`text`, `number`, `boolean`, `enum`** | Schema de atributos, validação, seed |
| D5 | Formato do dataset seed | **YAML versionado** em `data/seed/` | Seed |
| D6 | Falha na validação de specs | **Rejeita, loga e segue** (pula o registro inválido) | Validação, worker |

### D1 — Ferramenta de migrations: Alembic

Versionar o schema com **Alembic**, par natural do SQLAlchemy já adotado no módulo `catalog`. Migrations versionadas e reprodutíveis via `make`; autogenerate a partir dos models reduz divergência código↔banco.

**Alternativas descartadas:** SQL puro versionado (mais controle, porém manual e sem autogenerate — maior risco de drift); ORM aplicando schema direto via `create_all` (não versiona evolução).

### D2 — Dimensão do embedding: `vector(768)`

`products.embedding` será **`vector(768)`**, alimentada por um **modelo open-source multilíngue executado localmente** (classe e5-base / nomic). A dimensão é fixada na migration mesmo com a IA desligada. O eixo decisivo não é qualidade marginal, e sim **dependência**: modelos locais mantêm o sistema autônomo, coerente com "IA opcional/desacoplada". 768 dá margem de qualidade sobre 384 sem custo de vendor e folgado no free-tier (~3 KB/produto); multilíngue é necessário pois produtos e buscas são em PT-BR.

**Alternativas descartadas:** `vector(384)` (mais enxuto e suficiente, mas optou-se por margem de qualidade); `vector(1536)` OpenAI (API paga que amarra a OpenAI — conflita com IA desacoplada).

### D3 — Chave natural de upsert: `products.slug`

O upsert idempotente do worker usa **`products.slug`** (já `UNIQUE`) como chave de conflito (`ON CONFLICT (slug) DO UPDATE`). O slug deve ser derivado de forma determinística (marca + modelo normalizados). Rodar o seed N vezes converge ao mesmo estado.

**Alternativas descartadas:** chave composta `(category_id, brand_id, model)` (exige marca/modelo sempre presentes e normalizados); id externo da fonte (o seed curado não tem id estável — reavaliar quando entrar fonte externa).

### D4 — `data_type` em `category_attribute_schema`: `text`, `number`, `boolean`, `enum`

Conjunto fechado: **`text`, `number`, `boolean`, `enum`**. `enum` carrega lista de valores permitidos; `number` usa `unit` para a unidade (GB, polegadas). Cobre as specs de notebooks e fones com validação efetiva e baixa complexidade; conjunto fechado evita texto livre não validável.

**Alternativas descartadas:** só `text/number/boolean` (sem enum, valores fechados viram texto livre); conjunto rico (+ `array`, `range`) — complexidade cedo demais, estender sob demanda.

### D5 — Formato do dataset seed: YAML versionado

O seed curado vive como **YAML versionado** em `data/seed/`, com os specs já no formato do `category_attribute_schema` (mapeados para `product_specs.attributes` em JSONB). Legível para curadoria manual e revisável em PR.

**Alternativas descartadas:** JSON (casa 1:1 com JSONB, mas menos amigável de editar à mão — alternativa aceitável); CSV (inadequado para specs aninhadas/variáveis).

### D6 — Falha na validação de specs: rejeita, loga e segue

Quando um registro falha na validação de specs obrigatórias, o worker **rejeita aquele registro, registra o motivo em log e continua o lote**. Para um seed curado, um item malformado não deve derrubar a ingestão; o log dá rastreabilidade.

**Alternativas descartadas:** fail-fast (um item quebrado trava a carga inteira); quarentena em tabela à parte (mais observável, mas exige tabela/fluxo extra — caminho de evolução natural).

## Consequências negativas

Congelar um v1 sobre um schema "aberto" cria custo de mudança: alterar D2 (dimensão) ou D3 (chave) depois exige recriar coluna/índice e reprocessar o seed. `vector(768)` consome ~2x o storage/índice de 384 (irrelevante agora). `enum` (D4) exige manter listas de valores permitidos. "Rejeita e segue" (D6) pode mascarar problemas se os logs não forem monitorados.

## Caminho de evolução / gatilho de revisão

**D2:** revisar dimensão/modelo se a qualidade semântica não satisfizer ou o catálogo escalar — encapsulado por `VectorProvider` (ADR-0002). **D3:** ao introduzir fonte externa via `IngestionSource` (APIFY/API), reavaliar id externo como chave. **D4:** estender tipos (`array`, `range`) sob demanda. **D6:** migrar para quarentena quando o volume justificar revisão assíncrona. Gatilhos gerais: metas de latência (RNF-01), recall insatisfatório, crescimento do catálogo, entrada de fontes externas.

## Impacto futuro

**Código:** `catalog/models.py` mapeia as tabelas com `embedding vector(768)`; surge `migrations/` (Alembic); o worker implementa upsert por `slug` e o ciclo `raw → normalização → validação → upsert`. **Dados:** `data/seed/` em YAML; índices GIN (FTS/JSONB) e vetorial (IVFFlat/HNSW). **Interfaces:** `IngestionSource` permanece agnóstica à fonte. **Relacionado:** ADR-0001, ADR-0002, ADR-0003.
