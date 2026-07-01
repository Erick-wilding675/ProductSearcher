# ADR-0005 — Decisões técnicas da Fase 2 (schema + ingestão)

- **Status:** Proposto (a ratificar no backlog da Fase 2)
- **Data:** 2026-06-27
- **Decisor(es):** Erick (arquiteto). A confirmar: Sofia Carvalho, Pedro Faria.

## Contexto

A Fase 2 entrega o pipeline de dados de ponta a ponta: migrations do schema, índices, interface de ingestão, `category_attribute_schema`, validação de specs, worker de ingestão e o dataset seed curado (~150 produtos, 2 categorias). Várias dessas tasks compartilham contratos: a migration define o schema que o worker escreve; a validação lê o `category_attribute_schema`; o seed precisa do formato dos atributos.

O schema é "provisório e aberto" (ver `docs/data-model.md`), mas a Fase 2 exige **congelar um v1** dessas decisões transversais — caso contrário cada pessoa trabalha contra um alvo móvel e cria-se retrabalho e handoffs no pior ponto da cadeia. Este ADR agrupa as decisões que **bloqueiam mais de uma task** e precisam estar fechadas antes de começar a codar.

Restrições herdadas: free-tier, Postgres-only (ADR-0002), IA opcional e desacoplada (o caminho crítico opera sem OpenAI/Gemini/Claude), monólito modular com dependências externas atrás de interfaces (ADR-0003), documentação em PT e código em inglês.

## Decisão

| # | Tema | Decisão | Bloqueia |
| --- | --- | --- | --- |
| D1 | Ferramenta de migrations | **Alembic** *(recomendado — ratificar)* | Migrations, índices |
| D2 | Dimensão do embedding | **`vector(768)`** — modelo open-source multilíngue local (e5-base / nomic) | Migrations, índice vetorial |
| D3 | Chave natural de upsert | **`products.slug`** (UNIQUE existente) | Worker (idempotência) |
| D4 | `data_type` permitidos em `category_attribute_schema` | **`text`, `number`, `boolean`, `enum`** | Schema de atributos, validação, seed |
| D5 | Formato do dataset seed | **YAML versionado** em `data/seed/` *(recomendado — ratificar)* | Seed |
| D6 | Falha na validação de specs | **Rejeita, loga e segue** (pula o registro inválido) | Validação, worker |

---

### D1 — Ferramenta de migrations: Alembic

**Decisão.** Versionar o schema com **Alembic**, par natural do SQLAlchemy já adotado no módulo `catalog` (`api/app/catalog/models.py`, hoje stub). Migrations versionadas e reprodutíveis via `make`.

**Por quê.** Autogenerate a partir dos models reduz divergência entre código e banco; histórico de migrations dá reprodutibilidade (prioridade do projeto); integra ao fluxo Python/`make` existente.

**Alternativas descartadas.**

| Alternativa | Por que não (agora) |
| --- | --- |
| SQL puro versionado (arquivos `.sql` numerados) | Mais controle e transparência, porém trabalho manual e sem autogenerate; maior risco de drift código↔banco. |
| ORM aplicando schema direto (`create_all`) | Não versiona evolução; inviável para mudanças incrementais e ambientes múltiplos. |

### D2 — Dimensão do embedding: `vector(768)`

**Decisão.** A coluna `products.embedding` será **`vector(768)`**, alimentada por um **modelo de embedding open-source multilíngue executado localmente** (classe e5-base / nomic). A dimensão é fixada na migration mesmo com a IA desligada.

**Por quê.** O eixo decisivo não é qualidade marginal, e sim **dependência**: modelos locais 384/768 mantêm o sistema autônomo, coerente com "IA opcional/desacoplada"; 768 dá margem de qualidade semântica sobre 384 sem custo de vendor e ainda folgado no free-tier (~3 KB/produto). Multilíngue é necessário porque produtos e buscas são em PT-BR. A busca FTS segue como caminho crítico; o vetor é complementar.

**Alternativas descartadas.**

| Alternativa | Por que não (agora) |
| --- | --- |
| `vector(384)` (e5-small) | Mais enxuto e suficiente, mas optou-se por margem de qualidade do 768 a custo de storage ainda irrelevante nesta escala. |
| `vector(1536)` (OpenAI text-embedding-3-small) | API paga que amarra a OpenAI — conflita com o princípio de operar sem IA externa; maior storage/índice. |

### D3 — Chave natural de upsert: `products.slug`

**Decisão.** O upsert idempotente do worker usa **`products.slug`** (já `UNIQUE` no modelo) como chave de conflito. O slug deve ser derivado de forma determinística (ex.: marca + modelo normalizados).

**Por quê.** Reaproveita restrição já existente, menos peças móveis; rodar o seed N vezes converge ao mesmo estado. Não depende de id externo, que o seed curado não possui de forma estável.

**Alternativas descartadas.**

