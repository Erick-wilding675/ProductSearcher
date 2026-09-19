# Wireframes

> Fidelidade low/mid-fi (estrutural). O visual final segue o
> [design system](design-system.md).

## Arquivo no Figma

[ProductSearcher, wireframes do MVP](https://www.figma.com/design/cLPke6gwD5fPvotKU1hWiK/ProductSearcher-%E2%80%94-Wireframes--MVP-?node-id=0-1)

Os wireframes são o desenho estrutural da Fase 4, não o estado atual da interface. Quando
divergirem do que está no ar, vale o código em `frontend/src/`.

## Telas

### 01. Busca e resultados

Cobre UC-01 e UC-03 (RF-10/12/30/40/43). Navbar com busca, painel lateral de filtros
(categoria, preço, marca, specs), cards de resultado rankeados com badge, chips de specs,
loja, preço e ação de comparar.

Implementado em `frontend/src/app/page.tsx`, com `SearchBar`, `FilterPanel`, `ResultCard`,
`SortSelect`, `RankPreferenceSelect` e `Pagination`.

### 02. Comparação

Cobre UC-02 (RF-20/21/41). Cabeçalho com os produtos escolhidos (de 2 a 4), tabela de
atributos linha a linha, destaque do melhor valor por linha (cor mais peso) e legenda.
Compara apenas produtos da mesma categoria.

Implementado em `frontend/src/app/compare/page.tsx` e `ComparisonTable`.

### 03. Popup da extensão

Cobre UC-05 (RF-50/51/52/54). SERP ao fundo, painel do ProductSearcher com "Top 3 para
‹query›", mini-cards e link para ver todos no web app. Ativa apenas em categoria coberta e
envia somente a query.

Implementado em `extension/src/content/` e `extension/src/popup/`.

## O que foi entregue depois do desenho

| Item | Onde |
| --- | --- |
| Detalhe do produto (RF-42) | `frontend/src/app/products/[id]/page.tsx` |
| Estados de carregamento, vazio e erro (RF-43) | `frontend/src/components/states/` |
| Alternância de tema light e dark | `ThemeToggle` |
| Filtro por specs disponíveis no pool atual | `FilterPanel`, alimentado por `GET /spec-options` |

## Pendências

- **Versão mobile em coluna única** desenhada no Figma. O código já é responsivo por
  breakpoints do Tailwind, mas o desenho não acompanha.
- **Component Spec** com os estados de cada componente (default, hover, active, disabled,
  loading). Os estados existem no código, e há arquivos `*.stories.tsx` em
  `frontend/src/components/`, mas o Storybook **não está executável**: falta o diretório
  de configuração `.storybook/` e o script no `package.json`. Ou se completa a instalação,
  ou as stories saem do repositório.
- **Auditoria de acessibilidade** sobre as três telas (RNF-11).
