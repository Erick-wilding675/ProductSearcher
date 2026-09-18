# ADR-0011 — Deploy de produção: Fly.io em `gru`, imagem leve, banco em `sa-east-1` e keep-alive por health check

- **Status:** Aceito
- **Data:** 2026-09-18 (proposto em 2026-09-04 por Pedro Faria; aceito com emendas por Erick CMendes)
- **Decisor(es):** Erick CMendes (proposta: Pedro Faria)
- **Relacionado:** [ADR-0004](0004-deploy-free-tier.md) (fecha o "ponto em aberto" do host), [ADR-0010](0010-fase-6-onde-a-ia-entra.md) (busca vetorial opcional e desligada), [ADR-0002](0002-datastore-postgres-only.md) (Postgres/pgvector no Supabase)

> 📐 **Decisão de infraestrutura da Fase 7** — fecha o host do backend (ADR-0004), fixa a região do backend e do banco, e reflete que a busca vetorial ficou fora de produção (ADR-0010).

> 🪞 Espelhar no Document Hub (Notion) como ADR-011 — mesmo documento, numeração de 3 dígitos no Notion e 4 no repositório (`adr/0011-*.md`).

## Contexto

O ADR-0004 fixou **Vercel** (frontend) + **Supabase** (banco) + backend **sem cold
start**, com **Fly.io** como preferência e **Hugging Face Spaces** como alternativa,
mas deixou o **host definitivo do backend como "ponto em aberto"**, a decidir "após um
teste prático de cold start/limites". Três fatos mudaram o quadro desde então:

1. **A busca vetorial saiu de produção (ADR-0010).** O modelo de embedding (~800 MB,
   carregado no próprio processo da API) foi avaliado e **piora a precisão** no catálogo
   atual — pequeno, onde palavras-chave de um produto aparecem em outro sem relação. O
   caminho ficou **desligado por flag** (`vector_enabled = False`, `hybrid_enabled =
   False`). Logo, **produção não carrega o modelo**.

2. **Os free tiers mudaram (set/2026).** O Fly.io **encerrou o free tier**; o
   Hugging Face Spaces passou a **exigir plano pago (PRO)** para Docker Spaces; o Render
   free dorme; o Cloud Run free só sem instância quente.

3. **O banco está longe de onde o backend ia ficar.** O projeto Supabase foi
   provisionado em **us-east-1** na Fase 1, quando ainda não havia decisão de região para
   a API. A proposta original desta ADR colocava a API em `gru` (São Paulo) mantendo o
   banco na Virgínia — e é isso que a revisão desta ADR derrubou (ver D3).

Com o modelo fora de produção, os quatro requisitos de host do comunicado da Fase 7
(RAM ≥ 1 GB, `OMP_NUM_THREADS=1`, imagem de ~886 MB) valem **apenas para a imagem de
teste**. A produção roda a **imagem leve** (~102 MB comprimida / ~294 MB em disco), que
cabe em qualquer tier pequeno.

## Decisão

**D1 — Duas imagens; produção é a leve.** A produção usa `api/Dockerfile` (leve, sem
modelo). A imagem pesada (`api/Dockerfile.vector`, com o embedding de ~800 MB) existe
**apenas para testes**. A busca vetorial permanece desligada por flag (`vector_enabled =
False`), coerente com o ADR-0010 ("IA é complementar; liga quando ajudar").

**D2 — Host do backend: Fly.io, `shared-cpu-1x` com 256 MB, na região `gru`.** Fecha o
ponto em aberto do ADR-0004. O "sem cold start" é determinístico
(`auto_stop_machines = false`, `min_machines_running = 1`), e não uma promessa de plano.
O dimensionamento vem de medição: a API leve estabiliza em **~87 MB de RSS** (uvicorn,
FastAPI, SQLAlchemy, psycopg; medido em 15/09/2026 fora do container), o que cabe em
256 MB com folga de ~2,5x depois do sistema. Preço de referência do Fly:
**US$1,94/mês** para `shared-cpu-1x`/256 MB e US$3,19/mês para 512 MB, em `iad`; `gru`
tem **acréscimo regional** (o Fly não publica o multiplicador por região). IPv4
compartilhado não custa nada; IPv4 dedicado custaria US$2/mês e **não é necessário**.

