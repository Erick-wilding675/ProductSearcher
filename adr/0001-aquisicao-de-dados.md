# ADR-0001 — Aquisição de dados do catálogo

- **Status:** Aceito (MVP)
- **Data:** 2026-06-21 (atualizado em 2026-07-09 após validar o Apify + API do ML)
- **Decisor:** Erick

## Contexto

Todo o valor do ProductSearcher depende de dados de produtos (catálogo, specs, ofertas, preços). Fontes possíveis: scraping direto de marketplaces, APIs oficiais/afiliados, **dataset seed curado** e scraping gerenciado (ex.: APIFY). Restrições: equipe de 3 pessoas, orçamento ~US$0, **projeto de portfólio público** (risco reputacional/jurídico), MVP precisa ser entregável.

## Decisão

No MVP, o catálogo vive como um **dataset seed curado** — YAML **versionado** em `worker/seed/products/`, carregado por um **pipeline reprodutível** (raw → normalização → validação → upsert). O **runtime nunca depende de fonte externa**: só lê o seed.

O seed é **gerado offline** por um seed-builder (`worker/tools/seedbuilder/`), que combina:

1. **Apify** (actor de listagem do Mercado Livre) → produto, preços, oferta e o **item ID** (`SKU = MLB…`).
2. **API do Mercado Livre** (`/items/{id}` → `attributes`) → **specs estruturadas** (CPU/RAM/tela/…), via app dev com token.
3. **Parser de título** → fallback determinístico para specs ausentes.

## Validação do Apify + API do ML (2026-07)

Exploramos o Apify: **os actors de listagem (Mercado Livre, Amazon, Magalu) não retornam a ficha técnica** — as specs só existem embutidas no título. Porém o CSV traz o **item ID** (`SKU`), que dá acesso às specs estruturadas pela **API oficial do ML** (que passou a exigir **access token** OAuth desde 2024). Conclusão: Apify resolve produto/preço/oferta; a API do ML resolve as specs; o parser de título cobre lacunas. Tudo isso roda **offline** para gerar o seed — coerente com "o sistema funciona sem fonte externa".

## Benefícios

- **Zero risco jurídico/ToS** no runtime; a coleta é offline e via API oficial.
- **Reprodutibilidade** — seed versionado recria o catálogo.
- **Qualidade controlada** — specs validadas por categoria (ADR-0005 D4/D6).
- **Desacoplamento** — `IngestionSource` é agnóstica à fonte; Apify/ML são só geradores do seed.
- **Foco no diferencial** — esforço vai para o produto, não para um coletor frágil.

## Consequências negativas

- Catálogo **limitado** ao que é curado; atualização de preços não é em tempo real.
- Depende de um **token do ML** (app dev gratuito) para as specs estruturadas — passo manual, offline.
- Cobertura de specs varia por categoria (notebooks têm boa cobertura por título; fones dependem mais da API).

## Alternativas descartadas

| Alternativa | Decisão |
| --- | --- |
| Scraping direto de marketplaces | Viola ToS, frágil, risco jurídico. **Descartado.** |
| APIs oficiais/afiliados como fonte de runtime | Burocracia, limites, dependência externa no caminho crítico. **Não usar em runtime** (a API do ML é usada só offline p/ o seed). |
| APIFY como fonte de runtime | Custo/credenciais e dado sem specs. **Validado e adotado apenas offline** (gera o seed). |

## Caminho de evolução / gatilho de revisão

Revisar quando: (a) precisar de catálogo amplo/atualizado (ex.: preço em tempo → agendar o seed-builder ou um worker de preços); (b) entrar nova fonte (Amazon/Magalu) — cabe na mesma `IngestionSource`; (c) o volume justificar automatizar a coleta. A dimensão de "atualidade" de preço é o principal gatilho.

## Impacto futuro

A **interface de ingestão** (`IngestionSource`) permanece agnóstica à fonte, então trocar/adicionar fontes não muda o runtime. O seed-builder (`worker/tools/seedbuilder/`, com `ml_auth`/`ml_api`/`mapping`/`title_parser`) é a peça que evolui conforme novas fontes/categorias. Relacionado: ADR-0005 (schema + ingestão).
