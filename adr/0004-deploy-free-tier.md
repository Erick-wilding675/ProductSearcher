# ADR-0004 — Deploy e infraestrutura (free-tier)

- **Status:** Aceito (MVP) — **ponto em aberto fechado pelo [ADR-0011](0011-deploy-producao-fly-io.md)**
- **Data:** 2026-06-21 (atualizado em 2026-09-18)
- **Decisor:** Erick

## Contexto

O MVP precisa hospedar **frontend**, **backend** e **banco** com orçamento ~US$0, mantendo uma **demo pública apresentável** (sem cold start visível) e ambiente **reprodutível**. Realidades de free-tier verificadas em **jun/2026** (sujeitas a mudança):

- **Railway:** não tem free real (trial US$5/30d, depois ~US$1/mês mínimo).
- **Render free:** derruba o serviço após 15 min de inatividade, com cold start de 30–60s.
- **Supabase free:** pausa o projeto após 7 dias sem requisições; inclui pgvector; até 2 projetos.
- **Vercel free:** adequado para o frontend Next.js.

## Decisão

- **Frontend:** Vercel (free).
- **Backend:** host **sem cold start** — preferência **Fly.io**; alternativa **Hugging Face Spaces**. Evitar Render free (cold start).
- **Banco:** Supabase (FTS + pgvector) com **cron/keep-alive** contra a pausa de 7 dias.
- **Dev local:** Docker Compose.

## Benefícios

- Custo ~US$0 mantendo a demo viva.
- Sem cold start perceptível (meta RNF-02 < 2s).
- pgvector grátis no Supabase (alinhado ao ADR-0002).
- Reprodutível via Docker Compose.

## Consequências negativas

- Free-tier impõe limites (CPU/RAM/horas) e exige keep-alive.
- Múltiplos provedores para gerenciar.
- Pode exigir upgrade barato (~US$5–7/mês) se a demo precisar de mais robustez.

## Alternativas descartadas

| Alternativa | Por que não (agora) |
| --- | --- |
| Railway | Sem free real (US$1–5/mês). **Descartado para ~US$0.** |
| Render free (backend) | Cold start de 30–60s arruína demo e popup da extensão. **Descartado.** |
| PaaS pago único | Fora do orçamento do MVP. **Adiado.** |

## Ponto em aberto — fechado em 18/09/2026

O host definitivo do backend era **Fly.io vs Hugging Face Spaces**. O [ADR-0011](0011-deploy-producao-fly-io.md) fecha em **Fly.io** (`shared-cpu-1x`, 256 MB, região `gru`, sem sleep) e revisa três premissas desta ADR:

- **Custo não é ~US$0**: o free tier do Fly acabou; o serviço custa ~US$2/mês.
- **Região do banco**: o Supabase sai de `us-east-1` para `sa-east-1`, junto do backend (ADR-0011 D3).
- **Keep-alive**: deixa de ser cron e passa a ser o health check do próprio host sobre `/health` (ADR-0011 D4).

## Caminho de evolução / gatilho de revisão

Migrar para tier pago barato se uptime/limites apertarem; consolidar provedor se o custo justificar. Gatilhos: RNF-02 não atingido, ou limites de free-tier estourando sob uso de demo.

## Referências (free-tier, verificado jun/2026)

- Railway — Free Trial (docs): https://docs.railway.com/pricing/free-trial
- Render — free tier / cold start: https://deploybase.app/blog/render-free-tier-complete-guide-2026
- Supabase — limites do free tier: https://www.itpathsolutions.com/supabase-free-tier-limits
