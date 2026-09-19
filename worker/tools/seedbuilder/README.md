# seedbuilder: gerador do dataset seed (offline)

Ferramenta de **dev** (não faz parte do runtime do worker) que transforma o CSV de
listagem do **Apify** no dataset seed YAML (`worker/seed/products/*.yaml`), no formato
`RawProduct`. Ver [ADR-0001](../../../adr/0001-aquisicao-de-dados.md) e
[ADR-0005](../../../adr/0005-decisoes-fase-2.md).

## Por que existe

Os actors de listagem do Apify (Mercado Livre, Amazon, Magalu) trazem **produto +
preços + item ID**, mas **não** a ficha técnica estruturada. As specs vêm de duas
fontes, nesta ordem de precedência:

1. **API do Mercado Livre** (`/products/{id}` → ficha técnica) para specs estruturadas de
   verdade, mais `/products/{id}/items` para as ofertas concorrentes e `/users/{id}` para a
   loja. Exige um **access token** (OAuth) de um app dev gratuito do ML.

   > `/items/{id}` e `/sites/MLB/search` respondem **403** para token de aplicação. O
   > `external_id` do seed é id de **produto de catálogo**, não de anúncio, e foi confundir
   > os dois que manteve o enriquecimento sem funcionar por semanas.
2. **Parser de título** (`title_parser.py`), que extrai CPU, RAM, armazenamento e marca do
   título. É o fallback para quando a API não cobre o produto ou não há token.

O que sair sem spec obrigatória é rejeitado no `load` (ADR-0005 D6).

## Uso

```bash
# só título (sem token), cobertura parcial
python -m tools.seedbuilder.build_seed \
  --csv dataset_mercadolivre.csv --category notebooks \
  --out seed/products/notebooks.yaml

# com enriquecimento da API do ML
export ML_ACCESS_TOKEN="APP_USR-..."
python -m tools.seedbuilder.build_seed \
  --csv dataset_mercadolivre.csv --category notebooks \
  --out seed/products/notebooks.yaml
```

## Configuração (`.env`)

Copie `worker/.env.example` para `worker/.env` e preencha. Os entry points carregam o
`.env` automaticamente (via `python-dotenv`), **só na execução por CLI**: os testes não
herdam segredos. Variáveis: `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`,
`ML_REFRESH_TOKEN`, `ML_ACCESS_TOKEN`. O `.env` está no `.gitignore`.

## Como obter o `ML_ACCESS_TOKEN`

Crie um app dev gratuito em https://developers.mercadolivre.com.br e use o helper
`ml_auth` (lê as credenciais do `.env`):

```bash
# 1) caminho curto: token de app (se o app tiver "Client Credentials")
python -m tools.seedbuilder.ml_auth token

# 2) caminho com login (authorization_code), se o item exigir token de usuário
python -m tools.seedbuilder.ml_auth url               # abra, autorize, copie o code
python -m tools.seedbuilder.ml_auth exchange --code TG-...   # → access_token + refresh_token
python -m tools.seedbuilder.ml_auth refresh           # renova via ML_REFRESH_TOKEN
```

Pegue o `access_token` da saída e coloque em `ML_ACCESS_TOKEN` no `.env` (validade ~6h).
O token **não** é versionado nem usado em runtime, apenas neste build offline.
`ML_REDIRECT_URI` precisa ser um https público válido (localhost **não** é aceito).

## Estrutura

| Arquivo | Papel |
| --- | --- |
| `build_seed.py` | CLI que junta tudo e grava o YAML |
| `title_parser.py` | Specs a partir do título do anúncio, determinístico |
| `ml_api.py` | Cliente HTTP da API do Mercado Livre (`urlopen` injetável para teste) |
| `ml_auth.py` | OAuth do ML: `client_credentials`, `authorization_code` e `refresh` |
| `mapping.py` | Traduz os ids de atributo do ML para as nossas `attribute_key` |
| `config.py` | Carrega o `.env` do worker nos entry points |
| `enrich.py` | Enriquece um seed já coletado pela **API**: `model`, `description`, specs completas, ofertas concorrentes e URL da loja |
| `backfill.py` | Re-deriva campos ausentes a partir dos **títulos já salvos**, quando o `title_parser` melhora. Não exige credencial |
| `label_use_cases.py` | Rotula `use_case` por LLM, offline (ADR-0010 D2) |

## Enriquecer um seed já coletado

`build_seed.py` exige o CSV original do Apify e refaz a coleta inteira. Para melhorar um
seed que já existe, use os dois irmãos, que trabalham no lugar e são **idempotentes e
conservadores** (nunca sobrescrevem valor existente):

```bash
python -m tools.seedbuilder.enrich              # busca na API do ML
python -m tools.seedbuilder.backfill --dry-run  # re-deriva do título, só relata
python -m tools.seedbuilder.backfill            # aplica
```

O `enrich.py` carimba cada produto em `_enrichment` com data e status, então reexecutar
tenta de novo apenas o que faltou. Produto despublicado (404) fica marcado como `stale` e
mantém o que veio do título, sem apagar nada.

## Rotular `use_case`

```bash
python -m tools.seedbuilder.label_use_cases
```

Este é o **único** ponto do projeto em que um LLM toca o dado, e ele roda offline, uma
vez, com o resultado gravado e medido contra gabarito. Em runtime o rótulo vira um filtro
JSONB comum: zero IA no caminho da resposta, zero latência e zero custo por requisição.

Guardas que o ADR-0010 D2 exige:

- **Conjunto fechado.** Os rótulos permitidos saem de `seed/categories.json` e entram no
  schema da resposta. Rótulo fora da lista é rejeitado na validação antes de chegar ao
  banco.
- **Nada de inventar atributo.** O prompt recebe apenas nome, modelo, descrição e as specs
  que **já estão no banco**. O LLM classifica o que existe, não completa ficha técnica.
- **Idempotente e carimbado** em `attributes._labeling` (data e modelo). Reexecutar tenta
  só o que faltou.

O provider é a Groq, cujo plano gratuito não expõe Batch API; o script respeita o limite
de tokens por minuto lendo os cabeçalhos `x-ratelimit-*` e pausando.

> **Recarregar o seed apaga os rótulos**, porque o upsert de `product_specs` reescreve os
> atributos. Re-rotular é passo obrigatório do runbook depois de qualquer recarga.
