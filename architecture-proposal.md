# ProductSearcher — Proposed Architecture

# Visão Geral

O ProductSearcher será construído seguindo princípios de modularidade, separação de responsabilidades e evolução incremental.

A arquitetura deve permitir:

* execução local
* deploy em cloud
* reprodutibilidade
* escalabilidade futura
* integração com IA

---

# Arquitetura de Alto Nível

Frontend
↓
API Gateway
↓
Backend Services
↓
Search Layer
↓
Database Layer
↓
AI Layer

---

# Componentes

## Frontend

Tecnologia sugerida:

* Next.js
* TypeScript
* Tailwind
* Shadcn/UI

Responsabilidades:

* Interface do usuário
* Busca
* Comparação
* Dashboards
* Consumo das APIs

---

## API Layer

Tecnologia sugerida:

* FastAPI

Responsabilidades:

* Endpoints REST
* Autenticação
* Regras de negócio
* Orquestração

---

## Search Layer

Responsável por:

* ranking
* matching
* busca textual
* filtros

Possíveis tecnologias:

* PostgreSQL Full Text Search
* OpenSearch
* Elasticsearch

MVP:

PostgreSQL Full Text Search.

---

## Data Layer

Tecnologia:

* PostgreSQL

Possível uso:

* Supabase

Tabelas iniciais:

products

stores

offers

reviews

searches

users

---

# Pipeline de Dados

Objetivo:

Ingerir informações de produtos.

Fluxo:

Fonte
↓
Raw Data
↓
Normalização
↓
Enriquecimento
↓
Persistência

---

# Camadas de Dados

## Raw

Dados originais.

Sem transformação.

Objetivo:

Reprocessamento.

---

## Staging

Dados parcialmente tratados.

Objetivo:

Validação.

---

## Curated

Dados prontos para consumo.

Objetivo:

Busca e recomendação.

---

# IA

A IA deve ser desacoplada da aplicação principal.

---

## AI Service

Responsabilidades:

* NLP
* classificação
* extração de filtros
* geração de respostas

---

Exemplo:

Entrada:

"Melhor notebook para ciência de dados até R$ 5000"

Saída:

{
categoria: notebook,
preco_maximo: 5000,
uso: ciencia_de_dados
}

---

# LangGraph

Introduzir apenas após MVP funcional.

Fluxo sugerido:

User Query
↓
Intent Extraction
↓
Product Search
↓
Ranking
↓
Response Generation

---

# RAG

Objetivo:

Permitir consultas contextuais.

Base documental:

* especificações
* reviews
* benchmarks
* FAQs

---

Fluxo:

Question
↓
Embedding
↓
Vector Search
↓
Context Retrieval
↓
LLM
↓
Answer

---

# Banco Vetorial

Opções:

* Qdrant
* ChromaDB

Preferência inicial:

Qdrant

---

# Observabilidade

Ferramentas:

* LangSmith
* OpenTelemetry
* Structured Logging

Objetivos:

* rastreabilidade
* debugging
* monitoramento

---

# Infraestrutura

Desenvolvimento:

Docker Compose

Produção:

Frontend:
Vercel

Backend:
Render ou Railway

Banco:
Supabase

Redis:
Upstash

---

# Reprodutibilidade

Todo ambiente deve ser reproduzível através de:

docker compose up

ou

devcontainer

---

# Estrutura de Repositório

productsearcher/

frontend/

api/

workers/

search/

rag/

infra/

deploy/

docs/

tests/

scripts/

---

# Estratégia de Evolução

Fase 1

Busca + Comparação

---

Fase 2

Ranking Inteligente

---

Fase 3

Busca em Linguagem Natural

---

Fase 4

RAG

---

Fase 5

Agentes

---

# Princípio Arquitetural Principal

O sistema deve funcionar sem IA.

A IA deve atuar como camada de inteligência adicional.

Isso garante:

* menor acoplamento
* maior robustez
* redução de custos
* facilidade de manutenção
* liberdade para trocar provedores de LLM
