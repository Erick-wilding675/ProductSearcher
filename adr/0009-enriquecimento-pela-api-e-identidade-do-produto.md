# ADR-0009 — Enriquecimento pela API do ML e identidade do produto

- **Status:** Aceito
- **Data:** 2026-08-09
- **Decisor(es):** Erick
- **Relacionado:** revisa parcialmente o [ADR-0008](0008-cobertura-do-seed-parser-e-specs-opcionais.md); estende o [ADR-0005](0005-decisoes-fase-2.md) D3

## Contexto

O banco tinha colunas inteiras vazias: `products.model` **0/167**,
`products.description` **0/167**, `stores.url` **0/31**, `reviews` e `searches`
sem uma linha. Havia **uma oferta por produto**, o que deixava o "melhor valor"
da comparação (RF-21) sem com quem comparar. E quatro atributos declarados no
`category_attribute_schema` — `weight_kg`, `battery_wh`, `touchscreen`,
`water_resistant` — nunca receberam um único valor.

A investigação achou a causa e ela é uma só: **o enriquecimento pela API do
Mercado Livre nunca funcionou**.

Os `external_id` do seed (`MLB45574031`) são ids de **produto de catálogo**, não
de anúncio. Consequências, todas verificadas contra a API:

| Chamada | Resultado |
| --- | --- |
| `GET /items/{id}` — o que o `ml_api.py` fazia | **404** em 10/10 amostrados |
| `GET /products/{id}` | **200**, com ficha técnica completa |
| `GET /products/{id}/items` | **200**, várias ofertas reais por produto |
| `GET /users/{seller_id}` | **200**, nome e permalink da loja |
| `GET /items/{id}`, `GET /sites/MLB/search` | **403** para token de aplicação |

E o `mapping.py` procurava `RAM_MEMORY`, `STORAGE_CAPACITY`, `HARD_DRIVE_TYPE`,
`IS_TOUCHSCREEN` — nenhum existe no payload de catálogo, que usa
`RAM_MEMORY_MODULE_TOTAL_CAPACITY`, `TOTAL_DISK_CAPACITY`, `DISK_TYPE` e
`WITH_TOUCH_SCREEN`. Tudo que havia no banco vinha do `title_parser`.

## Decisão

### D1 — `/products/{id}` como fonte, com token de aplicação

`ml_api.py` passa a falar com o endpoint de catálogo. A autenticação usa
**`client_credentials`** (token de 6h, sem navegador e sem redirect), que cobre
tudo que o enriquecimento precisa. O fluxo `authorization_code` continua no
`ml_auth.py` para o dia em que um recurso de usuário for necessário — hoje não é,
e o `ML_ACCESS_TOKEN` deixa de ser pré-requisito manual.

`mapping.py` foi reescrito com os IDs e **valores observados** na API, não
deduzidos: `DISPLAY_SIZE` chega como `'15.6 "'`, `WEIGHT` como `'2.49 kg'`, os
booleanos como `'Sim'`/`'Não'`, `HEADPHONE_FORMAT` como `'In-ear'`/`'Clip-ear'`.

### D2 — `enrich.py`: enriquecer no lugar, não regerar

Regerar pelo `build_seed.py` exigiria o CSV original do Apify e refaria a coleta.
Como os ids de catálogo já estão no seed versionado, o `enrich.py` consulta a API
e completa o YAML. É idempotente, carimba cada produto com o resultado da
tentativa (`enrichment: {status, date}`) e **nunca sobrescreve** valor existente.

### D3 — Identidade do produto: `parent_id` + SKU

Com `model` preenchido, `marca + modelo` deixou de ser único e 32 produtos seriam
descartados como duplicata. A própria API resolve o impasse:

- variantes de cor compartilham `parent_id` — os cinco "Dapon H02D" do seed têm
  todos `MLB24117256` como pai;
- produtos diferentes têm pais diferentes mesmo com marca e modelo iguais — os
  "IdeaPad Slim 3 15IRH10" i5 e i7, SKUs `83NS0002BR` e `83NS0004BR`.

Então: **a identidade é o `parent_id`**, e o slug ganha o `ALPHANUMERIC_MODEL`
(SKU do fabricante) como desempate. Linhas de mesma identidade **não são
descartadas — são fundidas**, somando as ofertas. Isso emenda o ADR-0005 D3, que
definia o slug como marca + modelo.

