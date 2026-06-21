# seed/ — Dataset seed (versionado)

Catálogo inicial curado (sem scraping — ADR-0001). Categorias do MVP: **notebooks + fones**.

## Organização sugerida

```
seed/
  categories.json   # categorias e seus atributos (category_attribute_schema)
  brands.json       # marcas
  products/         # produtos por categoria (ex.: notebooks.json, headphones.json)
  offers.json       # ofertas (loja, preço, url)
```

Cada produto deve trazer as specs obrigatórias da sua categoria (validadas na ingestão).
`categories.example.json` mostra o formato esperado.
