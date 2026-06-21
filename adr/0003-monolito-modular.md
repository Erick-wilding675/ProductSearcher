# ADR-0003 — Arquitetura de backend: monólito modular

- **Status:** Aceito (MVP)
- **Data:** 2026-06-21
- **Decisor:** Erick

## Contexto

Precisamos definir a forma do backend que serve web app e extensão e executa busca, comparação, ranking e ingestão. Opções: monólito modular, microserviços, serverless puro. Restrições: equipe de 3 pessoas, free-tier, simplicidade; as instruções do projeto pedem evitar microserviços desnecessários e complexidade prematura.

## Decisão

Um **monólito modular em FastAPI** com módulos internos de fronteiras claras — **`catalog`**, **`search`**, **`ai`** (+ `core` compartilhado) — mais **um worker separado** para a ingestão do seed. **Sem API Gateway** e **sem microserviços** no MVP. Web app e extensão consomem a **mesma API**.

## Benefícios

- Simplicidade operacional (um deploy, um runtime).
- Fronteiras claras e testáveis (módulos desacoplados).
- Reaproveitamento da API entre clientes.
- Custo/ops mínimos (ideal para free-tier).
- Evolução natural (módulos bem definidos são fáceis de extrair).

## Consequências negativas

- Risco de acoplamento se a disciplina de módulos falhar (mitigado por interfaces e revisão).
- Escala por componente limitada (tudo escala junto).
- Um único deploy para toda a aplicação.

## Alternativas descartadas

| Alternativa | Por que não (agora) |
| --- | --- |
| Microserviços | Overhead de infra/observabilidade/DevOps despropositado para 3 pessoas; prematuro. **Descartado.** |
| Serverless puro (funções) | Cold start, fragmentação, possível lock-in; ruim para o popup da extensão. **Descartado.** |
| API Gateway na frente | Desnecessário sem múltiplos serviços. **Descartado no MVP.** |

## Caminho de evolução / gatilho de revisão

Extrair um módulo (provavelmente `search` ou `ai`) para serviço próprio **somente** com necessidade real: escala independente, time maior ou gargalo medido. O worker de ingestão **já é separado** — primeiro passo natural. Gatilho: gargalo isolado a um módulo, ou necessidade de deploy/escala independente.

## Impacto futuro

Organização de pastas por módulo; contratos internos via interfaces; a camada `ai` fica **atrás de interface** (liga com o princípio "funciona sem IA").