> Gatilho de revisão de D2: qualquer OOM kill, ou p95 subindo sem explicação de banco,
> manda para 512 MB (US$3,19/mês). É uma linha do `fly.toml`, não uma migração.

**D3 — O banco vai para `sa-east-1` (São Paulo), junto do backend.** Esta é a emenda
que mais muda o desenho proposto. Uma busca faz de **3 a 5 idas ao banco** (o
`pool_pre_ping`, a consulta de retrieval, o fallback do ADR-0010 D2 quando existe, o
`INSERT` no log de buscas e seu commit). Com a API em `gru` e o banco em `us-east-1`,
cada ida cruza o continente (RTT típico São Paulo–Virgínia na casa de 110–130 ms, valor
de referência, **ainda não medido por nós**), o que põe **400–600 ms só de rede** dentro
de uma requisição cujo orçamento inteiro é de 500 ms (RNF-01). Colar os dois na mesma
região deixa cada ida em poucos milissegundos e mantém o usuário brasileiro perto da
API — o custo transcontinental sai do caminho crítico repetido e não aparece em lugar
nenhum.

O preço disso é operacional e pago uma vez: **criar um projeto Supabase novo em
`sa-east-1`, habilitar `pgvector`, aplicar as migrations, recarregar o seed e trocar o
segredo**. Não há migração de dado vivo a preservar — o catálogo é reproduzível pela
ingestão (ADR-0001/0009) e a tabela `searches` ainda não tem consulta real (ADR-0010).
Runbook: [`infra/deploy/supabase-sa-east-1.md`](../infra/deploy/supabase-sa-east-1.md).

**D4 — Keep-alive do Supabase via health check do host.** Em vez de um pipeline externo
agendado, o keep-alive é um **health check configurado no próprio deploy** (Fly.io,
`[[http_service.checks]]`), sondando `/health` a cada **30 s**. Como o `/health` já
executa um `SELECT 1`, a própria sondagem mantém o serviço acordado **e** o banco ativo
(evita a pausa por inatividade do plano free), sem serviço extra nem segredo.

Dois detalhes que tornam isso seguro, e que valem por serem propriedades do código e não
intenções: `/health` **sempre responde 200** e informa o estado do banco no campo `db`
("ok"/"down"), então uma oscilação do Supabase **não** faz o proxy do Fly tirar a máquina
de rota; e a checagem não acorda nada, porque a máquina nunca dorme (D2).

> ⚠️ Risco registrado: a documentação do Supabase define atividade como "atividade de
> banco do usuário" e **não diz explicitamente** se tráfego via pooler conta. Gatilho de
> revisão: se o projeto pausar mesmo com o check no ar, troca-se o `SELECT 1` por uma
> escrita periódica em tabela própria, ou volta-se ao cron externo.

**D5 — CORS de produção sem curinga.** `CORS_ORIGINS` recebe **a origem exata do web
app em produção**; previews da Vercel não falam com a API de produção. O
`CORSMiddleware` compara origem como string exata — `*.vercel.app` **não funcionaria**
como foi escrito na proposta, e, se fosse transformado em regex, liberaria qualquer
aplicação hospedada na Vercel. O `cors_origin_regex` continua servindo só às extensões
(`chrome-extension://…`), como está em `app/core/config.py`.

**D6 — A extensão aponta para produção por padrão.** `extension/src/shared/config.js`
passa a ter as URLs de produção, e `manifest.json` lista a origem da API em
`host_permissions` (mantendo `localhost` para desenvolvimento). Sem isso, o popup sobre
a SERP — que é o argumento inteiro do "sem cold start" — não funcionaria em produção.

