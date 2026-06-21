# ADR-0001 — Aquisição de dados do catálogo

- **Status:** Aceito (MVP)
- **Data:** 2026-06-21
- **Decisor:** Erick

## Contexto

Todo o valor do ProductSearcher depende de dados de produtos (catálogo, specs, ofertas, preços). Fontes possíveis: scraping direto de marketplaces, APIs oficiais/afiliados, dataset seed curado e scraping gerenciado (ex.: APIFY). Restrições: equipe de 3 pessoas, orçamento ~US$0, **projeto de portfólio público** (risco reputacional/jurídico), MVP precisa ser entregável.

## Decisão

No MVP, usar um **dataset seed curado** — montado manual/semi-automático, **versionado** e carregado por um **pipeline reprodutível** (raw → normalização → validação → persistência). Ingestão automatizada e fontes externas ficam para fases posteriores.

## Benefícios

- Zero risco jurídico/ToS — essencial num portfólio público.
- Destrava o resto do produto (busca, comparação, extensão).
- Qualidade controlada (specs validadas por categoria).
- Reprodutibilidade (seed versionado).
- Foco no diferencial, não num coletor frágil.

## Consequências negativas

- Catálogo limitado (poucas categorias, ~150 produtos).
- Trabalho manual de curadoria.
- Preços podem desatualizar.
- Cobertura restrita afeta a extensão — mitigada pela ativação por categoria.

## Alternativas descartadas

| Alternativa | Por que não (agora) |
| --- | --- |
| Scraping direto de marketplaces | Viola ToS, frágil (anti-bot/captcha/layout), risco jurídico. **Descartado.** |
| APIs oficiais / afiliados (Mercado Livre, Amazon PA-API, Best Buy) | Burocracia, requisitos (Amazon exige vendas), limites, dependência externa. **Adiado.** |
| APIFY (scraping gerenciado/"legal") | Pode reduzir risco/esforço; viabilidade jurídica/técnica/custo **a validar**. **Candidato futuro.** |

## Caminho de evolução / gatilho de revisão

Revisar quando: (a) for preciso catálogo amplo/atualizado; (b) preço em tempo (`price_history`) virar requisito central; ou (c) a validação de APIFY/APIs concluir viabilidade. Fase provável: APIFY ou APIs alimentando `offers`/`price_history`, mantendo o seed como fallback.

## Impacto futuro

A interface de ingestão (`IngestionSource`) deve ser **agnóstica à fonte**, para trocar seed por APIFY/API sem reescrever o consumo.
