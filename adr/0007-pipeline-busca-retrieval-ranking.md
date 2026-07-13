# ADR-0007 — Pipeline de busca: retrieval (SearchProvider) + ranking (RankingService)

- **Status:** Aceito
- **Data:** 2026-07-13
- **Decisor(es):** Erick
- **Relacionado:** ADR-0002 (Postgres-only), ADR-0003 (monólito modular)

## Contexto

A Fase 3 entrega a busca. Duas peças convivem no módulo `search` e precisam ter
fronteiras claras, senão viram lógica duplicada:

1. **`SqlSearchRepository`** (já entregue, alimenta `GET /search`): resolve
   FTS + filtros + ordenação + paginação **numa única query SQL**, direto para o
   endpoint. É o caminho pragmático da SERP: rápido, paginado no banco, sem passos
   intermediários.
2. **`SearchProvider` + `RankingService`** (esta decisão): o pipeline **composável e
   explicável** previsto no esqueleto (RF-11/30/31), que consome o `Intent` produzido
   pelo `IntentParser`:

   ```
   query -> IntentParser -> Intent -> SearchProvider.search() -> hits
                                                                   |
                                          RankingService.rank(hits, intent) -> itens + critérios
   ```

O risco é os dois caminhos brigarem pela mesma responsabilidade. Este ADR fixa a
divisão e o contrato entre retrieval e ranking.

Restrições herdadas: **Postgres-only** (ADR-0002), **IA opcional e desacoplada**
(o ranking é determinístico, sem LLM), **dependências externas atrás de interfaces**
(ADR-0003).

## Decisão

**D1 — Duas responsabilidades separadas.**
- `SearchProvider` faz **retrieval**: aplica os **filtros duros** (categoria, marca,
  `price_max` via `HAVING`) e devolve *candidatos* com o score bruto de relevância
  textual (`fts_rank = ts_rank`). Não ordena para o usuário final nem pagina.
- `RankingService` faz **ordenação explicável**: recebe os candidatos e o `Intent` e
  produz a ordem final + os **critérios** que a justificam.

**D2 — Contrato do `hit`.** O retrieval devolve `list[dict]` com
`id, slug, name, category, brand, min_price, fts_rank`. É o formato que o ranking
consome — desacopla ranking da fonte (Postgres hoje; pgvector/OpenSearch depois).

**D3 — Modelo de ranking determinístico** (`DeterministicRanking`): soma ponderada
sobre os fatores **aplicáveis ao intent**, com renormalização dos pesos:
`relevance` 0.6 (fts_rank normalizado no conjunto), `price` 0.3 (aderência ao teto),
`attributes` 0.1 (cobertura dos atributos pedidos). Desempate estável e objetivo
(relevância desc, nome asc, id asc). Mesmo input ⇒ mesma saída.

**D4 — `price_max` é filtro duro no retrieval, refino no ranking.** Itens acima do teto
são cortados pelo `SearchProvider` (`HAVING`); no ranking o preço só desempata entre
elegíveis (mais barato dentro do orçamento pontua mais).

**D5 — `SqlSearchRepository` permanece** como o caminho direto do `GET /search`
enquanto não há `IntentParser`. Quando o parser (Sofia) entrar, o endpoint pode migrar
para o pipeline `IntentParser → SearchProvider → RankingService` sem reescrever o core —
os dois já dividem as mesmas tabelas Core e o mesmo `search_vector` (ADR-0005 D8).

## Benefícios

- **Explicabilidade (RF-31):** cada resultado carrega o porquê da posição (fatores +
  pesos), exigência do produto e diferencial de portfólio.
- **Determinismo/testabilidade:** ranking é função pura, testável sem banco; retrieval
  é testável isolando o SQL.
- **Desacoplamento (ADR-0003):** trocar o datastore afeta só o `SearchProvider`; trocar
  a política de ordenação afeta só o `RankingService`.
- **IA opcional:** o sistema ranqueia bem sem qualquer LLM; IA entra depois como
  reforço atrás das mesmas interfaces.

## Consequências negativas

- **Dois caminhos de busca** coexistem temporariamente (repository direto + pipeline).
  Custo de clareza mitigado por este ADR e pelos docstrings; a convergência é o gatilho
  de revisão abaixo.
- **Ranking em memória:** reordenar candidatos no app assume um **pool limitado**
  (`CANDIDATE_POOL = 50`). Suficiente para o MVP; para catálogos grandes, revisar.
- Pesos do ranking são um **ponto de calibração** — sujeitos à suíte de relevância
  (tarefa da Sofia) para ajuste empírico.

## Alternativas descartadas

| Alternativa | Por que não (agora) |
| --- | --- |
| Só o `SqlSearchRepository` (ranking no SQL) | Ordenação explicável e evolutiva fica presa no SQL; difícil justificar/ajustar e testar isolado |
| Ranking por LLM | Fere o princípio de IA opcional; não determinístico; custo/vendor no free-tier |
| Provider já paginando/ordenando | Confunde retrieval com ranking; impede reordenar por critérios do produto |

## Caminho de evolução / gatilho de revisão

- **Gatilho de convergência:** quando o `IntentParser` existir e a suíte de relevância
  validar os pesos, migrar `GET /search` para o pipeline e **aposentar** o caminho
  direto (ou reduzi-lo a um atalho para consultas sem intent).
- **Gatilho de escala:** se o catálogo crescer a ponto de `CANDIDATE_POOL` cortar
  resultados relevantes, mover parte do ranking para o banco ou aumentar o pool com
  paginação de candidatos.
- **Gatilho de IA:** reforço semântico (pgvector) entra como novo `SearchProvider`/sinal
  adicional no ranking, sem quebrar o contrato do `hit`.

## Impacto futuro

- **Código:** `search/providers.py` (retrieval) e `search/ranking.py` (ordenação)
  implementados atrás de `Protocol`; factory `get_fts_search_provider` para injeção.
- **Interfaces:** contrato do `hit` (D2) e da resposta do ranking (`{criteria, items}`)
  viram a fronteira estável entre busca e apresentação.
- **Dados:** nenhum; reaproveita `search_vector` e as tabelas Core existentes.
