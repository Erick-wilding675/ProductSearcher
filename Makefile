# ProductSearcher — comandos unificados de dev.
# Backend (api/worker): ruff + pytest. Frontend: eslint + prettier.
# Objetivo: lint/format/test rodando com um comando (RNF reprodutibilidade).
.DEFAULT_GOAL := help
.PHONY: help install lint format format-check test up down logs ci migrate seed

help: ## Lista os comandos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependências de dev (api, worker, frontend)
	cd api && pip install -e ".[dev]"
	cd worker && pip install -e ".[dev]"
	cd frontend && npm install

lint: ## Lint em todo o repo (ruff check + next lint)
	cd api && ruff check .
	cd worker && ruff check .
	cd frontend && npm run lint

format: ## Formata todo o repo (ruff format + prettier)
	cd api && ruff format . && ruff check --fix .
	cd worker && ruff format . && ruff check --fix .
	cd frontend && npm run format

format-check: ## Verifica formatação sem alterar arquivos
	cd api && ruff format --check .
	cd worker && ruff format --check .
	cd frontend && npm run format:check

test: ## Roda os testes (pytest) da api e do worker
	cd api && pytest -q
	cd worker && pytest -q

ci: lint test ## Replica localmente o que a CI roda (lint + test)

migrate: ## Aplica as migrations no banco de DATABASE_URL (alembic upgrade head)
	cd api && alembic upgrade head

seed: ## Carrega o catálogo seed no banco de DATABASE_URL
	cd worker && python -m ingestion.pipeline

up: ## Sobe o ambiente local (Postgres + API)
	docker compose up -d --build

down: ## Derruba o ambiente local
	docker compose down

logs: ## Acompanha os logs dos serviços
	docker compose logs -f
