# Glossário

| Termo | Significado |
| --- | --- |
| **SERP** | Search Engine Results Page, a página de resultados do Google |
| **FTS** | Full Text Search do PostgreSQL |
| **unaccent** | Extensão do Postgres que dobra acento. Consulta e documento precisam passar pela mesma configuração de FTS, ou casam menos sem dar erro |
| **pgvector** | Extensão do PostgreSQL para busca vetorial |
| **Embedding** | Representação vetorial de texto. Aqui são 768 dimensões, geradas offline |
| **Carimbo de embedding** | Chave `_embedding` em `product_specs.attributes`, com modelo, dimensão e data. Produto carimbado por outro modelo volta a contar como pendente |
| **RRF** | Reciprocal Rank Fusion, a fusão usada pelo provider híbrido. Construída e desligada |
| **Specs category-aware** | O conjunto de specs válido depende da categoria do produto |
| **`use_case`** | Rótulo de um conjunto fechado (`jogos`, `trabalho`, `estudo`, `edicao-video`, `programacao`, `portabilidade` em notebooks; `esporte`, `chamadas`, `viagem`, `trabalho`, `jogos` em fones), gravado na ingestão por LLM. Em runtime é filtro JSONB comum, sem modelo no caminho. O parser traduz sinônimos da consulta ("gamer") para o rótulo (`jogos`) |
| **Seed** | Catálogo inicial curado e versionado, em YAML |
| **seedbuilder** | Ferramenta offline de dev que transforma a listagem do Apify no seed |
| **Ingestão** | Pipeline fetch, normalize, data quality, validate, load |
| **Idempotente (upsert)** | Rodar a ingestão duas vezes não duplica dados |
| **`quality_status`** | Classificação da oferta em `valid` ou `rejected`. Oferta suspeita é preservada para auditoria, não apagada |
| **Ranking determinístico** | Ordenação reproduzível por critérios objetivos, sem LLM |
| **Critérios e fatores** | `criteria` explica o que o ranking usou e com que peso; `factors` mostra a contribuição por item. É o que sustenta o RF-31 |
| **IntentParser** | Extrai categoria, preço, atributos e `use_case` da consulta. Determinístico |
| **Pool de candidatos** | Conjunto limitado (200) que o retrieval devolve para o ranking reordenar em memória |
| **Ativação por cobertura** | A extensão só age quando a busca casa com categoria que existe no catálogo |
| **Cliente fino** | A extensão consome a mesma API do web app, sem backend próprio |
| **Degradação graciosa** | Sem IA nem rede externa, busca e comparação continuam funcionando |
| **Keep-alive** | O health check do Fly a cada 30 s, que executa `SELECT 1` e evita a pausa do Supabase free |
| **Pooler de sessão e de transação** | Portas 5432 e 6543 do Supabase. DDL exige a de sessão; o runtime usa a de transação |
| **MoSCoW** | Must, Should, Could, Won't |
| **ADR** | Architecture Decision Record |
| **MVP** | Minimum Viable Product |
