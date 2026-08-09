# extension/ — Extensão Chrome (Manifest V3)

Cliente fino da **mesma API** do web app (ADR-0003). Na SERP do Google, mostra o top-N
do catálogo para a busca — **apenas** quando a categoria é coberta.

Ver [`../docs/wireframes.md`](../docs/wireframes.md) (tela 03) e
[`../docs/design-system.md`](../docs/design-system.md).

## Estrutura

```
manifest.json           # MV3
src/
  shared/
    config.js           # URLs da API e do web app, TOP_N, TTL do cache
    coverage.js         # decide cobertura + extrai a query da URL (puro, testável)
    api.js              # cliente da API — SÓ para o service worker
  background/
    service-worker.js   # único ponto que fala com a API; cache de cobertura
  content/
    content.js/.css     # painel na SERP + fallback de botão flutuante
  popup/
    popup.html/.js/.css # top-N da aba atual
tests/                  # node --test (runner nativo, sem dependência)
```

## Como funciona

```
SERP  ──lê ?q= da URL──▶  content.js
                              │  mensagem
                              ▼
                       service-worker.js  ──▶  GET /categories   (cache 1h)
                              │                GET /search
                              ▼
                     categoria coberta?  ──não──▶  silêncio
                              │ sim
                              ▼
                   injeta painel  ──falhou?──▶  botão flutuante
```

### Por que a rede passa toda pelo service worker

Um `fetch` disparado do content script sai com a **origem da página** (`google.com`),
que o CORS da API não libera — o regex do backend só aceita `chrome-extension://`.
O service worker tem a origem da extensão, então é ele quem chama a API. De quebra,
content script e popup compartilham o mesmo cache de cobertura.

### Ativação por cobertura

A decisão é **local**: baixamos as categorias cobertas uma vez (`GET /categories`,
cache de 1h) e comparamos com a busca em `coverage.js`. Consultar a API a cada SERP
exporia buscas que nada têm a ver com produto — e a extensão roda em toda SERP.

As palavras-chave saem do `slug` e do `name` que a API devolve, mais uma tabela local
de sinônimos (`fone`, `headset`, `laptop`…). Uma categoria nova no catálogo já funciona
sem republicar a extensão, desde que o nome dela seja o termo que as pessoas digitam;
casos como "fone" para "Fones de ouvido" precisam entrar em `SINONIMOS`.

> O backend tem a mesma noção em `RuleBasedIntentParser`. A duplicação é consciente:
> aqui é só um **pré-filtro** tolerante (erra para o lado de ativar); quem decide a
> categoria de verdade é a API.

## Privacidade (RNF-09)

**Só a busca sai do navegador — e só quando a categoria é coberta.**

O que é enviado à API:

| Enviado                          | Quando                                    |
| -------------------------------- | ----------------------------------------- |
| O texto do parâmetro `q` da SERP | Só se a busca casar com categoria coberta |

O que **não** é enviado, lido nem armazenado:

- Nenhum outro parâmetro da URL da SERP (`ei`, `sclient`, etc. são descartados —
  `queryDaSerp` lê exclusivamente `q`)
- Conteúdo, DOM ou resultados da página do Google
- Histórico, outras abas, cookies, `localStorage` do Google
- Qualquer identificador de usuário: a extensão **não** tem login, telemetria,
  analytics ou identificador persistente

Permissões pedidas, e por quê:

| Permissão                          | Motivo                                                                |
| ---------------------------------- | --------------------------------------------------------------------- |
| `storage`                          | Guardar o cache das categorias cobertas (não guarda buscas)           |
| `activeTab`                        | Ler a URL da aba **no clique** do usuário, para o popup saber a busca |
| `host_permissions: localhost:8000` | Falar com a API do ProductSearcher                                    |

Não pedimos `tabs` (que daria acesso a todas as abas) nem `history`. `activeTab` é
concedida pelo Chrome só no gesto do usuário e expira — é o menor privilégio que
atende ao caso.

O `content_scripts.matches` restringe a execução a `google.com/search` e
`google.com.br/search`: em qualquer outro site a extensão nem carrega.

## Rodar em dev

1. Suba a API: `docker compose up -d db api` na raiz (ver `../api/README.md`)
2. `chrome://extensions` → ative **Modo do desenvolvedor** → **Carregar sem compactação**
   → aponte para esta pasta
3. Busque "melhor notebook gamer" no Google

Apontando para outro backend: ajuste `API_BASE_URL` em `src/shared/config.js` **e**
`host_permissions` no `manifest.json` — trocar só um dos dois faz toda requisição
falhar por permissão.

## Testes

`npm test` (ou `node --test`) — cobre a decisão de cobertura e a extração da query,
que é onde mora a regra de negócio. O resto é DOM e rede, verificados carregando a
extensão.

## Limitações conhecidas

- **Seletores da SERP são frágeis.** O Google muda o DOM sem aviso; por isso o
  fallback de botão flutuante existe (RF-53).
- **Só Google.** Outros buscadores exigiriam novos `matches` e âncoras.
- `API_BASE_URL` aponta para `localhost`. Publicar exige o host de produção aqui e em
  `host_permissions` (Fase 7).
- `package.json` existe só para os testes (`type: module`); o Chrome o ignora.
