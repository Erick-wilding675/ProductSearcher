# Wireframes

> Fidelidade **low/mid-fi** (estrutural; o visual final segue o [design system](design-system.md)).

## Arquivo no Figma

[ProductSearcher — Wireframes (MVP)](https://www.figma.com/design/cLPke6gwD5fPvotKU1hWiK/ProductSearcher-%E2%80%94-Wireframes--MVP-?node-id=0-1)

## Telas (escopo desta iteração)

### 01 — Busca + Resultados (UC-01/03 · RF-10/12/30/40/43)
Navbar com busca · sidebar de filtros (categoria/preço/marca) · cards de resultado rankeados (badge, chips de specs, loja/avaliação, preço, comparar).

### 02 — Comparação (UC-02 · RF-20/21/41)
Cabeçalho com produtos (2–4) · tabela de atributos linha a linha · **destaque do melhor valor por linha** (cor + peso) + legenda. Só compara produtos da mesma categoria.

### 03 — Popup da extensão (UC-05 · RF-50/51/52/54)
SERP simulada ao fundo · popup ProductSearcher com "Top 3 para ‹query›", mini-cards e link "Ver todos no ProductSearcher →". Ativa só em categoria coberta; envia apenas a query (sem PII).

## Pendências (próximas iterações)

- Tela de **detalhe do produto** (RF-42).
- Estados loading/vazio/erro em todas as telas.
- Versão **mobile** (coluna única).
- Component Spec (estados: default/hover/active/disabled/loading).
