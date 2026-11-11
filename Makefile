# Manju Library: run `make` to list the commands.
#
#   make setup   install dependencies (first time only)
#   make dev     run the whole app: PostgreSQL and Redis in Docker, Django and React.
#                Ctrl+C stops everything.

SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173
# USE_DOCKER=0 uses a PostgreSQL and Redis you run yourself (set in backend/.env).
USE_DOCKER ?= 1

COMPOSE := docker compose -f docker-compose.yml
MANAGE := cd backend && uv run python manage.py

.PHONY: help setup deps dev services-up services-down migrate seed superuser worker shell \
	test test-backend test-frontend lint format build check docker-build clean

help: ## List the commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend and frontend dependencies and create backend/.env
	@command -v uv >/dev/null || { echo "Install uv first: https://docs.astral.sh/uv/"; exit 1; }
	@command -v npm >/dev/null || { echo "Install Node.js 22 first: https://nodejs.org/"; exit 1; }
	cd backend && uv sync
	cd frontend && npm ci
	@test -f backend/.env || { cp backend/.env.example backend/.env && echo "Created backend/.env"; }

deps:
	@test -d backend/.venv || (cd backend && uv sync)
	@test -d frontend/node_modules || (cd frontend && npm ci)

dev: deps services-up migrate ## Run the whole app (Ctrl+C stops everything)
	@for port in $(BACKEND_PORT) $(FRONTEND_PORT); do \
	  if command -v lsof >/dev/null && lsof -nP -iTCP:$$port -sTCP:LISTEN >/dev/null 2>&1; then \
	    echo "Port $$port is already in use. Pick free ones, for example:"; \
	    echo "  make dev BACKEND_PORT=8001 FRONTEND_PORT=5174"; \
	    exit 1; \
	  fi; \
	done
	@echo ""
	@echo "  App          http://localhost:$(FRONTEND_PORT)"
	@echo "  Back office  http://localhost:$(FRONTEND_PORT)/backoffice/"
	@echo "  First run? 'make seed' creates local logins. Student login codes appear in this log."
	@echo ""
	@trap 'trap - INT TERM; kill 0' INT TERM; \
	(cd backend && uv run python manage.py runserver 127.0.0.1:$(BACKEND_PORT)) & \
	(cd frontend && VITE_BACKEND_URL=http://127.0.0.1:$(BACKEND_PORT) npm run dev -- --port $(FRONTEND_PORT)) & \
	wait

services-up: ## Start PostgreSQL and Redis in Docker
ifeq ($(USE_DOCKER),1)
	@docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop, then run this again."; exit 1; }
	$(COMPOSE) up -d --wait
else
	@echo "USE_DOCKER=0: using the PostgreSQL and Redis set in backend/.env"
endif

services-down: ## Stop PostgreSQL and Redis (their data is kept)
	$(COMPOSE) down

migrate: ## Apply database migrations
	$(MANAGE) migrate

seed: ## Create the local Super Admin and a sample student
	$(MANAGE) seed_dev

superuser: ## Create a Super Admin account
	$(MANAGE) createsuperuser

worker: ## Run background jobs (Celery worker with the scheduler)
	cd backend && uv run celery -A config worker --beat --loglevel=INFO

shell: ## Open a Django shell
	$(MANAGE) shell

test: test-backend test-frontend ## Run all tests

test-backend: services-up ## Run backend tests (needs PostgreSQL)
	cd backend && uv run pytest

test-frontend: deps ## Run frontend tests
	cd frontend && npm test

lint: deps ## Lint, format-check and type-check everything
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npm run typecheck

format: ## Auto-format the backend
	cd backend && uv run ruff check --fix . && uv run ruff format .

build: deps ## Build the React app for production
	cd frontend && npm run build

check: lint test build ## Everything CI runs

docker-build: ## Build the production Docker images
	docker build -t manju-library/backend:dev backend
	docker build -f deploy/nginx/Dockerfile -t manju-library/web:dev .

clean: ## Remove build output and caches
	rm -rf frontend/dist backend/staticfiles backend/.pytest_cache backend/.ruff_cache
