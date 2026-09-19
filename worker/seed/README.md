# seed: dataset versionado

Catálogo do MVP, versionado junto ao código (ADR-0001). Categorias: **notebooks** e
**fones de ouvido**.

## Organização real

```
seed/
  categories.json        categorias e seus atributos (vira category_attribute_schema)
  products/
    notebooks.yaml       122 produtos
    headphones.yaml      157 produtos
```

Não há `brands.json` nem `offers.json`: marcas e lojas são **derivadas** dos próprios
produtos durante a carga, e as ofertas vêm aninhadas em cada produto.

## `categories.json`

Lista de categorias. Cada uma declara os atributos que existem nela, o que alimenta
`category_attribute_schema` e é o que a validação cobra:

```json
{
  "slug": "headphones",
  "name": "Fones de ouvido",
  "attributes": [
    { "attribute_key": "type", "label": "Tipo", "data_type": "enum",
      "allowed_values": ["in-ear", "on-ear", "over-ear", "earbuds"],
      "unit": null, "required": true },
    { "attribute_key": "anc", "label": "Cancelamento de ruído (ANC)",
      "data_type": "boolean", "allowed_values": null, "unit": null, "required": true }
  ]
}
```

`data_type` aceita `text`, `number`, `boolean`, `enum` e `enum_multi`. Produto sem um
atributo `required: true` é rejeitado na validação (ADR-0005 D6).

O atributo `use_case` é `enum_multi` e seus `allowed_values` são o **conjunto fechado** de
rótulos que a rotulagem offline pode gravar. Rótulo fora dessa lista vira filtro que não
casa com nada, em silêncio: o `RuleBasedIntentParser` da API precisa usar exatamente estes
valores.

## `products/*.yaml`

Uma lista de produtos por categoria, no formato `RawProduct`:

```yaml
- source: apify:mercadolivre
  external_id: MLB45574031
  name: Notebook Gamer Lenovo Loq 15irx9 Intel Core I5-13450hx RTX 3050 8GB 512GB SSD
  brand: Lenovo
  category: notebooks
  specs:
    cpu: Intel Core i5-13450HX
    ram_gb: 8
    storage_gb: 512
    storage_type: SSD
    screen_in: 15.6
    gpu: RTX 3050
  offers:
    - store: Mercado Livre
      price: '5794'
      currency: BRL
      url: https://www.mercadolivre.com.br/p/MLB45574031
```

As chaves de `specs` precisam bater com os `attribute_key` declarados na categoria. O
`external_id` é o **id de produto de catálogo** do Mercado Livre, não o id de anúncio: a
diferença já custou um enriquecimento inteiro que parecia funcionar e não funcionava (ver
[`../../docs/plano-dados-completos.md`](../../docs/plano-dados-completos.md) §2).

## Como este arquivo é gerado

O YAML não é escrito à mão. Ele sai do
[`seedbuilder`](../tools/seedbuilder/README.md), que transforma o CSV de listagem do Apify
em `RawProduct`, enriquecendo as specs pela API do Mercado Livre e caindo no parser de
título quando a API não cobre.

Depois de carregar o seed, a rotulagem de `use_case` roda à parte
(`tools/seedbuilder/label_use_cases.py`). **Recarregar o seed apaga os rótulos**, então a
re-rotulagem é passo obrigatório do runbook, não opcional.

## Carregar

```bash
make seed                                  # pela raiz
cd worker && python -m ingestion.pipeline  # direto
```
