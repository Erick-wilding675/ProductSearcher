# ADR-0010 — Fase 6: onde a IA entra (e onde não entra)

- **Status:** Aceito
- **Data:** 2026-08-19
- **Decisor(es):** Erick
- **Relacionado:** [ADR-0002](0002-datastore-postgres-only.md) (Postgres-only), [ADR-0005](0005-decisoes-fase-2.md) D2 (dimensão do embedding), [ADR-0007](0007-pipeline-busca-retrieval-ranking.md) D2.1 (o defeito que motiva esta fase), [ADR-0009](0009-enriquecimento-pela-api-e-identidade-do-produto.md) D7 (`searches`)

> Espelho do ADR-010 do Document Hub (Notion). O Notion numera com 3 dígitos
> (ADR-010), o repositório com 4 (`adr/0010-*.md`) — é o mesmo documento.

## Contexto

As três tasks de IA da Fase 6 foram escritas em **21/06/2026**, antes de existir
busca, ranking ou catálogo enriquecido. Quatro coisas mudaram desde então e
alteram o que faz sentido construir:

1. **A explicabilidade já foi entregue, sem IA.** O ADR-0007 D5.1 pôs
   `criteria` + `score` + `factors` no contrato do `GET /search`. Quando a task
   de explicação por LLM nasceu, não havia explicação nenhuma; hoje há,
   determinística (RF-31 atendido).
2. **Existe um defeito de busca medido.** ADR-0007 D2.1: `plainto_tsquery`
   combina termos com **AND**, então "notebook **para jogos**" exige que "jogos"
   apareça no título do anúncio. O próprio ADR aponta pgvector ou RF-16 como
   saída.
3. **O ADR-0009 encheu `description` (178) e `model` (185).** Antes disso,
   embeddar produto era embeddar título de marketplace. O ganho potencial da
   busca vetorial subiu.
4. **`searches` passou a ser gravado** (ADR-0009 D7): existe evidência real de
   quais consultas voltam vazias.

E uma lacuna de instrumentação: os 12 casos de `test_relevance.py` são **todos
marca+modelo** ("acer predator helios", "qcy h3") — a metade que o FTS já
acerta. Não há um único caso de uso. O KPI marca 100% enquanto o defeito do item
2 passa batido, e nenhum ganho de busca semântica seria **detectável**.

## Decisão

### D1 — Instrumento de medida antes de qualquer IA

Nada de IA entra antes de (a) rodar o `cleanup_orphans` e (b) a suíte enxergar o
problema.

O cleanup deixa de ser chore paralela e vira **pré-requisito**: 141 duplicatas
dentro de um pool de 200 candidatos distorcem qualquer medição de recall — medir
ganho semântico com o catálogo sujo produz número que não vale nada.

A suíte ganha um segundo bloco de consultas de **caso de uso**, com o esperado
sendo um *conjunto aceitável* (não um produto único), marcado `xfail`: é o
placar que a fase precisa virar. Em paralelo, uma ferramenta lê `searches` e
lista as consultas reais com `result_count = 0` — evidência, não suposição.

### D2 — O LLM entra **offline, na ingestão** — não em runtime

A melhor aplicação de LLM neste projeto não é responder o usuário: é **preparar
o dado** para que o caminho determinístico consiga responder.

Um passo irmão do `enrich.py` recebe **nome + description + specs já no banco** e
devolve um conjunto **fechado** de rótulos de caso de uso — `use_case:
["jogos", "trabalho", "estudo", "edicao-video", "portabilidade"]` — gravados em
`product_specs.attributes` (JSONB, **sem migration**) e declarados no
`category_attribute_schema` como `enum`.

Depois disso, "notebook para jogos" é respondido **pelo caminho que já existe**:
o `RuleBasedIntentParser` reconhece "para jogos" → `attributes={"use_case":
"jogos"}` → filtro JSONB por containment que o `FtsSearchProvider` já aplica
(RF-12).

Por que esta é a forma certa:

- **Zero IA em runtime.** Zero latência, zero custo por request, nenhuma
  dependência de provider no caminho crítico — que é literalmente o RF-60 e o
  RNF-10.
- **Custo delimitado e único:** ~250 produtos × 1 chamada, dentro do teto de
  US$10 da RNF-03. Pela **Batch API** o custo cai à metade e a latência não
  importa num passo offline.
- **Guardas:** o prompt recebe só specs que **já estão no banco** (nada de
  inventar atributo); rótulo fora do enum fechado é descartado — o
  `validate_specs` já sabe rejeitar. Idempotente e carimbado como o `enrich.py`
  (ADR-0009 D2).

### D3 — Vetorial: produtos offline, query em runtime, **768 dimensões mantidas**

A infra já existe desde a Fase 2: `products.embedding vector(768)` e índice HNSW
na migration. Falta apenas o valor.

O desenho é **assimétrico**: os vetores dos **produtos** são gerados offline, uma
vez (como o `enrich.py`); em runtime o único cálculo é o vetor **da consulta**.

A dimensão **permanece 768** — esta decisão **não emenda** o ADR-0005 D2, e não
há migration.

**Invariante que governa tudo aqui:** produto e consulta têm de ser vetorizados
**pelo mesmo modelo**. Vetores de modelos diferentes vivem em espaços diferentes
e a similaridade de cosseno entre eles não significa nada — falha silenciosa, sem
erro, só resultado ruim.

### D3.1 — O embedding roda no serviço em nuvem, com modelo aberto

*(decidido em 19/08/2026)*

Restrição que forçou a decisão: **a Anthropic não expõe endpoint de embeddings**
— a API é `/v1/messages` mais Batches, Files, Token Counting e Models. A chave da
Anthropic serve para D2, **não** para D3.

Decisão: **nada roda na máquina do desenvolvedor.** O modelo é **aberto, de 768
dimensões, e roda dentro do serviço em nuvem que hospeda a API**. O mesmo
processo atende os dois lados: a carga inicial dos ~250 produtos e o vetor de
cada consulta em runtime.

Por quê:

- Preserva a premissa de **modelo aberto** do ADR-0002 e do ADR-0005 D2 — sem
  segundo vendor, sem custo por request, sem chamada de rede externa no caminho
  crítico.
- Satisfaz a invariante do parágrafo anterior **por construção**: só existe um
  lugar onde vetor é gerado, então produto e consulta não têm como divergir de
  modelo.
- Descarta gerar os vetores dos produtos na máquina do Erick: ela não é
  reprodutível nem está no caminho de deploy (RNF-04), e a query teria de ser
  vetorizada em outro lugar de qualquer forma.

O preço é um **requisito de infraestrutura** que a Fase 7 tem de honrar — e é o
assunto do comunicado ao Pedro.

### D3.2 — Requisitos para o serviço de deploy do backend

| Requisito | Por quê |
| --- | --- |
| RAM acima do mínimo de free-tier | O processo passa a carregar o modelo além do FastAPI. Planos de 256 MB (default de várias free-tiers) não comportam; a faixa a mirar é da ordem de **1–2 GB**, a confirmar por medição |
| **Sem sleep / idle shutdown** | Carregar o modelo custa segundos. Se o host dorme, o primeiro request paga isso e fura a RNF-02 (< 2 s). Já era requisito da Fase 7 — agora é inegociável |
| Disco/imagem para o runtime de inferência | Runtime + pesos entram na imagem do container. Várias free-tiers limitam o tamanho da imagem |
| CPU para uma inferência por busca | Um embedding de consulta por request, dentro do orçamento da RNF-01 (p95 < 500 ms) junto com a query SQL |

Duas alavancas se o envelope não couber, **nesta ordem**: (1) runtime de
inferência quantizado/otimizado em vez do stack de treino completo — reduz
memória e imagem **sem** mudar modelo nem dimensão; (2) só então reabrir dimensão
ou provider externo.

**Medição é pré-requisito do comunicado.** Os números acima são estimativa. Antes
de mandar requisito ao Pedro: medir o RSS do processo com o modelo carregado, o
tempo de carga e a latência de uma inferência de consulta — e comunicar **número
medido, não estimado**. Mesma disciplina do ADR-0009.