**D7 — Migrations não rodam no deploy.** Sem `release_command`. O DDL do Alembic exige o
**pooler de sessão (5432)**, enquanto o runtime usa o **pooler de transação (6543)** com
`prepare_threshold=None` (ADR-0005); embutir migration no deploy obrigaria a carregar uma
segunda credencial no host só para isso. Migration é passo manual do runbook, executado
antes do deploy que depende dela.

**D8 — Deploy disparado pela CI.** `.github/workflows/deploy-backend.yml` escuta o
`workflow_run` da CI: **só quando a CI conclui com sucesso na `main`** ele roda
`flyctl deploy --remote-only` sobre o commit exato que passou. Segredo:
`FLY_API_TOKEN` no GitHub. O frontend segue o caminho nativo da Vercel (integração Git,
deploy a cada push na `main`).

> 💡 O que destrava tudo: como a produção **não** carrega o modelo (ADR-0010), o backend ficou leve e o host deixou de ser o problema pesado — uma máquina de 256 MB resolve, sem cold start.

## Benefícios

- **Sem cold start perceptível** (RNF-02), inclusive no popup da extensão sobre a SERP.
- **Latência de banco fora do caminho crítico** (D3): o orçamento de 500 ms da RNF-01
  volta a ser gasto com trabalho, não com rede.
- **Custo baixo e previsível** (~US$2/mês, mais o acréscimo regional de `gru`) e **deploy
  simples** (PaaS, Docker nativo, build remoto do Fly a partir da CI).
- **Imagem leve** → deploy rápido, pouca RAM, menor superfície.
- **Keep-alive sem segredo** e cobrindo backend + banco num ping só.
- **Produção determinística e sem IA**, alinhada ao princípio do ADR-0010.

## Consequências negativas

- ⚠️ **Não é US$0.** O free tier do Fly morreu. Aceito em troca de simplicidade e
  ausência de cold start; as alternativas a US$0 têm cold start ou exigem operar uma VM.
- ⚠️ **Trocar a região do banco custa uma reconstrução** (projeto novo, migrations, seed,
  segredo trocado) e **invalida a connection string documentada na Fase 1**.
- **Duas imagens para manter** (leve/produção e pesada/teste) — mitigado por serem o
  mesmo código atrás de uma flag.
- **256 MB tem folga menor que 512 MB**; o gatilho de D2 existe por causa disso.
- **Dependência de conta/cartão no Fly.**
- **O keep-alive depende do backend no ar** (se o serviço cair, não pinga) — aceitável:
  o objetivo é evitar a pausa por inatividade, não monitorar uptime.
- **Previews da Vercel não conversam com a API de produção** (D5). Testar PR contra a API
  real exige adicionar a origem do preview à mão.

## Alternativas descartadas

| Alternativa | Por que não (agora) |
| --- | --- |
| **API em `iad`, banco onde está (`us-east-1`)** | Resolve a latência do banco sem migrar nada, mas joga o usuário brasileiro para a Virgínia em toda navegação do web app e do popup. Entre pagar o oceano uma vez por requisição (esta) ou 3–5 vezes (a proposta original), a melhor é não pagar: ambos em São Paulo. |
| Manter API em `gru` e banco em `us-east-1` (proposta original) | 400–600 ms de rede por busca contra um orçamento de 500 ms (RNF-01). Descartado na revisão. |
| Hugging Face Spaces | Docker Space passou a exigir plano pago (PRO, ~US$9/mês) — mais caro que o Fly e fora do ~US$0. |
| Google Cloud Run | US$0, mas scale-to-zero = cold start (~1–2 s), indesejado para o popup da extensão (ADR-0004). |
| GCP e2-micro / Oracle Always Free | US$0 e sem cold start, mas IaaS: exige montar e manter uma VM (Docker + proxy + TLS); a Oracle ainda é ARM (rebuild). Custo de operação supera a economia. |
| Render free | Dorme após 15 min (cold start de 30–60 s) — já vetado no ADR-0004. |
| Máquina de 512 MB desde já | US$3,19/mês para uma aplicação medida em 87 MB. Vira decisão só com sintoma (gatilho de D2). |
| Manter a busca vetorial em produção | Piora a precisão no catálogo atual (ADR-0010) e exigiria host ≥ 1 GB. Religar só quando o catálogo justificar. |
| Keep-alive por cron externo (GitHub Actions) ou com a `DATABASE_URL` mestra num secret | O cron é um serviço a mais a manter; a `DATABASE_URL` mestra num segredo de CI é privilégio alto. Preferido: health check do host no `/health` — sem serviço extra e sem segredo. |
| `release_command` do Fly rodando `alembic upgrade head` | Exigiria a credencial do pooler de sessão no host, só para DDL (D7). |