Quando duas identidades ainda assim colidem no slug (sem SKU para desempatar), a
segunda recebe sufixo. Antes, o upsert por slug faria uma sobrescrever a outra em
silêncio — pior que a rejeição explícita de antes.

### D4 — Os 64 despublicados ficam, marcados

215 de 279 ids (77%) ainda resolvem; 64 foram despublicados desde a coleta.
Ficam no catálogo com o que o título fornece e com `enrichment.status: stale`,
deixando explícito qual dado é de 1ª mão e qual é inferido.

### D5 — `required` volta onde há cobertura

| Atributo | Cobertura | `required` |
| --- | ---: | --- |
| `headphones.type` | 117/117 (100%) | **volta a `true`** — reverte o ADR-0008 |
| `headphones.anc` | 117/117 (100%) | segue `true` |
| `notebooks.cpu` | 109/118 (92%) | segue `false` |
| `notebooks.ram_gb` | 106/118 (89%) | segue `false` |
| `notebooks.storage_gb` / `storage_type` | 104/118 (88%) | segue `false` |

Os notebooks seguem opcionais por um motivo agora **medido**: os 39 despublicados
não têm como ser enriquecidos. Exigi-los custaria ~14 produtos.

### D6 — `battery_wh` sai do schema

A API expõe `BATTERY_CAPACITY` em Ah/mAh (`'3.574 Ah'`, `'41 mAh'`), não em Wh.
Converter exigiria a tensão da bateria, que não vem. Um número em unidade errada
é pior que a ausência, e um atributo que nunca poderá ser preenchido é dívida
visível — então ele sai do `categories.json`.

### D7 — `searches` passa a ser escrito; `reviews` e `embedding` ficam

- **`searches`**: o `SearchService` registra consulta, intent e total. Fica atrás
  de uma interface (`SearchLog`), e **falha ao registrar nunca derruba a busca**.
- **`reviews`**: continua vazia. RF-05 é `Could` no PRD e a API não expõe
  avaliação para token de aplicação (`/reviews/item` 404,
  `/products/{id}/reviews` 500, `rating_average` nulo em 44/44). A rota de
  povoamento — ator do Apify sobre a página do produto — está documentada no
  `data-model`.
- **`embedding`**: nulo é o estado **correto** no MVP. O sistema funciona 100%
  sem IA e a busca vetorial é reforço opcional atrás do `VectorProvider`
  (ADR-0002). Fica para a Fase 6.

### D8 — Carga em lote e prepared statements desligados

Dois problemas que só apareceram com o catálogo maior:

- A carga fazia **um round trip por linha**. Com 167 ofertas passava; com ~1400
  em ~800 lojas estourava o tempo contra o Supabase. Agora cada tabela é uma
  instrução com `RETURNING`: a carga inteira caiu de >170s (timeout) para **8,9s**.
- O pooler do Supabase (porta 6543, modo transação) multiplexa sessões, e os
  prepared statements do psycopg3 são por sessão. Consulta repetida quebrava com
  `DuplicatePreparedStatement` — derrubou a suíte de relevância inteira.
  `prepare_threshold=None` no `connect_args` resolve. **Isso afetava a API em
  produção**, não só o teste.

### D9 — `rank_by=price` resolve a ordenação no servidor

Adendo de 2026-08-09, na revisão do seletor de critério de relevância.

O `rank_by` entra no ranking como um fator de preferência, mas **preço não é um
peso — é uma ordem absoluta** ("do menor para o maior, sempre"). Como o fator de
preferência só existe para marca e especificação, `rank_by=price` era aceito e
**ignorado**: só a web app se comportava certo, porque mandava `sort=price_asc`
junto. Qualquer outro cliente da API — a extensão, por exemplo, e o ADR-0003
prevê dois clientes — não via efeito nenhum.

Agora o `sort` não tem default no router (`SortOption | None`), e o service
resolve: `sort` explícito manda; sem ele, `rank_by=price` aplica `price_asc`.
Isso preserva a decisão de manter os dois controles com papéis distintos — a
escolha do usuário continua tendo a última palavra — sem deixar um parâmetro do
contrato sem efeito.

