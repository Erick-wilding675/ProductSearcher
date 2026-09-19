# ADR-0012. Qualidade de ofertas na ingestão: classificar, não descartar

- **Status:** Aceito
- **Data:** 2026-09-19 (decisão e código de 2026-09-01, registrada no merge para a `main`)
- **Decisor(es):** Erick (tech lead)

## Contexto

O catálogo vem de listagens de marketplace (ADR-0001 e ADR-0009). Uma parte das ofertas
chega com preço que não descreve o produto: kit com vários itens anunciado sob o mesmo
`item ID`, erro de digitação do vendedor, anúncio de peça de reposição pendurado na página
do produto inteiro. O efeito aparece em três lugares de uma vez, porque os três consomem a
mesma coluna `offers.price`:

- o preço exibido no card de resultado, que usa o menor preço entre as ofertas;
- o fator `price` do ranking, que compara o produto contra o teto pedido pelo usuário;
- a comparação, que mostra preço lado a lado.

Uma oferta com preço absurdamente alto contamina o teto da categoria e empurra produtos
legítimos para baixo. Uma oferta com preço absurdamente baixo faria o inverso. O problema
não é de busca nem de ranking: é de dado, e precisa ser resolvido onde o dado entra.

A restrição que molda a decisão: **não temos como saber qual é o preço certo.** Só dá para
dizer que um valor é implausível dentro da própria categoria. Qualquer correção
automática seria invenção.

## Decisão

**D1. A triagem acontece na ingestão, entre a normalização e a validação.** O pipeline
passa a ser `fetch → normalize → data quality → validate → load`. O módulo
`worker/ingestion/data_quality.py` detecta, não corrige, e devolve a lista de ofertas
suspeitas junto dos produtos intactos.

**D2. Oferta suspeita é gravada, não descartada.** A tabela `offers` ganha
`quality_status` (`valid` ou `rejected`, com default `valid`) e `quality_reason` (texto
livre com o motivo e o limite que a oferta superou). Migration `e4f6a8b0c2d3`.

Descartar seria mais simples e seria pior: a reexecução da ingestão não deixaria rastro do
que foi removido, e não haveria como auditar um falso positivo nem calibrar os limites
depois. Gravar com marca custa uma coluna e mantém o dado original disponível.

**D3. A leitura filtra por `quality_status = 'valid'`.** O filtro está em três pontos, e
são os três que tocam preço: `FtsSearchProvider` (preço mínimo e fator de preço do
ranking), `CatalogRepository.get_product` (detalhe) e a consulta que alimenta a comparação.
O default `valid` na coluna garante que tudo que já estava no banco continue visível.

**D4. O limite é estatístico e por categoria, com dois critérios que precisam concordar.**
Uma oferta só é classificada como suspeita quando supera o **maior** entre:

```
mediana da categoria × 5
P99 da categoria     × 2
```

A mediana sozinha rejeitaria demais em categorias de cauda longa: fone premium
legitimamente custa muitas vezes a mediana de fones. O P99 sozinho é instável em amostra
pequena. Exigir que o valor supere o maior dos dois faz o critério errar para o lado de
aceitar, que é o lado certo quando o custo do falso positivo é esconder um produto real.

**D5. Amostra menor que 10 preços na categoria desliga a regra.** Inferência estatística
sobre 3 preços não é inferência. A categoria inteira passa sem triagem e o fato é logado,
em vez de aplicar um limite que não significa nada.

**D6. Só preço alto é tratado.** Preço baixo demais é um problema diferente (isca,
acessório listado como produto) que precisa de outro sinal além do próprio preço, e não
apareceu no catálogo atual em volume que justifique a regra.

## Benefícios

- O preço exibido e o preço que entra no ranking passam a ser preço de produto, não de
  kit ou de erro de digitação.
- A decisão é auditável: `select * from offers where quality_status = 'rejected'` devolve
  o que foi tirado de circulação e por quê.
- A regra é reproduzível e não usa modelo: mesmos dados, mesmo resultado.
- Calibrar os multiplicadores não exige reprocessar a fonte, só reexecutar a ingestão.

## Consequências negativas

- **Os multiplicadores são um chute educado.** `5` e `2` vieram da distribuição do seed
  atual, não de uma análise de erro sobre gabarito. Não há, hoje, medida de quantos falsos
  positivos e falsos negativos a regra produz.
- **O limite se move com o catálogo.** Mediana e P99 são recalculados a cada ingestão, então
  a mesma oferta pode mudar de classificação quando o catálogo muda. É o preço de um limite
  relativo, e o `quality_reason` grava o limite vigente na hora da decisão.
- **Um produto cujas ofertas foram todas rejeitadas fica sem preço.** Ele continua
  aparecendo na busca com `min_price` nulo, o que é melhor que aparecer com preço errado,
  mas a UI precisa tratar o caso.
- Mais duas colunas em `offers` e um passo a mais no pipeline.

## Alternativas descartadas

| Alternativa | Por que não |
| --- | --- |
| Descartar a oferta suspeita no `load` | Sem rastro para auditar nem para calibrar; um falso positivo some em silêncio |
| Corrigir o preço (usar a mediana das outras ofertas do produto) | Inventa dado. O sistema passaria a exibir um preço que nenhuma loja pratica |
| Filtrar por limite absoluto por categoria (constante no código) | Quebra quando o catálogo cresce ou a categoria muda de faixa; exige manutenção manual |
| Tratar no ranking, em vez da ingestão | Resolveria o ranking e deixaria o card e a comparação errados, porque os três leem a mesma coluna |
| Detecção por modelo (isolation forest e afins) | Complexidade e dependência desproporcionais para uma regra que cabe em duas linhas de estatística, e contra o princípio 1 do projeto |

## Caminho de evolução / gatilho de revisão

- **Gatilho de calibração:** ofertas legítimas aparecendo como `rejected`, ou preço errado
  passando como `valid`, em qualquer volume observável. A resposta é medir a regra contra
  um gabarito manual de ofertas antes de mexer nos multiplicadores, não ajustar por
  intuição.
- **Gatilho para tratar preço baixo:** produto entrando no topo do ranking por causa de um
  acessório listado como o produto. Exigiria um sinal além do preço, porque preço baixo
  legítimo (promoção real) é exatamente o que o usuário procura.
- **Gatilho para expor no produto:** se a UI precisar mostrar "há ofertas fora da faixa",
  a coluna já carrega o motivo e basta um campo no schema de resposta.

## Impacto futuro

- **Dados:** `offers.quality_status` e `offers.quality_reason` (migration `e4f6a8b0c2d3`).
  Ver [`docs/data-model.md`](../docs/data-model.md).
- **Worker:** `ingestion/data_quality.py` (novo), `ingestion/pipeline.py` (o passo novo),
  `ingestion/load.py` (persistência da classificação), `ingestion/models.py`
  (`OfferRejection`), `ingestion/schema.py`. O relatório do pipeline passa a devolver
  `rejected_offers`.
- **API:** `app/search/providers.py`, `app/catalog/repository.py` e a comparação filtram
  por `quality_status = 'valid'`.
- **Testes:** `worker/tests/test_data_quality.py`.
- **Operação:** a migration precisa rodar no banco antes do deploy do código que lê a
  coluna, como todas as outras (ADR-0011 D7).
