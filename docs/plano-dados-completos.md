# Plano — deixar o banco completo e zerar as pendências

> Levantamento de 2026-08-09. **Números medidos**, não estimados: contagens
> tiradas do Supabase de produção e chamadas reais à API do Mercado Livre.
> Status: **aguardando aprovação**.

## 1. Estado real do banco (produção, hoje)

| Tabela | Linhas | Situação |
| --- | ---: | --- |
| `categories` | 2 | OK |
| `category_attribute_schema` | 14 | OK |
| `brands` | 33 | OK |
| `products` | 167 | Sobe para ~252 quando a branch da Fase 4 for carregada |
| `product_specs` | 167 | Esparso — ver §2 |
| `stores` | 31 | `url` **NULL em 31/31** |
| `offers` | 167 | **1 oferta por produto** — sem concorrência de preço |
| `price_history` | 167 | Um ponto por oferta (carga inicial) |
| `reviews` | **0** | Tabela existe, nada escreve |
| `searches` | **0** | Tabela existe, nada escreve |

Colunas vazias em `products`: `model` **0/167**, `description` **0/167**,
`embedding` **0/167**.

Cobertura de specs (de 167 produtos):

| Atributo | Preenchidos | Declarado como |
| --- | ---: | --- |
| `cpu`, `ram_gb`, `storage_gb`, `storage_type` | 96/96 notebooks | opcional (ADR-0008) |
| `screen_in` | 63/96 notebooks | opcional |
| `weight_kg`, `battery_wh`, `touchscreen` | **0** | opcional |
| `type`, `anc` | 71/71 fones | opcional / obrigatório |
| `bluetooth` | 12/71 | opcional |
| `battery_h` | 12/71 | opcional |
| `microphone` | 15/71 | opcional |
| `water_resistant` | **0** | opcional |

Quatro atributos declarados no schema nunca receberam um único valor.

## 2. A causa raiz das specs esparsas

Os `external_id` do seed (`MLB45574031`) são **IDs de produto de catálogo**, não
IDs de anúncio. Consequências, todas verificadas:

- `GET /items/{id}` → **404** (é o endpoint que o `ml_api.py` chama hoje).
- `GET /products/{id}` → **200**, com ficha técnica completa.
- O `mapping.py` procura `RAM_MEMORY`, `STORAGE_CAPACITY`, `HARD_DRIVE_TYPE`,
  `IS_TOUCHSCREEN`. O payload de `/products` entrega
  `RAM_MEMORY_MODULE_TOTAL_CAPACITY`, `TOTAL_DISK_CAPACITY`, `DISK_TYPE`,
  `WEIGHT`, `IS_WATER_RESISTANT`…

Ou seja: o enriquecimento pela API **nunca funcionou de fato**. O que existe no
banco veio quase todo do `title_parser`. É por isso que `weight_kg`,
`touchscreen` e `water_resistant` estão zerados — o parser não os extrai e o
mapeamento apontava para o lugar errado.

## 3. O que a API do ML entrega (testado agora)

**Autenticação:** `client_credentials` funciona — token de 6h, **sem navegador**.
O fluxo `authorization_code` do `ml_auth.py` deixa de ser necessário para isto.

| Endpoint | Status | Serve para |
| --- | --- | --- |
| `GET /products/{id}` | 200 | `name` limpo, `short_description` → `description`, `MODEL` → `model`, ficha técnica completa |
| `GET /products/{id}/items` | 200 | **Várias ofertas reais** por produto (3 no exemplo), com `price` e `seller_id` |
| `GET /users/{seller_id}` | 200 | `nickname` + `permalink` → `stores.name` e `stores.url` |
| `GET /items/{id}` | 403 | Bloqueado para token de app — não precisamos |
| `GET /sites/MLB/search` | 403 | **Não dá para ampliar o catálogo** buscando; dependemos do CSV já coletado |
| `/reviews/item/{id}` | 404 | — |
| `/products/{id}/reviews` | 500 | — |
| `rating_average` no produto | `null` em 44/44 | — |

**Taxa de resolução do seed inteiro:** 215 de 279 (**77%**) — notebooks 83/122
(68%), fones 132/157 (84%). Os 64 restantes foram despublicados desde a coleta
(julho). Dos que resolvem, `name` e `short_description` vêm em **100%**.

**Reviews não têm fonte.** Três caminhos testados, nenhum devolve nota. A tabela
`reviews` não é "falta implementar": é um schema sem origem de dado.

## 4. Frentes de trabalho

### F1 — Corrigir o enriquecimento pela API (a base de tudo)

1. `ml_auth`: usar `client_credentials` como caminho padrão; o `authorization_code`
   vira fallback documentado.
2. `ml_api`: trocar `/items/{id}` por `/products/{id}`; adicionar
   `/products/{id}/items` e `/users/{id}`.
3. `mapping.py`: reescrever os IDs de atributo para o payload de `/products`, e
   estender para `weight_kg`, `battery_wh`, `touchscreen`, `water_resistant`,
   `microphone`, `battery_h`, `bluetooth`.
4. Novo `enrich.py` (irmão do `backfill.py`): percorre o seed, chama a API,
   preenche `model`, `description` e specs. Idempotente, com cache em disco para
   não repetir chamada, e sem sobrescrever dado melhor.
5. Ampliar `RawProduct`/`NormalizedProduct` com `model` e `description` (o `load`
   já grava as duas colunas — o seed é que nunca as traz).

