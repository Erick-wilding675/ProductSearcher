# frontend: web app (Next.js)

Next.js 14 (App Router), TypeScript, Tailwind e shadcn/ui. Consome a mesma API que a
extensão. Ver [`../docs/design-system.md`](../docs/design-system.md) e
[`../docs/wireframes.md`](../docs/wireframes.md).

## Estrutura

```
src/
  app/
    layout.tsx              layout raiz, tema light e dark
    page.tsx                busca e resultados (RF-40/43)
    compare/page.tsx        painel de comparação (RF-41)
    products/[id]/page.tsx  detalhe do produto (RF-42)
    globals.css             tokens em CSS vars, light e dark
  components/
    SearchBar/              entrada da consulta
    FilterPanel/            categoria, preço, marca e specs
    ResultCard/             card de resultado, com specs e preço
    ComparisonTable/        tabela comparativa com destaque por linha
    SortSelect/             ordenação
    RankPreferenceSelect/   preferência de ranking (rank_by)
    Pagination/             paginação
    ThemeToggle/            alternância de tema
    states/                 vazio, erro e carregamento
    ui/                     primitivos do shadcn (button, skeleton)
  lib/
    api.ts                  cliente tipado da API
    utils.ts
tests/e2e/                  smoke test em Playwright
```

## Design tokens

Cor dominante violet, aplicação 60-30-10, light e dark desde o MVP. Os tokens vivem em
`globals.css` como CSS vars e são mapeados no `tailwind.config.ts`. **Não use hex solto nos
componentes:** a alternância de tema depende de os valores passarem pelas vars.

## Rodar em dev

```bash
npm install
npm run dev
```

Requer a API acessível em `NEXT_PUBLIC_API_URL` (ver `.env.example`). Sem ela, as páginas
sobem e mostram o estado de erro.

## Testes

| Comando                   | O que cobre                                         |
| ------------------------- | --------------------------------------------------- |
| `npm run lint`            | ESLint                                              |
| `npm run format:check`    | Prettier                                            |
| `npm run build`           | Build de produção, que é o que a CI verifica        |
| `npm run test:e2e`        | Playwright: busca, seleção de produtos e comparação |
| `npm run test:e2e:headed` | O mesmo, com o navegador visível                    |

O E2E exige a **API de pé e com catálogo carregado**; o web app ele mesmo sobe, porque
`playwright.config.ts` declara um `webServer` que roda `npm run dev`. Como esse bloco usa
`reuseExistingServer: false`, um `npm run dev` já aberto na 3000 faz o teste falhar ao
subir o próprio servidor: derrube o seu antes.

Na primeira execução, instale os navegadores: `npx playwright install chromium`.

> `@storybook/nextjs-vite` está nas devDependencies e existem arquivos `*.stories.tsx`,
> mas **o Storybook não está executável**: falta o diretório `.storybook/` e o script no
> `package.json`. Ou se completa a instalação, ou as stories saem do repositório.

## Página sem estilo nenhum? Limpe o `.next`

Sintoma: a página carrega, o React funciona, mas vem sem CSS, e
`/_next/static/css/app/layout.css` responde **404** (o `<link>` existe e a folha carrega
com zero regras).

Causa: `next build` e `next dev` compartilham o diretório `.next`. Rodar o build e depois o
dev deixa manifests de produção apontando para assets que só existem em dev, e vice-versa.
O CSS é o primeiro a sumir.

Correção: `npm run clean && npm run dev`. O script `build` já limpa antes de rodar,
justamente para não envenenar o dev seguinte.

> Este repositório fica dentro do OneDrive. Além do acima, a sincronização pode travar
> arquivos e gravar `.next` e `node_modules` pela metade. Se o comportamento continuar
> errático depois do `clean`, pause a sincronização antes de investigar.