## Emendas à proposta de 04/09 (rastreabilidade)

A proposta do Pedro foi aceita na direção (imagem leve + Fly sem cold start) e emendada
em cinco pontos, todos achados ao confrontar o texto com o código:

| # | O que a proposta dizia | O que ficou decidido |
| --- | --- | --- |
| E1 | `gru`, com o banco em `us-east-1` | `gru` **e** banco em `sa-east-1` (D3) |
| E2 | "512 MB, ~US$2/mês" | 256 MB a US$1,94 (512 MB custa US$3,19) — D2 |
| E3 | `CORS_ORIGINS` com `*.vercel.app` | origem exata de produção; curinga não funciona no `CORSMiddleware` (D5) |
| E4 | (não mencionava a extensão) | extensão apontando para produção, com `host_permissions` (D6) |
| E5 | "configuração exata do check a cargo de quem faz o deploy" | `/health` a cada 30 s, com o porquê de isso não derrubar a API (D4); migrations fora do deploy (D7) |

## Caminho de evolução / gatilho de revisão

- **Gatilho de IA / RAM:** se o catálogo crescer a ponto de a busca vetorial passar a
  ajudar (ADR-0010), religar `vector_enabled` traz a imagem pesada para produção →
  reavaliar host e plano (RAM ≥ 1 GB). Revisar D1 e D2 juntos.
- **Gatilho de RAM (sem IA):** OOM kill ou p95 inexplicado → 512 MB.
- **Gatilho de custo:** se o valor mensal incomodar, migrar para uma VM free (e2-micro),
  assumindo o custo de operação, ou reabrir a arquitetura.
- **Gatilho do keep-alive:** projeto pausado mesmo com o check no ar → escrita periódica
  ou cron externo (D4).
- **Gatilho de uptime:** se for preciso monitorar (não só evitar a pausa), trocar o
  keep-alive por um monitor de verdade.
- **Pendência de medição:** os 110–130 ms de RTT usados em D3 são valor de referência.
  Medir com o serviço no ar (a task de cold start da Fase 7 já tem o script) e registrar
  aqui o número real.

## Impacto futuro

- **Código/infra:** `api/fly.toml` (deploy + health check do keep-alive);
  `.github/workflows/deploy-backend.yml` (deploy após a CI);
  `infra/deploy/fly.md` e `infra/deploy/supabase-sa-east-1.md` (runbooks).
- **Variáveis/segredos:** `NEXT_PUBLIC_API_URL` (Vercel) aponta para a URL do Fly;
  secret `FLY_API_TOKEN` no GitHub; `DATABASE_URL` e `CORS_ORIGINS` como secrets do Fly.
- **Extensão:** `extension/src/shared/config.js` e `manifest.json` com as origens de
  produção.
- **Documentação:** substitui parcialmente o ADR-0004 (fecha o ponto em aberto do host) e
  torna obsoleta a região registrada em `infra/deploy/supabase.md`.