**Resultado esperado:** `model` e `description` em ~215 produtos, `search_vector`
enriquecido (a coluna gerada concatena `name + model + description`, então a
busca melhora de graça), specs perto de 100% nos que resolvem.

### F2 — Ofertas e lojas de verdade

1. `/products/{id}/items` → 2–4 ofertas por produto em vez de 1.
2. `/users/{seller_id}` → `stores.name` e `stores.url` preenchidos.
3. `price_history` passa a ter sentido: reexecuções capturam variação real.

**Resultado esperado:** "melhor valor" na comparação deixa de ser decorativo;
`stores.url` sai de 0/31.

### F3 — Reconciliar o schema com a realidade

- `reviews` e `searches`: decidir (§5) entre implementar, remover ou documentar.
- `embedding`: decidir (§5).
- `category_attribute_schema`: com as specs completas, reavaliar quais atributos
  voltam a `required: true` — desfazendo a ressalva do ADR-0008.
- Atualizar `docs/data-model.md` (hoje descreve colunas que ninguém preenche).

### F4 — Pendências documentais

| Pendência | Origem | Ação |
| --- | --- | --- |
| `required` sem efeito prático | ADR-0008 | F1 devolve os dados → ADR-0009 revertendo o que der |
| `test_relevance.py` calibrado sobre 167 | ADR-0008 | Recalibrar para o catálogo final |
| "[Fase 6] price_history" como *Not started* | Notion | Já tem 167 linhas — corrigir o status |
| README da extensão manda `docker compose up -d db api` | `extension/README.md` | Conferir contra o uso real (Supabase) |
| `ML_ACCESS_TOKEN` / `ML_REFRESH_TOKEN` vazios no `.env` | `worker/.env` | F1 remove a dependência de token manual |

### F5 — Extensão em modo desenvolvedor

A extensão **já está configurada para localhost** e o CORS da API já libera
`chrome-extension://` por regex. Não há código a escrever; a frente é verificar
ponta a ponta e corrigir o que aparecer:

1. `uvicorn` na :8000 e `npm run dev` na :3000.
2. `chrome://extensions` → Modo do desenvolvedor → Carregar sem compactação →
   pasta `extension/`.
3. Buscar "melhor notebook gamer" no Google e conferir painel, popup e o link
   "ver no ProductSearcher".
4. Ajustar seletores da SERP se o DOM do Google tiver mudado (limitação já
   conhecida e documentada).

## 5. Decisões tomadas (2026-08-09, Erick)

### D1 — `reviews`: **mantida vazia, com rota de povoamento documentada**

O PRD classifica **RF-05 (Reviews resumidas) como `Could`** e o `data-model`
já a descreve como "opcional no MVP". Não é schema órfão: é requisito adiado.
Remover e recriar custaria duas migrations para voltar ao mesmo lugar.

O que muda: `docs/data-model.md` e a própria tabela ganham a explicação de por
que está vazia e **como se enche**, testado e datado:

- A API pública do ML não expõe avaliação para token de aplicação
  (`/reviews/item` 404, `/products/{id}/reviews` 500, `rating_average` nulo).
- Rota viável: ator do **Apify** sobre a página do produto — mesma fonte já
  usada para o catálogo (ADR-0001), colhendo `rating` e `rating_count`.
- `source` já existe na tabela justamente para distinguir a procedência.
- Gatilho de revisão: quando RF-05 sair de `Could`, ou quando o
  `RankingService` for ganhar a nota como fator.

### D2 — `searches`: **implementar a escrita no `/search`**

O `SearchService` passa a gravar `query_text`, o `parsed_intent` e o
`result_count`. Vira observabilidade de produto — quais buscas voltam vazias,
quais termos o `IntentParser` não entende — e é o insumo natural para
recalibrar o KPI de relevância. A escrita é tolerante a falha: erro ao logar
**nunca** derruba a busca.

### D3 — `embedding`: **fica na Fase 6**

Nulo está correto hoje. O sistema tem de funcionar 100% sem IA e a busca
vetorial é reforço opcional atrás do `VectorProvider` (ADR-0002). A ação aqui é
documental: deixar explícito no `data-model` que a coluna é intencionalmente
vazia no MVP, para não ser lida como lacuna.

### D4 — os 64 despublicados: **mantidos, com marca de procedência**

Continuam no catálogo com o que o título fornece. O seed passa a registrar o
resultado da tentativa de enriquecimento (data e status), deixando explícito
qual campo é de primeira mão (API) e qual é inferido do título. Reexecutar o
enriquecimento reaproveita a marca e não repete chamada à toa.

## 6. Ordem de ataque

| Ordem | Frente | Depende de |
| --- | --- | --- |
| 1 | **F1** — enriquecimento pela API (`/products`, mapping, `enrich.py`) | — |
| 2 | **F2** — ofertas múltiplas e `stores.url` | F1 (mesmo cliente HTTP) |
| 3 | Recarregar o seed no Supabase | F1 + F2 |
| 4 | **F3** — schema x realidade, `required` de volta, `searches` | dados na mão |
| 5 | **F4** — ADR-0009, data-model, Notion, recalibrar o KPI | F3 |
| 6 | **F5** — extensão em dev mode | independente |

F5 não depende de nada e pode ser puxada para a frente se você quiser ver a
extensão rodando antes.
