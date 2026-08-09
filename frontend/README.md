# frontend/ — Web App (Next.js)

Next.js + TypeScript + Tailwind + shadcn/ui. Consome a mesma API do backend.
Ver [`../docs/design-system.md`](../docs/design-system.md) e [`../docs/wireframes.md`](../docs/wireframes.md).

## Estrutura

```
src/
  app/
    layout.tsx     # layout raiz (tema light/dark)
    page.tsx       # Home / Busca (placeholder)
    globals.css    # tokens (CSS vars) light + dark
  components/      # SearchBar, FilterPanel, ResultCard, ComparisonTable (a criar — Fase 4)
  lib/
    api.ts         # cliente tipado da API
```

## Design tokens

Cor dominante **violet**; aplicação 60-30-10; light + dark. Tokens em `globals.css` e mapeados no `tailwind.config.ts`.

## Rodar (dev)

`npm install && npm run dev` (requer a API em `NEXT_PUBLIC_API_URL`).

## Página sem estilo nenhum? Limpe o `.next`

Sintoma: a página carrega e o React funciona, mas vem sem CSS — e
`/_next/static/css/app/layout.css` responde **404** (o `<link>` existe e a folha
carrega com 0 regras).

Causa: `next build` e `next dev` compartilham o diretório `.next`. Rodar o build
e depois o dev deixa manifests de produção apontando para assets que só existem
em dev (e vice-versa); o CSS é o primeiro a sumir.

Correção: `npm run clean && npm run dev`. O script `build` já limpa antes de
rodar, justamente para não envenenar o dev seguinte.

> Este repositório fica dentro do OneDrive. Além do acima, a sincronização pode
> travar arquivos e gravar `.next`/`node_modules` pela metade. Se o comportamento
> for errático mesmo após o `clean`, pause a sincronização antes de investigar.
