# PRD (Product Requirements Document)

**Produto:** ProductSearcher · **Versão:** 1.1 · **Criado em:** 2026-06-21 · **Revisado em:** 2026-09-19 · **Autor:** Erick

> Prioridades seguem **MoSCoW** (Must / Should / Could / Won't).

## 1. Objetivo

Definir, de forma priorizada, **o que** o ProductSearcher deve fazer no MVP e adiante: escopo, personas, casos de uso, requisitos funcionais e não-funcionais, regras, métricas e critérios de aceitação. O *como* vive nos ADRs e em [architecture.md](architecture.md).

A seção 14 registra o **estado de implementação** de cada requisito, com o arquivo ou a decisão que o sustenta. O requisito continua sendo o contrato; a seção 14 diz onde ele foi parar.

## 2. Visão

Plataforma de **descoberta, comparação e análise de produtos**. Entrega ranking, comparação e explicações em um só lugar, por web app e por **extensão Chrome contextual** sobre a SERP. **Não é um chatbot**: usa IA como camada complementar e funciona sem ela.

## 3. Problema

Decidir uma compra exige cruzar busca, reviews, fóruns, marketplaces e avaliações, o que é fragmentado e demorado. A oportunidade está no topo de funil ("melhor X para Y") e em comparações ("A vs B").

## 4. Objetivos e não-objetivos

**Objetivos (MVP):** buscar produtos por texto; comparar 2–4 por specs; ranking determinístico; catálogo seed curado; web app + extensão de demonstração; deploy público em free-tier.

**Não-objetivos:** cashback/cupons/afiliados/marketplace/pagamentos; mobile nativo; autenticação; scraping automatizado; agentes/RAG em produção.

## 5. Métricas de sucesso

| Métrica | Alvo MVP |
| --- | --- |
| Latência de busca (p95) | < 500 ms server-side |
| Relevância | ≥ 80% das queries de teste com o produto esperado no top-5 |
| Cobertura | 2 categorias, ≥ 150 produtos válidos |
| Disponibilidade da demo | sem cold start perceptível (< 2 s) |
| Qualidade de dados | 0 produtos sem specs obrigatórias |
| Extensão | popup responde em < 1,5 s em categorias cobertas |

## 6. Personas

- **Consumidor topo de funil:** não decidiu o modelo; quer ranking + critérios.
- **Comparador:** já tem candidatos; quer A vs B.
- **Curador de catálogo (interno):** mantém o seed.

## 7. Casos de uso

Descoberta · Comparação · Assistência contextual (extensão) · Curadoria. Detalhe em [use-cases.md](use-cases.md).

## 8. Requisitos funcionais (MoSCoW)

### Catálogo & dados
| ID | Requisito | Prioridade |
| --- | --- | --- |
| RF-01 | Produto com categoria, marca, nome, identificadores | Must |
| RF-02 | Specs por categoria (category-aware, JSONB) | Must |
| RF-03 | Ofertas (preço, loja, URL, moeda, timestamp) | Must |
| RF-04 | Histórico de preço | Should |
| RF-05 | Reviews resumidas | Could |
| RF-06 | Seed reprodutível/versionado | Must |

### Busca
| ID | Requisito | Prioridade |
| --- | --- | --- |
| RF-10 | Busca textual (FTS) | Must |
| RF-11 | Parser de intenção determinístico | Must |
| RF-12 | Filtros estruturados (preço, marca, atributos) | Must |
| RF-13 | Paginação e ordenação | Should |
| RF-14 | Busca semântica (pgvector) opcional | Should |
| RF-15 | Autocomplete | Could |
| RF-16 | Busca em linguagem natural via LLM | Could |

### Comparação
| ID | Requisito | Prioridade |
| --- | --- | --- |
| RF-20 | Comparar 2–4 produtos por specs | Must |
| RF-21 | Destacar diferenças/melhor valor | Should |
| RF-22 | Comparação a partir de "A vs B" | Should |
| RF-23 | Explicação textual das diferenças | Could |

### Ranking
| ID | Requisito | Prioridade |
| --- | --- | --- |
| RF-30 | Ranking determinístico por critérios objetivos | Must |
| RF-31 | Exibir critérios do ranking | Should |
| RF-32 | Score ponderado/ajustável | Could |

### Web app
| ID | Requisito | Prioridade |
| --- | --- | --- |
| RF-40 | Página de busca + resultados | Must |
| RF-41 | Painel de comparação | Must |
| RF-42 | Detalhe de produto | Should |
| RF-43 | Estado "sem resultados" | Must |
| RF-44 | Responsividade | Should |
| RF-45 | Acessibilidade básica | Should |

### Extensão Chrome
| ID | Requisito | Prioridade |
| --- | --- | --- |
| RF-50 | Ler query da SERP | Must |
| RF-51 | Ativação por cobertura de categoria | Must |
| RF-52 | Popup com top-N via API | Must |
| RF-53 | Fallback de botão flutuante | Should |
| RF-54 | Link para o web app | Should |
| RF-55 | Publicação na Web Store | Could |

### IA (complementar)
| ID | Requisito | Prioridade |
| --- | --- | --- |
| RF-60 | IA desacoplada; sistema opera sem ela | Must |
| RF-61 | Explicação via LLM (opcional) | Could |
| RF-62 | RAG sobre specs/reviews | Won't |
| RF-63 | Orquestração via LangGraph/agentes | Won't |

### Ingestão
| ID | Requisito | Prioridade |
| --- | --- | --- |
| RF-70 | Pipeline raw→normalização→validação→persistência | Must |
| RF-71 | Validação de specs obrigatórias por categoria | Must |
| RF-72 | Upsert idempotente | Should |
| RF-73 | Ingestão automatizada via APIs/fontes externas | Won't |

## 9. Requisitos não-funcionais (MoSCoW)

| ID | Categoria | Requisito | Prioridade |
| --- | --- | --- | --- |
| RNF-01 | Performance | Busca p95 < 500 ms | Must |
| RNF-02 | Disponibilidade | Sem cold start perceptível (< 2 s) | Should |
| RNF-03 | Custo | Free-tier (~US$0); teto ~US$10 p/ API | Must |
| RNF-04 | Reprodutibilidade | `docker compose up` sobe tudo | Must |
| RNF-05 | Observabilidade | Logging estruturado | Must |
| RNF-06 | Manutenibilidade | Monólito modular | Must |
| RNF-07 | Qualidade | Testes nos módulos críticos | Should |
| RNF-08 | Segurança | Sem segredos no repo | Must |
| RNF-09 | Privacidade (extensão) | Só query, sem PII | Must |
| RNF-10 | Portabilidade de IA | Trocar provider sem afetar core | Should |
| RNF-11 | Acessibilidade | WCAG AA nos fluxos principais | Should |
| RNF-12 | i18n | pt-BR; preparado para i18n | Could |
| RNF-13 | CI/CD | Pipeline automatizado | Should |
| RNF-14 | Escalabilidade evolutiva | Interfaces p/ trocar datastore | Should |

## 10. Regras de negócio

- Produto pertence a **uma** categoria; specs definidas pelo schema da categoria.
- Comparação só entre produtos da **mesma categoria**.
- Extensão só atua em **categorias cobertas** (senão, silêncio).
- Ranking **explicável e reproduzível**.
- Degradação graciosa: sem IA/rede externa, busca e comparação seguem funcionando.

## 11. Premissas e restrições

Equipe de 3 (1 sênior, 2 júnior). Custo próximo de US$0, com teto de aproximadamente
US$10 para API. Catálogo seed curado, sem scraping. Categorias iniciais: notebooks e
fones de ouvido. Topologia de deploy fechada no [ADR-0011](../adr/0011-deploy-producao-fly-io.md):
Vercel para o frontend, Fly.io em `gru` para o backend e Supabase em `sa-east-1` para o
banco.

## 12. Critérios de aceitação do MVP

| Critério | Estado |
| --- | --- |
| Todos os requisitos `Must` implementados e testados | Atendido, ver seção 14 |
| Seed com 150 ou mais produtos em 2 categorias | Atendido: 279 produtos no seed bruto (122 notebooks, 157 fones), 235 no catálogo depois da fusão de variantes |
| Busca, comparação e ranking funcionando sem LLM | Atendido: nenhum caminho de resposta chama modelo |
| Web app e extensão consumindo a mesma API | Atendido |
| Deploy público reprodutível | Atendido em 18/09/2026, com CI/CD (ADR-0011) |
| Documentação atualizada | Atendido; revisão de 2026-09-19 |

## 13. Questões fechadas e em aberto

As quatro questões abertas na versão 1.0 foram respondidas:

| Questão | Resposta | Onde |
| --- | --- | --- |
| Categorias exatas | Notebooks e fones de ouvido | ADR-0001 |
| Número de produtos por categoria | 122 notebooks e 157 fones no seed bruto; 235 produtos no catálogo após a fusão de variantes | ADR-0009 D3 |
| Host de backend (Fly.io ou Hugging Face) | Fly.io, `shared-cpu-1x` 256 MB em `gru`, sem sleep | ADR-0011 D2 |
| Fonte do seed (manual ou semi-automático) | Semi-automático: listagem do Apify mais enriquecimento pela API do Mercado Livre, com parser de título como fallback | ADR-0008, ADR-0009 |

Continuam em aberto:

- **p95 medido dentro do servidor.** A medição de 18/09/2026 foi feita de fora e inclui a
  travessia da internet, então vale como teto e não substitui o p95 server-side da RNF-01.
- **Publicação da extensão na Chrome Web Store** (RF-55).
- **Expurgo por idade em `searches`**, que hoje cresce sem limite.
- **Calibração dos limites de qualidade de oferta** contra gabarito manual (ADR-0012).

## 14. Estado de implementação

Legenda: **Feito**, entregue e em produção · **Construído, desligado**, existe e é testado
mas está atrás de flag desligada por decisão medida · **Não construído**, decisão explícita
de não fazer, com o gatilho que reabre a discussão · **Fora de escopo**, `Won't`.

### Catálogo e dados

| ID | Prioridade | Estado | Onde |
| --- | --- | --- | --- |
| RF-01 | Must | Feito | `worker/ingestion/`; tabelas `products`, `brands`, `categories` |
| RF-02 | Must | Feito | `product_specs.attributes` em JSONB, validado contra `category_attribute_schema` |
| RF-03 | Must | Feito | `offers`, com triagem de qualidade (ADR-0012) |
| RF-04 | Should | Feito | `price_history`, com ponto novo apenas quando o preço muda |
| RF-05 | Could | Não construído | A tabela `reviews` existe e está vazia: a API do Mercado Livre não expõe avaliação para token de aplicação. Gatilho: ator do Apify sobre a página do produto |
| RF-06 | Must | Feito | `worker/seed/`, versionado em YAML |

### Busca

| ID | Prioridade | Estado | Onde |
| --- | --- | --- | --- |
| RF-10 | Must | Feito | `FtsSearchProvider`, com `unaccent` (ADR-0010 D8) |
| RF-11 | Must | Feito | `RuleBasedIntentParser`, incluindo rótulos de `use_case` |
| RF-12 | Must | Feito | Filtros duros no retrieval: containment JSONB e faixas numéricas |
| RF-13 | Should | Feito | `page` e `sort` no `/search` |
| RF-14 | Should | Construído, desligado | `PgVectorProvider` e a carga offline existem; `vector_enabled=false`. Mediu pior que o FTS puro (ADR-0010 D4) |
| RF-15 | Could | Não construído | Autocomplete não entrou no MVP |
| RF-16 | Could | Não construído | O gatilho de D5 não passou: não há consulta real que o parser de regras deixe sem resposta (ADR-0010 D5.1) |

### Comparação

| ID | Prioridade | Estado | Onde |
| --- | --- | --- | --- |
| RF-20 | Must | Feito | `POST /compare`, de 2 a 4 produtos da mesma categoria |
| RF-21 | Should | Feito | `build_comparison` marca os atributos que diferem |
| RF-22 | Should | Não construído | A comparação parte da seleção na UI, não de uma consulta "A vs B" interpretada |
| RF-23 | Could | Não construído | Depende de RF-61, recusado em ADR-0010 D6.1 |

### Ranking

| ID | Prioridade | Estado | Onde |
| --- | --- | --- | --- |
| RF-30 | Must | Feito | `RankingService` determinístico; pesos em `app/search/ranking.py` |
| RF-31 | Should | Feito | `criteria` na resposta e `factors` por item |
| RF-32 | Could | Parcial | `rank_by` permite preferir marca, preço ou spec; os pesos em si não são ajustáveis pelo usuário |

### Web app

| ID | Prioridade | Estado | Onde |
| --- | --- | --- | --- |
| RF-40 | Must | Feito | `frontend/src/app/page.tsx` |
| RF-41 | Must | Feito | `frontend/src/app/compare/page.tsx` |
| RF-42 | Should | Feito | `frontend/src/app/products/[id]/page.tsx` |
| RF-43 | Must | Feito | `components/states/` cobre vazio, erro e carregamento |
| RF-44 | Should | Feito | Layout responsivo pelos breakpoints do Tailwind |
| RF-45 | Should | Parcial | Foco visível e rótulos acessíveis nos componentes principais; sem auditoria WCAG formal |

### Extensão

| ID | Prioridade | Estado | Onde |
| --- | --- | --- | --- |
| RF-50 | Must | Feito | `coverage.js` lê exclusivamente o `q` da URL |
| RF-51 | Must | Feito | Decisão local de cobertura, com cache de 1 h de `/categories` |
| RF-52 | Must | Feito | Painel na SERP e popup, ambos servidos pelo service worker |
| RF-53 | Should | Feito | Botão flutuante quando a injeção do painel falha |
| RF-54 | Should | Feito | `WEB_APP_URL` no link "ver todos" |
| RF-55 | Could | Não construído | Publicação na Chrome Web Store continua em aberto |

### IA

| ID | Prioridade | Estado | Onde |
| --- | --- | --- | --- |
| RF-60 | Must | Feito | Nenhum caminho de resposta chama modelo; a API sobe com `AI_ENABLED=false` por padrão |
| RF-61 | Could | Não construído | `DeterministicAIService` entrega a explicação. `LLMAIService` tem o desenho fechado e levanta `NotImplementedError`: foi recusado por não acrescentar nada ao determinístico (ADR-0010 D6.1), e não tem rota exposta |
| RF-62 | Won't | Fora de escopo | RAG sobre reviews permanece fora (ADR-0010 D7) |
| RF-63 | Won't | Fora de escopo | Sem orquestração por agentes |

### Ingestão

| ID | Prioridade | Estado | Onde |
| --- | --- | --- | --- |
| RF-70 | Must | Feito | `pipeline.py`: fetch, normalize, data quality, validate, load |
| RF-71 | Must | Feito | `validate.py` cobra as specs obrigatórias da categoria |
| RF-72 | Should | Feito | Upsert idempotente, com teste de integração |
| RF-73 | Won't | Fora de escopo | Sem ingestão automatizada em produção |

### Requisitos não-funcionais

| ID | Estado | Observação |
| --- | --- | --- |
| RNF-01 | Parcial | Medição externa de 18/09/2026, mediana de 349 ms em `/search`. O p95 server-side continua pendente |
| RNF-02 | Feito | `auto_stop_machines=false` mais health check a cada 30 s |
| RNF-03 | Feito | Free-tier em todas as camadas |
| RNF-04 | Feito | Docker Compose, seed versionado, migrations em Alembic |
| RNF-05 | Feito | Logging estruturado com `X-Request-ID` por requisição |
| RNF-06 | Feito | Monólito modular |
| RNF-07 | Feito | Suítes em api, worker, extensão e E2E, todas na CI |
| RNF-08 | Feito | Nenhum segredo versionado; o `.gitignore` cobre `.env` e seus backups |
| RNF-09 | Feito | A extensão envia apenas o `q`, e só em categoria coberta |
| RNF-10 | Feito | `AIService` e `VectorProvider` atrás de interface |
| RNF-11 | Parcial | Sem auditoria WCAG formal |
| RNF-12 | Não construído | pt-BR fixo, sem camada de i18n |
| RNF-13 | Feito | CI em cinco jobs e deploy disparado por `workflow_run` |
| RNF-14 | Feito | Providers trocáveis por interface |