### D3.3 — `multilingual-e5-base` sobre ONNX Runtime int8

*(decidido em 22/08/2026, sobre a medição registrada no log de construção)*

Decisão: o modelo é **`intfloat/multilingual-e5-base`**, servido por **ONNX
Runtime com quantização int8 dinâmica**, em imagem multi-stage onde o torch fica
só no estágio de export e **não entra na imagem final**. Dimensão **768**, como
D3 já fixou — a alavanca (2) do D3.2 continua fechada.

**A medição não escolheu o modelo, e isso é o resultado.** e5 e
`paraphrase-multilingual-mpnet-base-v2` empatam no envelope porque são a mesma
arquitetura (XLM-R base, 278M de parâmetros); a diferença entre eles é ruído da
máquina de medição. O desempate veio do **objetivo de treino**, não dos números:
o mpnet é `paraphrase-*`, treinado para similaridade **simétrica** entre frases
de mesma natureza. Nosso caso é **assimétrico** — consulta curta ("notebook para
faculdade") contra copy longo de produto — que é exatamente o que o e5 treina,
com os prefixos `query:` e `passage:`.

O que a medição decidiu foi o **runtime**: a alavanca (1) do D3.2 leva a imagem
de 2546 para 739 MB e o RSS de pico de 1220 para 872 MB, sem mudar modelo nem
dimensão. Adotada agora, e não guardada para o caso de não caber — porque com
ela o requisito ao Pedro cabe em muito mais host, o que é o ponto do comunicado.

**Preço da escolha, e como ele é pago:** o e5 degrada **em silêncio** se o
prefixo faltar — um vetor de produto gerado sem `passage:` não dá erro, só piora
o resultado. É a mesma classe de falha da invariante de modelo único do D3, e
recebe o mesmo tratamento: os prefixos ficam **encapsulados dentro do provider**,
sem caminho de chamada público que aceite texto cru. Quem chama pede "vetor de
consulta" ou "vetor de produto"; o prefixo não é decisão de quem chama.

Consequência para D3.2: os requisitos ao Pedro passam a ser os da coluna
quantizada — **RAM de 1 GB com folga** (pico medido de 872 MB), imagem de **~750
MB**, e `OMP_NUM_THREADS=1` como item obrigatório de configuração, não como
ajuste fino.

### D4 — Busca híbrida por **união**, não por chave

O enunciado original da task ("flag liga a vetorial; desligada, FTS opera
normal") descreve um *switch*, e switch é a pior opção: vetorial puro perde o
match exato que o FTS acerta hoje — "IdeaPad Slim 3 15IRH10" casa literal no FTS
e vira ruído no espaço vetorial.

`HybridSearchProvider` implementa a **mesma** `SearchProvider` Protocol, então
`service.py` não muda uma linha. Chama os dois braços, funde por *Reciprocal Rank
Fusion* e devolve o contrato de `hit` do ADR-0007 D2 mais um `vector_rank` que o
ranking pode consumir como sinal. A flag desliga tudo e cai no
`FtsSearchProvider` de hoje.

Efeito colateral a revisar: união aumenta o pool, e `total` hoje significa
"tamanho do pool" (ADR-0007 D5.1) — `search_candidate_pool = 200` precisa ser
reavaliado.

### D5 — LLM no `IntentParser` (RF-16): **condicional**

`LLMIntentParser` atrás da Protocol que já existe, acionado **só** quando o
parser de regra não extraiu nada **e** o FTS voltou vazio. O caminho comum nunca
chama — preserva p95 (RNF-01), custo e determinismo. Cache por consulta
normalizada; a chave já está em `searches`.

**Condicional a D2:** se o enriquecimento semântico resolver o caso comum, boa
parte do RF-16 fica sem função. Por isso vem depois, e só com evidência da suíte
de D1.

### D6 — Explicação por LLM (RF-61): mantida, **rebaixada e condicional**

Hoje o LLM aqui só converte número em prosa, e traz um risco novo: prosa que
contradiz os `factors` é pior que prosa nenhuma.

Pré-requisito que ninguém tinha notado: **`DeterministicAIService.explain` ainda
é `raise NotImplementedError`** desde a Fase 3 — o fallback que a flag
`ai_enabled=False` deveria usar **não existe**. Ele vem primeiro; só depois o
`LLMAIService`, recebendo **exclusivamente** os fatores já calculados, com
instrução de narrar sem introduzir fato novo.

Reavaliar se vale a pena depois de D2 e D4 — pode não valer.

### D7 — RAG sobre reviews continua fora

RF-62 é `Won't` no PRD e a tabela `reviews` está **vazia sem fonte**: a API do ML
não devolve avaliação para token de aplicação (ADR-0009 D7). Não é "falta
implementar" — é schema sem origem de dado. Qualquer plano de RAG sobre review
morre aqui até a rota do Apify ser executada.

### D8 — Dobrar acento no FTS vem **antes** de qualquer IA

*(decidido em 19/08/2026, a partir da medição de D1)*

D1 encontrou uma causa dos zeros que não é semântica: `to_tsvector('portuguese',
…)` **não dobra acento** e a extensão `unaccent` não estava instalada. O corpus é
copy de marketplace, escrita com acento; a consulta em pt-BR vem sem. Como o
`plainto_tsquery` combina com AND, **um** termo sem acento zera a consulta
inteira — "notebook para trabalho no escritorio" vira `'notebook' & 'trabalh' &
'escritori'`, e `escritori` casa nada, embora "escritório" apareça em 15
produtos.

Decisão: configuração de busca própria, `public.portuguese_unaccent` (`portuguese`
com `unaccent` na frente do `portuguese_stem`), usada **na coluna gerada e na
consulta**. Migration `d2e4f6a8b0c1`.

Por que antes de D2, e não depois: sozinho, o fix leva a **cobertura@5 de 27%
para 55%** e a **precisão média@5 de 16% para 34%** — mais da metade do caminho
até a meta, sem IA. Medir D2 antes disso creditaria ao LLM um ganho que era do
`unaccent`, e é exatamente o tipo de conta errada que D1 existe para impedir.

Duas notas de construção que valem como decisão:

- **A configuração é sempre qualificada** (`public.portuguese_unaccent`). Um nome
  nu resolveria pelo `search_path` de quem consulta, e o do Supabase (`"$user",
  public, extensions`) não é o do Postgres do docker. Coluna e consulta têm de
  usar a **mesma** configuração: divergir não dá erro, só devolve menos — falha
  silenciosa, do mesmo tipo que o ADR-010 D3 alerta para embeddings.
- **`unaccent` entra como dicionário, não como função.** `unaccent(text)` é
  STABLE e por isso proibida em coluna gerada; `to_tsvector(regconfig, text)` é
  IMMUTABLE mesmo com a dobra dentro da configuração.

**Custo aceito: o stemmer português enfraquece.** As regras de sufixo do snowball
dependem do acento. Com a dobra na frente, "programação" deixa de virar `program`
e vira `programaca`:

| termo | `portuguese` | `portuguese_unaccent` |
| --- | --- | --- |
| programação | `program` | `programaca` |
| programacao | `programaca` | `programaca` |
| edição / edicao | `ediçã` / `edica` | `edica` / `edica` |

O radical largo (`program`) casava 13 notebooks, mas casando "programa"/"programas"
— software incluso na copy, não relevância. O estreito casa 2, e o ganho real é a
**coerência**: acentuado e não acentuado passam a produzir o mesmo radical, que é
o defeito que estamos consertando. Se em algum momento a recall curta doer, a
saída é indexar a **união** das duas configurações
(`to_tsvector('portuguese', …) || to_tsvector('public.portuguese_unaccent', …)`)
em vez de reabrir a ordem do dicionário — mas isso dobra o índice e não se paga
com o número de hoje.

**O que o fix não alcança:** "faculdade" e "notebook leve para viagem" continuam
em zero. Ali não é acento — a palavra **não existe** no corpus em forma nenhuma.
São exatamente os casos que sobram para D2.

## Benefícios

- A IA passa a ser julgada por **evidência**: D1 constrói o placar antes de
  qualquer aposta.
- D2 ataca a causa do defeito do ADR-0007 D2.1 pela raiz e **mantém o runtime
  livre de IA** — coerente com o princípio fundacional do projeto, e defensável
  como portfólio.
- D3/D4 aproveitam infra que **já está no banco** (coluna + índice HNSW) e não
  exigem migration.
- Nenhuma das decisões muda o contrato público do `GET /search`.

## Consequências negativas

- **D2 introduz dado derivado de LLM no catálogo.** Mesmo com enum fechado e
  prompt restrito às specs do banco, um rótulo errado é erro silencioso — o
  produto some de uma busca legítima. Mitigação: amostra rotulada à mão como
  teste.
- **D3.1 encarece o host.** O modelo carregado no processo da API tira o backend
  da faixa de free-tier mais barata e acopla a Fase 6 à Fase 7: **a escolha do
  host pelo Pedro depende disto** e precisa ser comunicada antes de ele decidir.
- **D3.1 põe uma inferência de CPU no caminho de cada busca**, disputando o
  orçamento da RNF-01 com a query SQL.
- **D4 aumenta o pool** e mexe no significado de `total`.
- D5 e D6 podem terminar a fase **sem serem construídos**. É o desenho — mas
  significa que RF-16 e RF-61 podem continuar `Could` não atendidos.

## Alternativas descartadas

| Alternativa | Por que não (agora) |
| --- | --- |
| Começar pela busca vetorial (a task de maior prioridade no board) | Sem D1, o ganho não seria mensurável; e o catálogo com 141 órfãos falsearia qualquer número |
| LLM no caminho crítico da busca (interpretar toda consulta) | Fere RF-60/RNF-10, estoura a p95 da RNF-01 e o teto de custo da RNF-03 |
| Trocar a dimensão para 384 e usar modelo local menor | Avaliada e descartada por Erick: exigiria migration e emenda ao ADR-0005 D2. Mantido 768 |
| Switch FTS ↔ vetorial (enunciado original da task) | Perde a precisão do match exato; união com RRF preserva os dois sinais |
| RAG sobre specs/reviews | RF-62 é `Won't`; `reviews` não tem fonte de dado (ADR-0009 D7) |
| Explicação por LLM primeiro (task mais antiga) | RF-31 já atendido deterministicamente; seria a IA no lugar de menor impacto |

## Caminho de evolução / gatilho de revisão

- **Gatilho de D3:** ~~fechar o provider do embedding antes de escrever código~~
  **fechado em D3.1**; ~~medir o envelope de recursos~~ **medido em 22/08/2026**,
  e o modelo/runtime **fechado em D3.3**. Resta emitir o comunicado ao Pedro
  antes de ele escolher o host da Fase 7 — agora com número medido, como o D3.2
  exige. A alavanca (1) do D3.2 já foi gasta em D3.3; se o envelope ainda não
  couber em host viável, o que resta é a alavanca (2) — reabrir dimensão ou
  provider externo.
- **Gatilho de D4:** apresentar a revisão do pool/`total` e as rotas de fusão
  para decisão antes de implementar.
- **Gatilho de D5:** só constrói se a suíte de D1 continuar vermelha depois de
  D2.
- **Gatilho de D6:** reavaliar necessidade ao fim de D4.
- **Gatilho de D7:** quando RF-05 sair de `Could` ou a rota do Apify for
  executada.

## Impacto futuro

- `api/tests/` ganha a suíte de casos de uso e `worker/tools/` uma ferramenta
  nova sobre `searches`.
- `worker/tools/seedbuilder/`: passo novo de rótulos semânticos;
  `worker/seed/categories.json` ganha `use_case` como `enum`.
- `api/app/search/`: `intent.py` (rótulos de caso de uso), `providers.py`
  (`HybridSearchProvider`), possível `LLMIntentParser`.
- `api/app/ai/service.py`: `DeterministicAIService.explain` deixa de ser
  `NotImplementedError`.
- `api/app/core/config.py`: flags novas.
- **Sem migration em D2/D3**: a coluna `embedding` e o índice HNSW já existem;
  `use_case` cabe no JSONB. D8, decidido depois, **tem** migration
  (`d2e4f6a8b0c1`): recria a coluna gerada `search_vector` sob a configuração
  nova.

---

## Construção — registro por passo

Esta seção acompanha a implementação. É escrita **durante** o trabalho, não no
fim: o que foi decidido no teclado e não estava no plano é justamente o que se
perde se ficar para depois.

### D1 (em andamento desde 19/08/2026, branch `fase6`)

**Arquivo separado, não um bloco dentro do `test_relevance.py`.** O plano dizia
"a suíte ganha um segundo bloco". Na hora de escrever, os dois tipos de caso não
couberam no mesmo arquivo: o gabarito de `test_relevance.py` é um **produto
esperado** (`"Nitro V15"`, casado por substring do nome) e o de caso de uso é um
**predicado sobre specs**, com métricas próprias (precisão@5, acaso). Misturar
obrigaria a um `expected` polimórfico e a um KPI que soma laranja com maçã. Ficou
`api/tests/test_relevance_use_cases.py`, com a divisão de papéis explicada no
topo dos dois arquivos.

**O gabarito é spec, nunca nome.** Decisão que muda o valor da medida: usar o
nome como verdade seria circular, porque `search_vector` é
`to_tsvector(name || model || description)` — exatamente o texto que o FTS
indexa. Um gabarito textual mediria se a busca acha o que a busca indexa e daria
nota alta sem servir melhor o usuário. Spec é fato do produto, independente de
como o anúncio foi escrito.

**Predicados calibrados contra o seed antes de virar teste.** Um caso em que
grande parte do catálogo qualifica não mede nada — devolver qualquer coisa
acerta. Levantamento sobre `worker/seed/products/*.yaml` (279 produtos: 122
notebooks, 157 fones), com o predicado ajustado até ficar discriminante:

| Caso | Predicado | Fatia do catálogo |
| --- | --- | --- |
| jogos | `gpu` presente | 28% |
| edição de vídeo | `gpu` e `ram_gb >= 16` | 20% |
| trabalho | `ram_gb >= 8`, SSD, **sem** `gpu` | 44% |
| faculdade | `ram_gb >= 8`, SSD, preço ≤ R$4500 | 23% |
| portabilidade | `weight_kg <= 1.6` | 15% |
| programação | `ram_gb >= 16`, SSD, `storage_gb >= 512` | 43% |
| academia / corrida | resistente a água e in-ear/earbud | 22% |
| reunião | microfone e ANC | 34% |
| viagem de avião | ANC e over-ear | 15% |
| bateria | `battery_h >= 30` | 20% |

Descartados por serem largos demais para medir: "trabalho" como `ram>=8 + SSD`
(72%), "faculdade" como só `ram>=8` (75%), "reunião" como só microfone (85%).
Essa fatia entra no relatório como coluna **acaso** — 60% de precisão é ótimo
onde o acaso é 20% e é fracasso onde é 70%.

**Dois casos de controle.** "notebook gamer" (termo literal no título) e "fone
com cancelamento de ruído" (o `RuleBasedIntentParser` já converte em filtro duro
`anc=True`) são os únicos que **falham** individualmente. Se um controle
quebrar, o problema é o arreio — seed trocado, banco desatualizado — e não a
busca semântica que ainda não existe.

**Achado que muda a expectativa do baseline.** O ADR-0007 D2.1 diz que "notebook
para jogos" devolve zero. Isso valia antes do ADR-0009: hoje `description` está
preenchida em 206 dos 279 produtos do seed e **entra no `search_vector`**. Uma
varredura offline do documento FTS mostra vocabulário de uso espalhado pela copy
do marketplace — 39% dos notebooks mencionam jogo/gamer, 43% dos fones mencionam
trabalho, 55% mencionam reunião/chamada. Ou seja, o baseline provavelmente **não
é zero**: é recall que existe com precisão ruim, porque a copy fala de uso por
marketing, não por fato. Isso reforça D1 (precisar do número antes de apostar) e
não muda D2 — mas o texto de D2 acima está escrito para um baseline zero e deve
ser relido quando a medição sair.

**Ferramenta sobre `searches`:** `worker/tools/search_insights.py`, somente
leitura, no mesmo estilo do `cleanup_orphans` (argparse, `.env` do worker, SQL
cru). Quatro seções: mais buscadas, as que voltaram vazias (candidatas a caso
novo), as que o parser não categorizou, e as de necessidade — estas mostrando
lado a lado o que o usuário digitou e o `parsed_intent->>'text'` que de fato foi
ao `plainto_tsquery`, que é o problema da fase em uma linha.

**Pendências de D1 — resolvidas em 19/08/2026, de outra rede.** As duas
dependiam só de alcançar o Supabase. Segue o que a execução revelou.

#### O cleanup rodou — e o script tinha um defeito latente

`cleanup_orphans` nunca havia executado o caminho de escrita: o `--dry-run` sai
antes de `remove()`. Na primeira execução real ele morreu com
`syntax error at or near "$1"`. Causa: `sa.text("... in :ids")` recebendo uma
coleção entrega **um** parâmetro ao psycopg, e o SQL vira `in $1`. Faltava
`bindparam(..., expanding=True)`. Corrigido com o helper `_delete_por_ids`, que
concentra os seis `delete ... in :ids` do arquivo.

Vale como lição além do arquivo: **caminho que o `--dry-run` não percorre não
está testado**. O mesmo raciocínio motivou exercitar as quatro consultas do
`search_insights` direto contra o Postgres (todas executam; ver abaixo).

A transação abortou inteira, sem apagar nada — a atomicidade do `engine.begin()`
funcionou. Com a correção:

    removido: price_history 141, offers 141, product_specs 141, products 141
              reviews 0, stores 0, brands 0
    atributos de schema removidos: 1

Catálogo: **376 → 235 produtos** (118 notebooks + 117 fones), exatamente o que o
seed produz. `stores` e `brands` não perderam linha — toda loja e marca dos
órfãos ainda é referenciada por produto vivo.

#### O cleanup era mesmo pré-requisito, e dá para provar

D1 afirmava que medir com o catálogo sujo "produz número que não vale nada".
Medido dos dois lados, o **acaso** — o denominador de toda a suíte — se desloca
até 18 pontos:

| predicado | acaso com os 141 órfãos | acaso limpo | na calibração do YAML |
| --- | --- | --- | --- |
| jogos | 14% | 24% | 28% |
| trabalho | 68% | 50% | 44% |
| reunião | 25% | 37% | 34% |
| academia | 16% | 25% | 22% |
| portabilidade | 9% | 15% | 15% |

Sujo, "trabalho" aparentava 68% de acaso — na faixa que a própria D1 descartou
por não medir nada. Limpo, volta para perto da calibração feita sobre o YAML.

#### Baseline medido (19/08/2026, catálogo limpo, 235 produtos)

    caso                   consulta                                top5  prec  acaso  total
    jogos                  notebook para jogos                      4/5   80%   24%     28
    edição de vídeo        notebook para edicao de video            0/0    0%   18%      0
    trabalho               notebook para trabalho no escritorio     0/0    0%   50%      0
    faculdade              notebook para faculdade                  0/0    0%   24%      0
    portabilidade          notebook leve para viagem                0/0    0%   15%      0
    programação            notebook para programacao                0/0    0%   43%      0
    academia               fone para academia                       2/5   40%   25%     15
    corrida                fone para correr                         3/5   60%   25%     14
    reunião                fone para reuniao online                 0/0    0%   37%      0
    viagem                 fone para viagem de aviao                0/0    0%   14%      0
    bateria                fone com bateria para o dia todo         0/5    0%   22%     15

**cobertura@5 = 27%** (meta 80%) · **precisão média@5 = 16%** (alvo 60%, acaso
27%). Os dois controles passam e `test_relevance.py` segue 13/13 — o arreio está
certo, e a metade "produto conhecido" continua 100%. É o placar que a fase tem
de virar.

#### O achado anterior estava errado pela metade

O parágrafo acima ("o baseline provavelmente **não é zero**") não se confirmou:
**7 das 11 consultas devolvem literalmente zero**. A varredura offline que
sugeriu recall procurou as palavras que a *copy* usa ("gamer", "trabalho",
"reunião") — não as que o **usuário digita**. São conjuntos diferentes, e a
diferença é o item seguinte.

#### O defeito não é (só) semântico: é acento

Causa medida dos zeros: `to_tsvector('portuguese', …)` **não dobra acento** e a
extensão `unaccent` **não está instalada**. O corpus é copy de marketplace,
escrita com acento; a consulta em pt-BR costuma vir sem. Os dois nunca se
encontram:

| termo | docs sem acento | docs com acento |
| --- | --- | --- |
| reuniao / reunião | 0 | 3 |
| edicao / edição | 0 | 10 |
| programacao / programação | 0 | 13 |
| escritorio / escritório | 0 | 15 |
| aviao / avião | 0 | 1 |
| video / vídeo | 20 | 69 |

E o `plainto_tsquery` combina com **AND** (ADR-0007 D2.1), então basta um termo
sem acento na consulta para zerar o conjunto inteiro: "notebook para trabalho no
escritorio" vira `'notebook' & 'trabalh' & 'escritori'`, e `escritori` casa nada.
`faculdade` é o contraexemplo honesto — 0 dos dois lados: ali o vocabulário
realmente não existe no corpus, e só D2/D3 resolvem.

**Quanto isso vale, medido:** repetindo a suíte com as mesmas consultas
acentuadas (proxy do que o `unaccent` faria, e um piso — o fix real também ajuda
o sentido inverso):

| | hoje | só com acento resolvido |
| --- | --- | --- |
| cobertura@5 | 27% | **55%** |
| precisão média@5 | 16% | **36%** |

Mais da metade do caminho até a meta, **sem IA nenhuma**. Isso não muda o mérito
de D2, mas muda a contabilidade: medir D2 antes de corrigir o acento creditaria
ao LLM um ganho que era de `unaccent`. **Decisão pendente antes de D2** — o fix
mexe na expressão do índice FTS (migration) e por isso não entrou em D1, que é
instrumento, não correção.

#### `searches` continua vazio

`search_insights` rodou contra o banco real: a tabela tem **0 linhas**, e a
ferramenta sai pelo atalho com a explicação certa. Ninguém usou a busca contra
este banco fora dos testes (que usam `NullSearchLog`), e não há deploy — Fase 7.
Como o atalho impede que qualquer das quatro consultas execute, elas foram
exercitadas direto contra o Postgres: as quatro rodam sem erro de SQL. A
evidência de consulta real, porém, **só existe depois do deploy** — até lá a
suíte continua medindo a busca contra a nossa imaginação, como o próprio
cabeçalho da ferramenta admite.

### D2, primeira parte (19/08/2026, branch `fase6`) — construída, **não executada**

D2 foi relida à luz da medição, como o próprio ADR mandava. O que mudou:

**O caso de D2 encolheu, mas não caiu.** Depois de D8, só 2 das 11 consultas
ainda devolvem zero ("faculdade" e "notebook leve para viagem") — mas a
precisão média é 34% contra 60% de alvo, e o parser extrai `attrs={}` em
**todas** as consultas de uso. É exatamente o buraco que D2 preenche.

**Achado que o plano não previu: rotular não basta — o parser tem de tirar os
termos de uso do texto que vai ao FTS.** Mesma lógica do preço, e pelo mesmo
motivo: o que virou filtro **duro** não pode continuar obrigatório no AND do
`plainto_tsquery`. Deixar "faculdade" no texto exigiria a palavra no anúncio, e
ela não está em nenhum dos 235 produtos — o filtro acertaria e o AND zeraria em
seguida. O plano dizia que a consulta seria respondida "pelo caminho que já
existe"; o caminho existe, mas precisava desta limpeza para funcionar.

**As duas metades não podem viajar juntas, e isso foi medido.** Ligar o filtro
antes dos rótulos existirem quebra a busca: `use_case` vira filtro duro sobre um
atributo que nenhum produto tem. Pior que zerar as consultas de uso — derruba
**produto conhecido**: "headset gamer havit" passa a filtrar por `gamer` e perde
o match exato de marca. Cinco testes vermelhos, entre eles os dois controles e o
`test_relevance.py`. **O instrumento de D1 pegou o erro**, que é literalmente o
motivo de D1 existir.

Por isso a entrega está partida em duas:

| metade | onde | estado |
| --- | --- | --- |
| offline: schema `use_case`, `enum_multi`, guarda no `validate_specs` | `fase6` | commitada, **inerte** |
| offline: rotulador pela Batch API | `fase6` | reescrito para a Groq e **executado em 21/08** (ver abaixo) |
| runtime: parser converte necessidade em filtro | `fase6-d2-runtime` | commitada, **não mesclável** até os rótulos existirem |

**`use_case` é `enum_multi`, um tipo novo.** Lista e não escalar porque um
notebook serve para jogos **e** edição de vídeo, e porque o filtro é containment
JSONB (`@>`) — casa "contém este rótulo" sem precisar saber os outros. Sem
migration: cabe no JSONB de `product_specs.attributes`, como o plano previa.

**O enum é por categoria**, o que o plano não dizia. O mesmo termo não significa
a mesma coisa nos dois catálogos: "viagem" em fone é ruído de cabine; em
notebook é peso, ou seja `portabilidade`. O plano listava só
`["jogos", "trabalho", "estudo", "edicao-video", "portabilidade"]` — escrito
antes de D1 existir. A medição pediu `programacao` (notebooks) e um conjunto
próprio para fones:

- **notebooks:** `jogos`, `trabalho`, `estudo`, `edicao-video`, `programacao`,
  `portabilidade`
- **headphones:** `esporte`, `chamadas`, `viagem`, `trabalho`, `jogos`

**Custo real do lote, não estimado por analogia:** 235 produtos, ~134k tokens de
entrada, **US$ 0,45** com o desconto da Batch API. O teto da RNF-03 é US$ 10 — o
passo cabe com folga de mais de vinte vezes.

**Um caso que D2 não resolve, e é honesto dizer:** "fone com bateria para o dia
todo" devolve 15 resultados e nenhum com `battery_h >= 30`. Não é caso de uso, é
faixa numérica — pede filtro de atributo no parser, não rótulo de LLM. Fica
registrado como trabalho separado — e foi construído logo em seguida, abaixo.

**Pendência:** `ANTHROPIC_API_KEY`. Sem ela o lote não roda, os rótulos não
existem e a metade de runtime não pode ser mesclada. `--dry-run` verificado
contra o banco real: 235 fichas montadas, enum correto por categoria.

A chave chegou em 19/08/2026 e **não autentica**: 401 `authentication_error`. O
formato explica — 43 caracteres começando em `sk-ant-`, enquanto uma chave de API
é `sk-ant-api03-…` com ~108. O que está no `.env` é outra coisa (o identificador
da chave no Console, provavelmente), não o segredo.

**Resolvida em 21/08/2026 por outro caminho:** a chave que veio é da **Groq**. O
rotulador foi migrado, executado e medido — e a Batch API caiu junto com o
fornecedor. O registro está em *"D2, primeira parte — executada"*, no fim deste
arquivo; o custo de US$ 0,45 acima virou US$ 0.

#### O trabalho separado: faixa numérica no parser (19/08/2026)

Atacado antes de D3 porque é pequeno, é pré-requisito de medida e **não depende
da chave** — deixá-lo para depois manteria o placar sujo enquanto D2 esperava.

`attributes` não expressa faixa. O filtro de RF-12 é containment JSONB (`@>`),
que é **igualdade**: um fone de 40h não *contém* 30h. Por isso a faixa é um campo
próprio do `Intent` (`attribute_ranges`) e um operador próprio no SQL, em vez de
um valor de formato especial dentro de `attributes` que o provider teria de
adivinhar.

**A comparação é jsonb contra jsonb, não `::numeric`.** O caminho óbvio
(`(attributes->>'battery_h')::numeric >= 30`) é avaliado sobre as linhas que o
planner escolher, e um único spec gravado como texto derruba a **consulta
inteira** com erro de conversão — falha global causada por um dado ruim, o
oposto da política "rejeita, loga e segue" do ADR-0005 D6. `jsonb_typeof(...) =
'number'` mais `... >= to_jsonb(30::numeric)` nunca falha. Nenhum índice serve a
condição (o GIN `jsonb_path_ops` só atende containment); com 235 produtos isso
não custa nada, e se o catálogo crescer o caminho é um btree por expressão.

**O bug que apareceu no meio, e que era pior que o caso original.** `_PRICE_PATTERN`
casa `até` seguido de número, sem olhar o que vem depois. Então:

| consulta | antes | depois |
| --- | --- | --- |
| `fone ate 20 horas de bateria` | `price_max = 20.0` → 0 resultados | `battery_h <= 20` |
| `notebook ate 1,5kg` | `price_max = 15.0` → 0 resultados | `weight_kg <= 1.5` → 7 resultados |

O segundo é o mais feio: a conversão de preço lê `.` como separador de milhar,
então "1,5" virava quinze reais. As duas falhavam **em silêncio** — busca vazia
sem nada indicando que o parser tinha lido a medida como dinheiro. A guarda é
uma unidade colada ao número: se tem, não é preço.

**"O dia todo" exige a categoria certa.** A expressão por extenso é a única
regra aqui em que a *chave* é inferida, não digitada — e `battery_h` não existe
no schema de notebooks. Aplicá-la a "notebook com bateria para o dia todo"
zeraria a busca por um palpite do parser. Quando o usuário escreve o número, ele
assume a consequência de não haver resultado; quando o parser adivinha, não pode
impor essa consequência. Número dito vence a expressão sempre.

O limiar de 30h é **decisão de produto, não medição**: uma jornada mais margem.
A evidência que dá para trazer é de calibração — no catálogo de hoje o corte
deixa 26 dos 117 fones (22%), dentro da faixa de acaso que a D1 estabeleceu.

**O caso saiu do agregado, e é isso que importa para o placar.** Com o filtro no
ar, o predicado do gabarito (`battery_h >= 30`) e a condição do SQL passaram a
ser a **mesma regra**: a precisão dá 100% por construção, não por acerto. Contá-lo
creditaria ao enriquecimento semântico um ganho que é do `RuleBasedIntentParser`
— a conta errada que a D1 existe para impedir, a mesma que a D8 evitou ao vir
antes de D2. Virou **controle**, junto do caso de ANC, e a regra fica escrita na
suíte: *caso que o parser passa a resolver com filtro duro sai do agregado.*

Isso **rebaixa o baseline publicado em D8**, e o número correto é este:

| | D1 | depois de D8 | com a faixa | meta |
| --- | --- | --- | --- | --- |
| casos semânticos no agregado | 11 | 11 | **10** | — |
| cobertura@5 | 27% | 55% | **60%** | 80% |
| precisão média@5 | 16% | 34% | **37%** | 60% |
| consultas com zero resultado | 7 de 11 | 2 de 11 | **2 de 10** | 0 |

Os 60%/37% não são ganho de busca: são os mesmos 6 casos cobertos sobre um
denominador menor. O que a faixa entregou de verdade foi um controle novo e dois
bugs de preço a menos — e um placar que agora mede só o que D2 tem de resolver.

**O que não foi feito, de propósito:** "notebook leve para viagem" continua em
zero. "Leve" também é faixa (`weight_kg`), mas não há evidência para o corte além
do próprio gabarito — escolher 1,6 kg porque o teste diz 1,6 kg é a circularidade
que acabamos de tirar do agregado. Fica para quando houver um critério de fora.

### D8 (19/08/2026) — o fix de acento, medido

Construído logo depois de D1 fechar, pela razão que a própria D8 dá: medir D2
antes disso creditaria ao LLM o ganho do `unaccent`.

**A coluna gerada é recriada, não alterada.** `ALTER COLUMN … SET EXPRESSION` só
existe do PG17 em diante e o dev local roda PG16 (`pgvector/pgvector:pg16`),
enquanto o Supabase está em 17.6. Drop + add funciona nos dois, e como a coluna é
GERADA os 235 produtos se reindexam sozinhos — não há passo de backfill.

**Round-trip verificado no banco real**: `upgrade` → `downgrade` → `upgrade`, com
os 235 produtos intactos e a busca voltando ao comportamento antigo no meio do
caminho (`edicao` → 0 documentos) e ao novo no fim (→ 10).

**Placar depois do fix** (mesmo catálogo de 235, nenhuma IA):

| | D1 (baseline) | depois de D8 | meta |
| --- | --- | --- | --- |
| cobertura@5 | 27% | **55%** | 80% |
| precisão média@5 | 16% | **34%** | 60% |
| consultas com zero resultado | 7 de 11 | **2 de 11** | 0 |

`test_relevance.py` segue **13/13** — a metade "produto conhecido" não regrediu,
que era o risco real de mexer no dicionário. Os agregados continuam `xfail`: o
alvo é 80%/60% e ainda não chegamos. É D2 que tem de fechar o resto.

> Estes 55%/34% são sobre 11 casos semânticos. O trabalho de faixa numérica
> registrado em D2 tirou um caso do agregado (virou controle) e o denominador
> passou a 10 — ver a tabela lá. Comparar com números posteriores exige olhar o
> denominador junto.

**O parser em Python já era tolerante a acento** (`_sem_acento` nos fillers,
`ru[ií]do` no regex de ANC). O buraco era só do lado do Postgres — verificado
antes de mexer, para não "consertar" duas vezes o mesmo lugar.

### D6, primeira metade (19/08/2026, commit `8c562d7`)

Antecipada porque não depende de banco nem de rede — e porque este ADR já a
tinha identificado como **pré-requisito esquecido**: `DeterministicAIService.
explain` era `raise NotImplementedError` desde a Fase 3.

Como nada chamava `explain`, o contrato de `context` também nunca tinha sido
definido. Ficou sendo **exatamente o que o ranking já produz** — `score`,
`factors`, `intent` — e nada além. A camada não consulta banco, não recalcula
score e não conhece o catálogo.

Isso é a decisão de projeto, não uma simplificação: é o que torna o
`LLMAIService` seguro de construir depois. Um LLM que recebe o produto inteiro
pode elogiar a bateria; um que recebe só os fatores só pode narrar os fatores, e
a prosa não tem como contradizer o número exibido ao lado dela. A restrição está
escrita como **teste**, não como comentário.

Quatro regras de fidelidade, cada uma com teste em `api/tests/test_ai_service.py`:

1. **Score parcial não vira frase absoluta.** `relevance` é normalizada pelo
   maior `fts_rank` do conjunto: 0,62 vira "62% do melhor casamento desta
   busca", não "é o que mais se aproxima". A primeira versão escrita aqui tinha
   esse defeito — afirmava o superlativo com score parcial.
2. **Atributo com chave presente e valor divergente não é atributo atendido.**
   Pedir `ram_gb=16` e o item ter 8 não pode virar "tem o que você pediu". Para
   a prosa não divergir do score com o tempo, `attr_matches` deixou de ser
   privada em `ranking.py` e é a **mesma** função nos dois lugares.
3. **O que ficou de fora é declarado** ("preço não entrou: você não informou um
   teto"). Omitir faria o usuário supor um cuidado que o ranking não teve
   naquela consulta.
4. **Preço vira folga em reais** quando o teto veio no `context`: "R$ 701,00
   abaixo do teto" é verificável pelo usuário; "0,86" não é.

`LLMAIService.explain` segue `NotImplementedError` — RF-61 continua condicional
a D2/D4 —, agora com mensagem que aponta o substituto e o contrato a herdar.
### D2, primeira parte — **executada** (21/08/2026)

A chave chegou, e não é da Anthropic: é da **Groq**. O rotulador foi escrito para
a Batch API da Anthropic, então a execução começou por uma migração de transporte
— e o que ela revelou está registrado abaixo, porque nada disso estava no plano.

**A Batch API saiu, e o motivo dela também.** O plano gratuito da Groq não expõe
o endpoint de lotes (`not_available_for_plan`, verificado). A decisão original
tinha uma razão de custo — metade do preço, latência irrelevante num passo
offline; sem custo por token essa razão evapora, e no lugar dela entra o limite
de **8.000 tokens por minuto**. Com isso `--submit`/`--collect` (desenhados para
um lote de até 24h) deixaram de fazer sentido: virou uma passada síncrona que lê
`x-ratelimit-remaining-tokens` e `x-ratelimit-reset-tokens` da própria resposta e
dorme quando falta folga — quem dita o ritmo é o servidor, não um `sleep` chutado.
Modelo: `openai/gpt-oss-120b`, `temperature=0`, `reasoning_effort=low`.

O que **não** mudou é a decisão D2: o LLM continua offline, na ingestão, atrás do
conjunto fechado do `categories.json`, e o runtime segue sem IA. Trocar Anthropic
por Groq é trocar transporte — a guarda é o schema da resposta mais o
`validate_specs`, não a marca do modelo. Foi por isso que a substituição custou
uma tarde e não uma reescrita.

**A gravação passou a ser por produto**, e não um `--collect` transacional no fim:
a passada leva ~25 minutos contra o limite por minuto, e perder tudo por uma queda
de rede aos 20 seria o contrário da idempotência que o passo promete. Interromper
e reexecutar continua de onde parou pelo mesmo mecanismo que já existia (pula quem
tem `use_case`).

#### Três defeitos que só a execução mostrava

**1. A guarda rejeitava todo fone.** `validate_specs` cobra também os atributos
`required` da categoria, e a ficha aqui é **parcial** — um atributo só. Fone tem
`type` e `anc` obrigatórios: os 117 seriam rejeitados por "atributo obrigatório
ausente", com log, sem gravar nada. O piloto de 8 produtos pegou (7 gravados, 1
rejeitado — o único fone da amostra). A chamada passou a validar só o spec de
`use_case`; o conjunto fechado, que é a guarda que importa, continua valendo.

Vale a mesma lição do `cleanup_orphans`: **caminho que nenhuma execução percorre
não está testado**. O `--dry-run` monta a requisição e mostra a ficha — não chega
perto do `validate_specs`.

**2. `DuplicatePreparedStatement` no pooler.** A primeira execução morreu no
sétimo produto. O motivo já estava documentado em `api/app/core/db.py`: o Supabase
é acessado pelo pooler em modo transação (6543), que multiplexa sessões, e
prepared statement é por sessão. As outras ferramentas do worker escapam por
abrirem **uma** transação; esta abre uma por produto e reencontra o `_pg3_0` de
outra sessão na segunda escrita. `connect_args={"prepare_threshold": None}`,
como na API.

**3. O carimbo vazava para a UI.** `_labeling` (data e modelo) é metadado de
pipeline, mas mora no mesmo JSONB das specs — e o contrato público devolve
`attributes` inteiro. A página de produto renderiza `Object.entries(specs)` e a
comparação monta uma linha por chave presente em qualquer produto: o carimbo
viraria linha de tabela na cara do usuário. `app/catalog/specs.py` passou a
recortar o que começa com `_`, nos três pontos em que specs saem da API (busca,
detalhe, comparação), com teste. O rótulo `use_case`, que **é** spec, continua
exposto.

#### O prompt precisou de calibração — e ela tem um limite de propósito

A primeira passada rotulou um Alienware de 2,49 kg com os **seis** rótulos de
notebook, portabilidade inclusive. Rótulo que vale para todo mundo não filtra
nada: seria um `@>` que devolve o catálogo inteiro, e a precisão de D1 não subiria
um ponto. Duas mudanças:

- **Teto de 3 rótulos** e a regra escrita de que rótulo é *recomendação*, não
  inventário do que o aparelho aguenta — vale para quem se destaca naquilo entre
  os concorrentes da mesma categoria.
- **Glossário por categoria** (mesma razão do enum ser por categoria: `jogos` em
  notebook é GPU, em fone é latência e microfone).

O glossário define a **necessidade**, nunca o limiar. É deliberado: o gabarito de
D1 diz `weight_kg <= 1.6`, e escrever isso no prompt faria o rotulador repetir o
teste que deveria medi-lo — a precisão daria 100% por construção. É a mesma
circularidade que tirou o caso da bateria do agregado. O rotulador julga; a suíte
julga o rotulador; os dois não podem ler a mesma régua.


#### O que ficou no catálogo

    235 produtos · 213 com rótulo · 22 sem
    rótulos por produto: média 1,88   (0 → 22 produtos, 1 → 47, 2 → 103, 3 → 63)

Os 22 sem rótulo não são falha: lista vazia é resposta válida do prompt, e são
fichas magras demais para sustentar qualquer recomendação (fone com `type` e
nada mais). Eles são o **piso de recall** do filtro de D2 — nenhuma consulta de
uso vai alcançá-los.

Custo: **US$ 0** (plano gratuito), contra os US$ 0,45 estimados para a Batch API
da Anthropic. Tempo de relógio: ~30 minutos, todos ditados pelo limite por
minuto — o modelo responde em ~1s.

#### O rótulo medido contra o gabarito de D1

O rotulador não pode ser julgado por amostra lida a olho. A régua independente já
existe: os predicados sobre specs da suíte de D1. Para cada rótulo, sobre o
catálogo inteiro — **concordância** é quanto do que ele marcou satisfaz o
predicado; **cobertura**, quanto de quem satisfaz o predicado ele marcou:

| rótulo | caso de D1 | marcados | acaso | concordância | cobertura |
| --- | --- | ---: | ---: | ---: | ---: |
| `jogos` | notebook para jogos | 37/118 | 24% | **76%** | 100% |
| `edicao-video` | edição de vídeo | 26/118 | 18% | **62%** | 76% |
| `trabalho` | trabalho no escritório | 53/118 | 50% | **77%** | 69% |
| `estudo` | faculdade | 47/118 | 24% | 40% | 68% |
| `portabilidade` | notebook leve para viagem | 39/118 | 15% | 46% | 100% |
| `programacao` | programação | 46/118 | 43% | **74%** | 67% |
| `esporte` | academia / corrida | 31/117 | 25% | **77%** | 83% |
| `chamadas` | reunião online | 73/117 | 37% | 42% | 72% |
| `viagem` | viagem de avião | 25/117 | 14% | 32% | 50% |

Lidas contra o acaso, oito das nove batem a régua com folga. As duas fracas têm
explicação, e nenhuma delas é "o modelo errou":

- **`estudo` (40% contra 24%)**: o gabarito de "faculdade" inclui **preço ≤ R$
  4.500**, e a ficha enviada ao rotulador não tem preço — de propósito, porque
  preço muda e rótulo carimbado não. O teto é filtro do parser, não do rótulo;
  na consulta real os dois se somam.
- **`chamadas` (42% contra 37%)**: é o rótulo mais largo do catálogo (62% dos
  fones). Quase todo fone tem microfone, e o gabarito de "reunião" exige
  microfone **e** ANC. É o rótulo com menos valor de filtro dos nove — se a
  consulta de reunião continuar fraca depois de D2, é aqui que se mexe.
- **`portabilidade` (46% contra 15%)**: o modelo chama de portátil o notebook de
  1,8 kg; o gabarito corta em 1,6. Aqui a divergência é de régua, não de fato — e
  é exatamente a divergência que o glossário se recusou a eliminar por decreto.

#### O placar não mudou — e não devia

`227 passed, 2 xfailed`; cobertura@5 **60%**, precisão média@5 **37%**, iguais ao
que a faixa numérica deixou. `search_vector` é `name || model || description`:
rótulo em `attributes` não entra no documento FTS e nada em runtime lê `use_case`
ainda. Etapa 1 produziu o **dado**; quem o transforma em resultado é a metade de
runtime, que está pronta na `fase6-d2-runtime`.

Projetando a tabela acima sobre os 10 casos do agregado (a concordância do rótulo
é o teto da precisão@5 quando o filtro domina o top-5), a média dá **~60%** —
exatamente o alvo, com a cobertura indo a 100% porque todo caso passou a ter pelo
menos 25 produtos marcados. É projeção, não medida: o filtro ainda concorre com o
texto do FTS e com o ranking, e é a suíte de D1 que dá a palavra final depois do
merge.

#### Duas armadilhas para quem executar isto de novo

**A ordem é carga do seed → rotulagem, sempre.** Os rótulos vivem só no banco (o
YAML do seed não tem `use_case`), e o upsert de `product_specs` substituía
`attributes` inteiro — sem o cuidado que o `keep_if_null` tem com
`model`/`description`. Qualquer ingestão apagava a rotulagem em silêncio, e o
filtro de D2 voltava a não casar com nada.

> **Resolvido no mesmo dia**, com o upsert mesclando o JSONB — ver *"A carga do
> seed parou de apagar a rotulagem"*, no fim deste arquivo, com o trade-off que
> isso traz. A ordem continua sendo a recomendada; deixou é de ser obrigatória.

**`use_case` ainda não está em `category_attribute_schema` no banco.** O
`categories.json` tem, mas quem leva schema para o Postgres é a carga do seed.
Hoje isso não quebra nada: o atributo é lista, e o seletor de specs só oferece
valores simples, então ele já seria ignorado como faceta. Entra na próxima carga
— que, depois do merge de JSONB, deixou de ser perigosa para os rótulos.

### D2, metade de runtime — mesclada e medida (21/08/2026, merge `b293b7a`)

Com os rótulos no ar, a `fase6-d2-runtime` deixou de ser perigosa e entrou. O
merge **não foi mecânico**: as duas metades resolviam o mesmo problema — tirar do
texto do FTS o que virou filtro duro — por caminhos diferentes.

**Ficou o caminho da faixa numérica, e o outro morreu.** A faixa devolve, de cada
extração, os **trechos** que consumiu, e `_remove_trechos` apaga por posição; a
metade de runtime refazia a varredura com `re.sub` depois de já ter reconhecido os
termos. Apagar por posição não depende da ordem em que os padrões casaram — e eles
se sobrepõem (preço e faixa disputam o "até"). `_parse_use_cases` passou a devolver
`(rótulos, trechos)` e `_sem_termos_de_uso` deixou de existir. Um mecanismo para os
três filtros, não três.

Detalhe que o merge obrigou a pensar: a varredura de uso roda sobre a cópia **sem
acento**, e os índices são usados na original. Vale porque `_sem_acento` decompõe
em NFD e descarta só a combinante — cada letra acentuada continua ocupando uma
posição. Está escrito no docstring, porque é o tipo de coisa que a próxima pessoa
desfaz sem perceber.

**Três testes de parser mudaram de expectativa, e a mudança é o contrato.**
"notebook gamer" agora consulta o FTS por `notebook` e filtra `use_case=jogos`;
antes mandava "notebook gamer" ao `plainto_tsquery`. Não é regressão: é a mesma
regra do preço chegando ao vocabulário de uso.

#### O placar, medido depois do merge

| | D1 | +D8 (acento) | +faixa | **+D2** | meta |
| --- | --- | --- | --- | --- | --- |
| cobertura@5 | 27% | 55% | 60% | **100%** | 80% |
| precisão média@5 | 16% | 34% | 37% | **68%** | 60% |
| consultas com zero | 7/11 | 2/11 | 2/10 | **0/10** | 0 |

    caso                   consulta                                 top5   prec  acaso  total
    jogos                  notebook para jogos                    5/5     100%   24%     37
    edição de vídeo        notebook para edicao de video          2/5      40%   18%     24
    trabalho               notebook para trabalho no escritorio   4/5      80%   50%     50
    faculdade              notebook para faculdade                5/5     100%   24%     45
    portabilidade          notebook leve para viagem              1/5      20%   15%     15
    programação            notebook para programacao              5/5     100%   43%     42
    academia               fone para academia                     4/5      80%   25%     31
    corrida                fone para correr                       4/5      80%   25%     31
    reunião                fone para reuniao online               2/5      40%   37%      6
    viagem                 fone para viagem de aviao              2/5      40%   14%     23

`test_relevance.py` segue **13/13**: "headset gamer havit" não perdeu o match
exato de marca, que era o risco medido quando o filtro subiu sem rótulo.

**Os dois agregados saíram do `xfail`.** Nasceram vermelhos de propósito, como
previsão de fracasso a ser virada; viraram. Daqui para a frente são guarda de
regressão — quem baixar o placar tem de justificar.

#### As quatro consultas que sobraram não têm todas o mesmo problema

Vale separar, porque a tentação é creditar tudo ao rótulo:

- **`reunião` (40%, só 6 resultados)** e **`portabilidade` (20%, 15
  resultados)**: o gargalo é **texto residual**, não rótulo. "fone para reuniao
  online" vira `reuniao` → filtro e sobra `online` no AND do FTS; "notebook leve
  para viagem" sobra `leve`. Palavras que descrevem necessidade mas não estão no
  vocabulário de `use_case` continuam obrigatórias no `plainto_tsquery` e cortam
  o conjunto antes do ranking. É o mesmo defeito de fundo do ADR-0007 D2.1, agora
  no resto.
- **`edição de vídeo` (40%)** e **`viagem` (40%)**: aqui é o rótulo mesmo — 62% e
  32% de concordância com o predicado, os dois números mais baixos da tabela de
  rotulagem. O filtro traz o conjunto certo por definição do rótulo; quem discorda
  é o gabarito.

A diferença importa para o passo seguinte: D3 (vetorial) ataca o primeiro grupo —
"online" e "leve" deixariam de ser termo obrigatório — e não faz nada pelo
segundo, que é qualidade de rótulo.

### A carga do seed parou de apagar a rotulagem (21/08/2026, commit `ef3468f`)

A armadilha registrada acima — *"a ordem é carga do seed → rotulagem, sempre"* —
virou correção em vez de aviso, a pedido do Erick.

`product_specs.attributes` tem **dois donos**: o seed traz a ficha técnica e o
rotulador grava `use_case` e `_labeling`. O upsert substituía a coluna inteira,
então qualquer carga apagava a rotulagem em silêncio. Agora o `ON CONFLICT DO
UPDATE` faz `attributes || excluded.attributes`: o seed vence chave a chave, e o
que ele não conhece sobrevive. É o `keep_if_null` de `model`/`description` um
nível abaixo — chave, não coluna.

**O trade-off, dito por inteiro:** mesclar preserva o que a carga não conhece e,
pela mesma regra, o que ela **deixou** de conhecer. Um `gpu` errado que foi
removido do seed continua no banco para sempre; antes, a carga seguinte o
apagava. Trocar apagamento silencioso por permanência silenciosa seria trocar um
defeito por outro — então a permanência **é anunciada**: `_avisa_specs_orfas` loga
toda chave que ficou sem correspondente no seed, ignorando `use_case` e os
carimbos `_*`, que são do outro dono. Remover de vez continua sendo decisão
humana, com `update` à mão; o que não pode é a remoção acontecer sozinha, sem
ninguém saber.

Duas alternativas descartadas: **preservar só um conjunto fixo de chaves**
(`use_case`, `_labeling`) mantém a propagação de remoção, mas amarra a ingestão à
lista de passos de enriquecimento — cada passo novo obrigaria a mexer no `load`;
e **escrever os rótulos de volta no YAML do seed**, que resolveria de vez, mas
põe saída de LLM dentro do dado curado, que é justamente o que o ADR-0001 quis
evitar.

**Achado que só apareceu porque o teste é de integração:** montar o lado direito
do `||` com `cast(str, JSONB)` liga um `str` com tipo JSONB, o driver serializa
para o escalar `'"{...}"'` — e no Postgres `objeto || escalar` devolve **array**,
não objeto. `{"ram_gb": 16}` virou `[{"ram_gb": 16}, "{...}"]` sem erro nenhum.
Os dois lados agora são expressões jsonb; o teste que pegou isso é o mesmo que
guarda a preservação do rótulo.

### Medição do envelope de D3 (22/08/2026) — números, não estimativa

O D3.2 exige **número medido** antes do comunicado ao Pedro. Medido dentro de
container `python:3.11-slim` — a mesma base do deploy — porque RSS, tempo de
carga e tamanho de imagem não transferem do Windows local (venv 3.14) para lá.
Imagens de medição descartáveis: não tocam `api/pyproject.toml` nem a imagem de
produção.

**A medição foi feita com `--cpus=1`**, e não no host de 16 vCPU. Esse detalhe
não é cosmético — ver o achado das threads abaixo.

Candidatos comparados, ambos de 768 dimensões e multilíngues (modelo só-inglês
está fora: o catálogo é copy de marketplace brasileiro):
`intfloat/multilingual-e5-base` e
`sentence-transformers/paraphrase-multilingual-mpnet-base-v2`.

| Medida (1 vCPU, `OMP_NUM_THREADS=1`) | e5 (torch fp32) | mpnet (torch fp32) | e5 (ONNX int8) |
| --- | --- | --- | --- |
| Imagem em disco | 2546 MB | 2538 MB | **739 MB** |
| RSS de pico | 1220 MB | 1205 MB | **872 MB** |
| Carga (import + init) | ~10,5 s | ~14 s | **~2,5 s** |
| Consulta p50 | 44–52 ms | 40–47 ms | **10,3 ms** |
| Consulta p95 | 52–111 ms | 60–166 ms | **12,8 ms** |
| Catálogo de 250 offline | 39 s | 36 s | **14,3 s** |

**Os dois candidatos empatam no envelope, e o empate era previsível:** ambos são
XLM-R base, 278M de parâmetros, 768 dimensões. A dispersão entre eles (p95 de 52
a 166 ms) é ruído da máquina de medição, não diferença de modelo — rodadas
repetidas trocam quem "ganha". **Então a medição não escolhe o modelo.** Ela
decide outra coisa, que era a pergunta mais importante.

**Achado que vale mais que a escolha do modelo:** em 1 vCPU com a configuração
de threads *default*, o p50 vai a **602 ms** e o p95 a **804 ms** (mpnet: 651 e
806). Sozinho, sem a query SQL, isso já estoura a RNF-01 (p95 < 500 ms). O torch
dimensiona o pool de threads pelo número de CPUs que *enxerga* — 16, no host —
enquanto o cgroup lhe dá 1, e o processo passa o tempo em troca de contexto.
`OMP_NUM_THREADS=1` derruba o p95 de 804 para 63 ms: **13x, de uma variável de
ambiente.** Vale como requisito de deploy tanto quanto a RAM.

**A alavanca (1) do D3.2 foi medida, não assumida** — e paga muito bem: ONNX
Runtime com quantização int8 dinâmica, em build multi-stage onde o torch fica só
no estágio de export e **não entra na imagem final**. Imagem de 2546 para 739 MB
(3,4x), RSS de pico de 1220 para 872 MB, p95 de 63 para 13 ms, carga de 10,5 para
2,5 s. Mesmo modelo, mesma dimensão, mesmo espaço vetorial — exatamente o que a
alavanca (1) prometia, sem tocar em (2).

**Quantizar não quebrou o ranking** — verificado, porque recomendar int8 sem
checar seria trocar um problema de infra por uma falha silenciosa do tipo que
este ADR já alerta. Sobre um mini-corpus pt-BR de 8 produtos e 8 consultas, fp32
e int8 dão **o mesmo top-1 nas 8**, e o cosseno entre os vetores fp32 e int8 do
mesmo texto fica em 0,979 de média (mínimo 0,972). **Ressalva honesta:** 8 casos
descartam quebra grosseira, não provam paridade de qualidade sobre os ~250
produtos. A prova real é a suíte de casos de uso de D1.

Efeito colateral registrado: a margem de separação entre 1º e 2º colocado é bem
menor no e5 (0,04) que no mpnet (0,24). Não é defeito — o e5 comprime a faixa de
cosseno. E **não afeta D4**, que funde por RRF, que é baseado em posição, não em
score absoluto. Se a fusão fosse por limiar de score, afetaria.
