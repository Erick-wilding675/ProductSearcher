# PRD — Product Requirements Document

**Produto:** ProductSearcher · **Versão:** 1.0 (Draft) · **Data:** 2026-06-21 · **Autor:** Erick

> Prioridades seguem **MoSCoW** (Must / Should / Could / Won't).

## 1. Objetivo

Definir, de forma priorizada, **o que** o ProductSearcher deve fazer no MVP e adiante — escopo, personas, casos de uso, requisitos funcionais e não-funcionais, regras, métricas e critérios de aceitação. O *como* vive nos ADRs e na arquitetura.

## 2. Visão

Plataforma de **descoberta, comparação e análise de produtos**. Entrega ranking, comparação e explicações em um só lugar — via web app e via **extensão Chrome contextual** sobre a SERP. **Não é um chatbot**; usa IA como camada complementar e funciona sem ela.

## 3. Problema

Decidir uma compra exige cruzar busca, reviews, fóruns, marketplaces e avaliações — fragmentado e demorado. Oportunidade no topo de funil ("melhor X para Y") e em comparações ("A vs B").

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

Equipe de 3 (1 sênior + 2 júnior). ~US$0 (teto ~US$10 API). Seed curado. Categorias iniciais: notebooks + fones. Deploy: Vercel + backend sem cold start + Supabase.

## 12. Critérios de aceitação do MVP

Todos os **Must** implementados e testados · seed ≥ 150 produtos em 2 categorias · busca/comparação/ranking sem LLM · web app + extensão na mesma API · deploy público reprodutível · documentação atualizada.

## 13. Questões em aberto

Categorias exatas · nº de produtos por categoria · host de backend (Fly.io vs HF) · fonte do seed (manual vs semi-automático).
