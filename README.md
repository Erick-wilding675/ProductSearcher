# 🔎 ProductSearcher

Plataforma inteligente de **descoberta, comparação e análise de produtos**, com busca, filtros, ranking, comparação e IA opcional.

> A aplicação funciona sem LLM.  
> Contexto técnico: [`.ai/ai.md`](.ai/ai.md)

---

## 📦 Estrutura

```text
api/         # Backend FastAPI
worker/      # Ingestão e preparação do catálogo
frontend/    # Next.js + TypeScript + Tailwind
infra/       # Infraestrutura e deploy
docs/        # Documentação do projeto
adr/         # Architecture Decision Records
.ai/         # Contexto para agentes de IA
```

---

## 🚀 Rodar localmente

### Pré-requisitos

- Docker + Docker Compose
- Node.js + npm

### 1. Preparar o ambiente

Na raiz do repositório:

```bash
cp .env.example .env
docker compose up -d db api
```

### 2. Aplicar as migrations

```bash
docker compose exec api alembic upgrade head
```

Essa etapa prepara o schema e os recursos utilizados pela busca, incluindo Full Text Search, `unaccent` e `pgvector`.

### 3. Carregar o catálogo

```bash
docker compose run --rm worker
```

Confirme que os dados foram carregados:

```bash
curl http://localhost:8000/categories
```

As categorias devem aparecer com `product_count > 0`.

### 4. Subir o frontend

```bash
cd frontend
npm install
npm run dev
```

Acesse:

- **Web:** http://localhost:3000
- **API:** http://localhost:8000
- **Health:** http://localhost:8000/health

> `docker compose up` sozinho não prepara um banco novo.  
> Não pule as migrations e o seed.

---

## ✅ Validação rápida

Teste a busca:

```bash
curl "http://localhost:8000/search?q=notebook"
```

A resposta deve conter resultados em JSON.

---

## 🧪 Testes

### API e worker

```bash
make test
```

### Lint + testes

```bash
make ci
```

### Frontend

```bash
cd frontend
npm run lint
npm run build
```

### Smoke test E2E

O Playwright valida o fluxo principal:

```text
busca → seleção de produtos → comparação
```

Execute:

```bash
cd frontend
npm run test:e2e
```

Para acompanhar a execução no navegador:

```bash
npm run test:e2e:headed
```

---

## 🛠️ Comandos úteis

```bash
make help
make install
make lint
make format
make test
make ci
make migrate
make seed
make up
make down
make logs
```

Os comandos `make migrate` e `make seed` utilizam o ambiente Python do host.

Para o onboarding via Docker, prefira:

```bash
docker compose exec api alembic upgrade head
docker compose run --rm worker
```

---

## 🐍 Desenvolvimento Python sem Docker

Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e "./api[dev]" -e "./worker[dev]"
```

No Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## 🗄️ Banco em outra porta

Se a porta `5432` já estiver ocupada:

```bash
DB_PORT=5433 docker compose up -d db api
```

Dentro da rede Docker, os serviços continuam utilizando `db:5432`.

---

## 📚 Documentação

- [PRD](docs/prd.md)
- [Arquitetura](docs/architecture.md)
- [ADRs](adr/README.md)
- [Modelo de dados](docs/data-model.md)
- [Design system](docs/design-system.md)

---

## 🧱 Stack

Next.js · React · TypeScript · Tailwind CSS · Playwright · FastAPI · PostgreSQL · Full Text Search · pgvector · SQLAlchemy · Alembic · Docker

---

## 📌 Status

Projeto em evolução por fases.

O fluxo principal de busca e comparação possui **smoke test E2E automatizado com Playwright**.

---

## 📄 Licença

Distribuído sob a **Business Source License 1.1 (BUSL-1.1)** — ver [`LICENSE`](LICENSE).

Em **2030-07-01**, a licença converte automaticamente para **Apache License 2.0**.

Motivação e trade-offs: [ADR-0006](adr/0006-licenciamento-busl.md).