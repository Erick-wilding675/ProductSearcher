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