No mesmo passe, o peso do fator de preferência subiu de `1.0` para `2.0`. Com
`1.0` ele empatava com a soma de todos os outros (`0.6 + 0.3 + 0.1`): num caso
com teto de preço e atributo pedido, o item da marca escolhida ganhava por
`0.003` e, no limite, empatava e perdia no desempate por relevância. Agora a
dominância é por construção, e um teste trava a invariante.

## Benefícios

| | Antes | Depois |
| --- | ---: | ---: |
| `products.model` | 0 | 185 |
| `products.description` | 0 | 178 |
| Ofertas | 167 | 1392 |
| Ofertas por produto | 1,00 | 5,93 |
| `stores.url` | 0/31 | 751/791 |
| `touchscreen` / `weight_kg` / `water_resistant` | 0 | 72 / 68 / 80 |
| Tempo de carga | timeout | 8,9s |

`search_vector` é coluna gerada sobre `name + model + description`: preencher
`description` melhorou a busca sem tocar em uma linha do ranking.

## Consequências negativas

- **141 produtos órfãos no banco.** A mudança de chave natural (D3) faz o upsert
  criar linhas novas ao lado das antigas. A ferramenta `tools/cleanup_orphans.py`
  está pronta e testada em `--dry-run`, mas **não foi executada** — decisão de não
  apagar dado de produção dentro da automação. Até rodar, a busca mostra alguns
  produtos duas vezes. Rastreado no Notion.
- **A fusão de variantes perde a cor.** Não há spec de cor no schema; os cinco
  "Dapon H02D" viram um. Correto para comparação, mas é informação descartada.
- **`offers.url` aponta para a página de catálogo**, não para o anúncio de cada
  vendedor: `/items/{id}` é 403 para token de aplicação. A página de catálogo é
  onde o comprador escolhe o vendedor, então o destino é útil — mas não é o link
  direto da oferta.
- **`searches` cresce sem rotina de expurgo.** Uma linha por busca com texto, sem
  TTL. Revisar quando o volume justificar.
- **Dependência de um formato não contratual.** `parent_id` e `ALPHANUMERIC_MODEL`
  são detalhes do catálogo do ML; se mudarem, a identidade muda junto.

## Alternativas descartadas

| Alternativa | Por que não |
| --- | --- |
| Desempatar só pelo `external_id` no slug | Zero perda, mas os cinco Dapon H02D viram cinco resultados idênticos na busca |
| Tirar o `model` do slug | Volta ao slug longo do título e conta o mesmo produto duas vezes |
| Fundir tudo que colide por marca+modelo | Juntaria o IdeaPad i5 com o i7 — dado errado na comparação |
| Regerar o seed pelo `build_seed.py` | Exige o CSV do Apify e refaz a coleta; os ids já estão versionados |
| Remover a tabela `reviews` | RF-05 é `Could` no PRD; recriar depois custaria duas migrations |
| Gerar embeddings agora | Antecipa a Fase 6 e contraria "IA é complementar" |

## Caminho de evolução / gatilho de revisão

- **Rodar o `cleanup_orphans`** — é o que fecha a pendência aberta em D3.
- **`--retry-stale`** periodicamente: produto despublicado pode voltar.
- **`required` dos notebooks** volta a `true` se a cobertura passar de ~98%.
- **`reviews`**: quando RF-05 sair de `Could`, ou quando o `RankingService` for
  ganhar a nota como fator, executar a rota do Apify.
- **`searches`**: se o volume incomodar, `NullSearchLog` desliga sem tocar no
  serviço; um expurgo por idade resolve o crescimento.

## Impacto futuro

- `worker/tools/seedbuilder/`: `ml_api.py`, `mapping.py`, `ml_auth.py`,
  `enrich.py` (novo), `build_seed.py`.
- `worker/tools/cleanup_orphans.py` (novo).
- `worker/ingestion/`: `models.py`, `normalize.py`, `load.py`.
- `api/app/`: `core/db.py`, `search/log.py` (novo), `search/service.py`,
  `catalog/tables.py`.
- `worker/seed/`: `categories.json` e os dois YAML de produtos.
- **Sem migration**: nenhuma coluna ou tabela mudou de forma.
