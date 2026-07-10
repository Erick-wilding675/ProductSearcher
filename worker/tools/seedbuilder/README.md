# seedbuilder — gerador do dataset seed (offline)

Ferramenta de **dev** (não faz parte do runtime do worker) que transforma o CSV de
listagem do **Apify** no dataset seed YAML (`worker/seed/products/*.yaml`), no formato
`RawProduct`. Ver [ADR-0001](../../../adr/0001-aquisicao-de-dados.md) e
[ADR-0005](../../../adr/0005-decisoes-fase-2.md).

## Por que existe

Os actors de listagem do Apify (Mercado Livre, Amazon, Magalu) trazem **produto +
preços + item ID**, mas **não** a ficha técnica estruturada. As specs vêm de duas
fontes, nesta ordem de precedência:

1. **API do Mercado Livre** (`/items/{id}` → `attributes`) — specs estruturadas de
   verdade. Exige um **access token** (OAuth) de um app dev gratuito do ML.
2. **Parser de título** (`title_parser.py`) — extrai CPU/RAM/armazenamento/marca do
   título; fallback quando a API não cobre (ou quando não há token).

O que sair sem spec obrigatória é rejeitado no `load` (ADR-0005 D6).

## Uso

```bash
# só título (sem token) — cobertura parcial
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
`.env` automaticamente (via `python-dotenv`), **só na execução por CLI** — os testes não
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
O token **não** é versionado nem usado em runtime — só neste build offline.
`ML_REDIRECT_URI` precisa ser um https público válido (localhost **não** é aceito).

## Estrutura

- `title_parser.py` — specs a partir do título (determinístico).
- `ml_api.py` — cliente HTTP da API do ML (token, `urlopen` injetável para teste).
- `mapping.py` — atributos do ML → nossas `attribute_key`.
- `ml_auth.py` — OAuth do ML (client_credentials / authorization_code / refresh).
- `config.py` — carrega o `.env` do worker nos entry points.
- `build_seed.py` — CLI que junta tudo e grava o YAML.
