.PHONY: up down api web worker migrate install test help

COMPOSE ?= docker compose
API_PORT ?= 8741
WEB_PORT ?= 43127

help:
	@echo "DevDeploy local targets:"
	@echo "  make up       Start Postgres + Redis via Docker Compose"
	@echo "  make down     Stop Compose services"
	@echo "  make api      Run FastAPI (uvicorn) on :$(API_PORT)"
	@echo "  make web      Run Next.js on :$(WEB_PORT)"
	@echo "  make worker   Run deployment pipeline worker"
	@echo "  make migrate  Run Alembic migrations"
	@echo "  make install  Install API + web dependencies"
	@echo "  make test     Run API pytest suite"

up:
	$(COMPOSE) up -d postgres redis

down:
	$(COMPOSE) down

api:
	cd apps/api && uv run uvicorn devdeploy_api.main:app --reload --host 0.0.0.0 --port $(API_PORT)

web:
	cd apps/web && npm run dev -- --hostname 127.0.0.1 --port $(WEB_PORT)

worker:
	cd apps/api && uv run python -m devdeploy_api.worker

migrate:
	cd apps/api && uv run alembic upgrade head

install:
	cd apps/api && uv sync
	cd apps/web && npm install

test:
	cd apps/api && uv run pytest -q