| Alternativa | Por que não (agora) |
| --- | --- |
| Chave composta `(category_id, brand_id, model)` | Robusta, mas exige marca e modelo sempre presentes e normalizados em todo registro. |
| ID externo da fonte de ingestão | Bom para fontes futuras (APIFY/API), mas o seed não tem id externo estável — frágil agora. **Reavaliar quando entrar fonte externa.** |

### D4 — `data_type` em `category_attribute_schema`: `text`, `number`, `boolean`, `enum`

**Decisão.** O `category_attribute_schema.data_type` aceita um conjunto fechado: **`text`, `number`, `boolean`, `enum`**. `enum` carrega lista de valores permitidos; `number` usa `unit` para a unidade (ex.: GB, polegadas).

**Por quê.** Cobre as specs de notebooks e fones (RAM = `number`, Bluetooth = `boolean`, tipo de painel/driver = `enum`) com validação efetiva e baixa complexidade. Conjunto fechado evita texto livre não validável e mantém consistência na curadoria.

**Alternativas descartadas.**

| Alternativa | Por que não (agora) |
| --- | --- |
| Só `text`, `number`, `boolean` | Sem `enum`, valores fechados viram texto livre — menos validável e mais sujeito a inconsistência. |
| Conjunto rico (+ `array`, `range`) | Cobre specs multivalor e faixas, mas adiciona complexidade de validação cedo demais. **Estender sob demanda.** |

### D5 — Formato do dataset seed: YAML versionado

**Decisão.** O seed curado (~150 produtos, 2 categorias) vive como **YAML versionado** em `data/seed/`, com os specs já no formato do `category_attribute_schema`.

**Por quê.** Legibilidade para curadoria manual e conforto com specs aninhadas (mapeadas para `product_specs.attributes` em JSONB). Versionado no git → reprodutível e revisável em PR.

**Alternativas descartadas.**

| Alternativa | Por que não (agora) |
| --- | --- |
| JSON | Casa 1:1 com JSONB e dispensa parser extra, mas é menos amigável de editar à mão. Aceitável como alternativa. |
| CSV | Inadequado para specs aninhadas/variáveis por categoria. |

### D6 — Falha na validação de specs: rejeita, loga e segue

**Decisão.** Quando um registro falha na validação de specs obrigatórias, o worker **rejeita aquele registro, registra o motivo em log e continua o lote**.

**Por quê.** Para um seed curado, um item malformado não deve derrubar toda a ingestão; o log dá rastreabilidade para correção. Mantém o pipeline robusto e idempotente.

**Alternativas descartadas.**

| Alternativa | Por que não (agora) |
| --- | --- |
| Fail-fast (aborta o lote no 1º erro) | Garante 100% válido, mas um único item quebrado trava a carga inteira. |
| Quarentena (tabela à parte) | Mais observável, porém exige tabela e fluxo extra já na Fase 2. **Caminho de evolução natural.** |

---

## Consequências negativas

- Congelar um v1 sobre um schema declarado "aberto" cria custo de mudança: alterar D2 (dimensão) ou D3 (chave) depois exige recriar coluna/índice e reprocessar o seed.
- `vector(768)` consome ~2x o storage/índice de 384 — irrelevante agora, relevante se o catálogo crescer ordens de magnitude.
- `enum` (D4) exige manter listas de valores permitidos por atributo, com manutenção conforme novas categorias entram.
- "Rejeita e segue" (D6) pode mascarar problemas sistêmicos de qualidade se os logs não forem monitorados.
- Alembic (D1) e YAML (D5) seguem como recomendação até a ratificação no backlog.

## Alternativas descartadas

Detalhadas por decisão acima (D1–D6).

## Caminho de evolução / gatilho de revisão

- **D2 (embedding):** revisar dimensão/modelo se a qualidade de busca semântica não satisfizer ou se o catálogo escalar (storage/recall). Encapsulado por `VectorProvider` (ADR-0002), permitindo troca sem reescrever o core.
- **D3 (chave de upsert):** ao introduzir fonte externa via `IngestionSource` (APIFY/API), reavaliar uso de id externo como chave.
- **D4 (tipos):** estender o conjunto (`array`, `range`) sob demanda quando surgirem specs multivalor.
- **D6 (validação):** migrar para quarentena quando houver volume/erros que justifiquem revisão assíncrona.
- Gatilhos gerais: metas de latência (RNF-01), recall insatisfatório, crescimento do catálogo, entrada de fontes de dados externas.

## Impacto futuro

- **Código:** `catalog/models.py` mapeia as tabelas com `embedding vector(768)`; surge `migrations/` (Alembic); o worker implementa upsert por `slug` e o ciclo `raw → normalização → validação → upsert`; a validação consome o conjunto de `data_type` de D4.
- **Dados:** `data/seed/` em YAML; índices GIN (FTS/JSONB) e vetorial (IVFFlat/HNSW) sobre as colunas já previstas.
- **Interfaces:** `IngestionSource` permanece agnóstica à fonte, isolando o seed atual de fontes futuras.
- **Relacionado:** ADR-0001 (aquisição de dados), ADR-0002 (Postgres-only), ADR-0003 (monólito modular).
