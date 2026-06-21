# Glossário

- **SERP** — Search Engine Results Page (página de resultados do Google).
- **FTS** — Full-Text Search do PostgreSQL (busca textual).
- **pgvector** — extensão do PostgreSQL para busca vetorial (embeddings).
- **Embedding** — representação vetorial de texto para busca semântica.
- **Specs category-aware** — conjunto de specs válido depende da categoria do produto.
- **Seed / dataset seed** — catálogo inicial curado manualmente/semi-automático, versionado.
- **Ingestão** — pipeline raw → normalização → validação → persistência.
- **Idempotente (upsert)** — rodar a ingestão duas vezes não duplica dados.
- **Ranking determinístico** — ordenação reproduzível por critérios objetivos (sem LLM).
- **IntentParser** — extrai categoria/preço/atributos da query (determinístico no MVP).
- **MoSCoW** — Must / Should / Could / Won't (priorização).
- **ADR** — Architecture Decision Record.
- **Cliente fino** — a extensão consome a mesma API do web app, sem backend próprio.
- **Degradação graciosa** — extensão fica em silêncio em categorias não cobertas.
- **MVP** — Minimum Viable Product.
