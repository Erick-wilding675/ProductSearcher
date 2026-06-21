# Design system

> Hero color **Roxo/Lilás (Violet)** · 60-30-10 · light + dark · Inter. Swatch visual: `../design-palette-preview.html`.

## Princípios

- Clareza acima de decoração; cor guia a atenção.
- Hierarquia por **tons da mesma família** (violet + neutros).
- Mesmos tokens entre web app e extensão.
- Acessível por padrão; tokenizado (light/dark).

## Hero — Violet

| Token | Hex | Uso |
| --- | --- | --- |
| violet-50 | #F5F3FF | fundos suaves, chips |
| violet-100 | #EDE9FE | superfície de destaque |
| violet-200 | #DDD6FE | bordas/realces |
| violet-300 | #C4B5FD | hero no dark (texto/links) |
| violet-400 | #A78BFA | ícones, primary no dark |
| **violet-500** | **#8B5CF6** | cor de marca / acento |
| violet-600 | #7C3AED | botão primary (texto branco, AA) |
| violet-700 | #6D28D9 | hover do primary |
| violet-800 | #5B21B6 | pressionado |
| violet-900 | #4C1D95 | texto sobre violet claro |

## Neutros

`#FFFFFF · #F8FAFC · #F1F5F9 · #E2E8F0 · #CBD5E1 · #94A3B8 · #64748B · #475569 · #334155 · #1E293B · #0F172A · #0B1220`

## Semânticas

success #16A34A · warning #F59E0B · error #DC2626 · info #2563EB · accent opcional (oferta) #EC4899.

## Tokens por tema

| Token | Light | Dark |
| --- | --- | --- |
| bg | #F8FAFC | #0B1220 |
| surface | #FFFFFF | #1E293B |
| border | #E2E8F0 | #2A3852 |
| text | #0F172A | #F8FAFC |
| text-muted | #64748B | #94A3B8 |
| primary | #7C3AED | #A78BFA |
| primary-on | #FFFFFF | #0B1220 |
| focus-ring | #A78BFA | #C4B5FD |

## Acessibilidade

WCAG AA: texto ≥ 4.5:1; UI/large ≥ 3:1. **violet-500 não passa** para texto pequeno em branco → texto/botões usam violet-600/700. Estado nunca só por cor (cor + ícone/peso). Foco sempre visível.

## Tipografia

**Inter.** Display 32/40 · H1 28/36 · H2 22/30 · H3 18/26 · Body L 16/24 · Body 14/20 · Small 12/16 · Caption 11/14. Pesos 400/500/600/700.

## Forma

Espaçamento (4px): 4/8/12/16/24/32/48/64 · Raio: 6/8/12/16/full · Sombra: sm/md/lg · Grid: container 1200–1280, 12 col, gutter 24.
