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
  **fechado em D3.1**. Resta medir o envelope de recursos e emitir o comunicado
  ao Pedro antes de ele escolher o host da Fase 7. Se a medição não couber em
  host viável, reabrir por D3.2 na ordem ali definida.
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
