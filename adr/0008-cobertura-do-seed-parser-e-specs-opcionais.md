# ADR-0008 — Cobertura do seed: parser de título e specs opcionais

- **Status:** Aceito
- **Data:** 2026-08-09
- **Decisor(es):** Erick

## Contexto

A ingestão aceitava **167 de 279** produtos do seed (60%). O backlog registrava a
causa como "specs obrigatórias ausentes". O levantamento contra o seed mostrou
outro quadro:

| Causa | Produtos | Onde |
| --- | ---: | --- |
| `marca ausente` | 60 | normalização (`normalize.py`) |
| `headphones.type` ausente | 28 | validação de specs |
| `notebooks`: `cpu`/`ram_gb`/`storage_gb`/`storage_type` ausentes | 25 | validação de specs |
| `slug duplicado` | 1 | normalização |

Ou seja: **54% das rejeições não tinham nada a ver com specs** — eram anúncios
cujo título o `title_parser` não sabia atribuir a uma marca. Marca é obrigatória
na normalização (compõe o slug determinístico, ADR-0005 D3), então o produto nem
chegava à validação.

Documentar a causa errada é pior que não documentar: leva a mexer na regra de
validação quando o defeito estava no parser. Fica registrada aqui a correção.

## Decisão

Duas frentes, nesta ordem:

**1. Ampliar o `title_parser` (ataca a causa principal).**

- 20 marcas menores do marketplace no dicionário `BRANDS` (Dapon, Olafvi, JSKJ,
  Davely, Lumva, HTC…) — todas literais nos títulos já coletados.
- Inferência de `headphones.type` para formatos que o marketplace descreve pela
  fixação na orelha (`ear-clip`, `ear cuff`, `open ear`, condução óssea/aérea) e
  um fallback de último recurso: fone "sem fio/bluetooth" sem nenhum outro
  marcador vira `earbuds`. Qualquer marcador explícito tem precedência.

**2. Tornar opcionais** `headphones.type` e `notebooks.cpu`/`ram_gb`/
`storage_gb`/`storage_type` em `worker/seed/categories.json`.

Como o seed em `seed/products/*.yaml` é a **saída** do `build_seed.py` (que exige
credencial do Mercado Livre), a melhoria do parser é aplicada aos títulos já
coletados por `tools/seedbuilder/backfill.py` — as mesmas funções, só que sobre o
YAML versionado, preenchendo apenas o que falta e sem sobrescrever nada.

Resultado: **252 de 279 (90%)**. Só o parser levou 167 → 225; as regras
relaxadas, 225 → 252.

## Benefícios

- Catálogo 51% maior, com dado **derivado do título do anúncio** — nada inventado.
- A causa real (marca) foi corrigida onde nasce, e não mascarada afrouxando a
  validação de specs.
- `backfill.py` é idempotente e coberto por teste: reexecutar não muda nada, e a
  melhoria do parser fica reprodutível sem refazer a coleta.
- As 27 rejeições restantes são legítimas: anúncios genéricos sem marca alguma.

## Consequências negativas

- **`required` fica sem efeito prático nas duas categorias do MVP.** Só
  `headphones.anc` segue obrigatório (o parser sempre o resolve, porque ausência
  de menção = `false`). A regra `required` de `validate_specs` continua correta e
  testada, mas nenhum dado do seed atual a exercita.
- **Comparação e filtro por atributo ficam mais esburacados.** Produtos entram no
  catálogo sem `cpu`/`ram_gb`/`storage_gb`; a `ComparisonTable` mostra `—` e o
  filtro estruturado (RF-12, containment JSONB) simplesmente não os alcança.
- **O fallback de `type` é uma heurística.** Acerta na quase totalidade deste
  catálogo, mas um over-ear anunciado só como "fone sem fio" será rotulado
  `earbuds` — erro silencioso, pior de detectar que um campo vazio.
- **O KPI de relevância precisa ser reavaliado.** O pool de candidatos cresceu
  51%; os casos de `test_relevance.py` foram calibrados sobre 167 produtos.

## Alternativas descartadas

| Alternativa | Por que não (agora) |
| --- | --- |
| Só melhorar o parser, manter as regras | Deixaria 54 produtos fora por specs que o título genuinamente não traz |
| Só afrouxar as regras | Não resolveria as 60 rejeições por marca — a maior fatia — e trataria o sintoma |
| Completar as specs à mão no YAML | Dado inventado num seed que é evidência de engenharia; pior que ausente |
| Regerar o seed pelo `build_seed.py` | Exige credencial do ML e refaz a coleta; os títulos já estão versionados |

## Caminho de evolução / gatilho de revisão

- **Enriquecimento por SKU:** as specs faltantes de notebook existem na API do ML
  (`PROCESSOR_MODEL`, `RAM_MEMORY`, `STORAGE_CAPACITY`). Buscá-las por SKU
  devolveria o dado real e permitiria **voltar a `required: true`** — é o caminho
  preferencial, coerente com o ADR-0001.
- **Gatilho:** se a comparação começar a exibir muitas linhas vazias, ou se o
  filtro por atributo passar a errar por omissão, priorizar o enriquecimento em
  vez de afrouxar mais.
- **Rever o fallback de `type`** se entrar categoria/fonte com mais over-ear.
- **Recalibrar `test_relevance.py`** contra o catálogo de 252.

## Impacto futuro

- `worker/tools/seedbuilder/title_parser.py`: `BRANDS`, `_CLIP_ABERTO`, ramo final
  de `parse_headphone`.
- `worker/tools/seedbuilder/backfill.py`: novo.
- `worker/seed/categories.json` e `seed/products/headphones.yaml` (64 produtos
  completados; `notebooks.yaml` não mudou — os títulos não trazem as specs).
- Não altera schema de banco, migrations nem contrato da API.
