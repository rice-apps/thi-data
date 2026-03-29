ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

DOCKER_COMPOSE ?= docker compose
DC := cd $(ROOT) && $(DOCKER_COMPOSE) -f $(ROOT)/docker-compose.yml

.PHONY: help install install-client install-server \
	wait-db wait-api migrate \
	up up-detach start deploy down stop build ps \
	dev dev-local infra-local \
	run-server-local run-client-local \
	test

.DEFAULT_GOAL := help

help:
	@echo "thi-data — one-command workflows"
	@echo ""
	@echo "  make dev           Full Docker stack (API, worker, DB, queue, S3) + Next.js dev server"
	@echo "  make dev-local     DB/RabbitMQ/SeaweedFS in Docker; FastAPI + Next.js on host (hot reload)"
	@echo "  make up            Same services as dev, all logs in this terminal (foreground)"
	@echo "  make up-detach     Full stack in the background"
	@echo "  make migrate       Apply idempotent SQL only (safe to repeat; uses one-off backend container)"
	@echo "  make install       client npm install + server venv + pip (for dev-local)"
	@echo "  make test          ensures Docker stack is up, waits for API, runs pytest"
	@echo "  make deploy        production-style: full stack in background + DB/API ready (no Next.js)"
	@echo "  make down          Stop and remove containers"
	@echo ""
	@echo "Override compose if needed: make dev DOCKER_COMPOSE='docker-compose'"
	@echo ""

install: install-client install-server

install-client:
	cd $(ROOT)/client && npm install

install-server:
	@if ! command -v python3 >/dev/null 2>&1; then echo "python3 not found"; exit 1; fi
	cd $(ROOT)/server && (test -d venv || python3 -m venv venv)
	cd $(ROOT)/server && ./venv/bin/pip install -U pip && ./venv/bin/pip install -r requirements.txt

wait-db:
	@echo "Waiting for Postgres (thi-db)..."
	@cd $(ROOT) && until $(DOCKER_COMPOSE) -f docker-compose.yml exec -T db pg_isready -U postgres -d postgres 2>/dev/null; do sleep 1; done
	@echo "Postgres is ready."

# test_api.py talks to a live uvicorn; without this, make test can race right after compose up.
wait-api:
	@echo "Waiting for backend HTTP..."
	@cd $(ROOT) && until $(DOCKER_COMPOSE) -f docker-compose.yml exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)" 2>/dev/null; do sleep 1; done
	@echo "API is ready."

# Ensures schema matches server/migrations/init_db.sql even when the data volume already exists
# (docker-entrypoint init scripts only run on first DB create). Re-running is safe.
migrate:
	$(DC) up -d db
	@$(MAKE) wait-db
	$(DC) run --rm --no-deps backend python -c "from core.database import run_migrations; run_migrations()"

build:
	$(DC) build

up:
	$(DC) up --build

up-detach start:
	$(DC) up -d --build

# Same images as setup.md “On-Prem Deployment”: Postgres, RabbitMQ, SeaweedFS, API, Celery.
# Serve the Next.js app separately (e.g. Vercel or `npm run start`); nothing to docker-compose for the client yet.
deploy: up-detach wait-db wait-api
	@echo "Stack is up — API http://localhost:8000/docs | RabbitMQ http://localhost:15672 (guest/guest)"

down stop:
	$(DC) down

ps:
	$(DC) ps

# Bring DB up first so wait-db / migrate always succeed; stack applies migrations again on API boot (idempotent).
dev: up-detach wait-db migrate
	cd $(ROOT)/client && (test -d node_modules || npm install) && npm run dev

infra-local:
	$(DC) up -d --build db rabbitmq seaweedfs

dev-local: install infra-local wait-db migrate
	@echo "Starting local backend :8000 and Next.js :3000 — Ctrl+C stops both"
	@$(MAKE) -j2 run-server-local run-client-local

run-server-local:
	@test -x $(ROOT)/server/venv/bin/uvicorn || (echo "Run 'make install' first (need server/venv)." && false)
	cd $(ROOT)/server && ./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-client-local:
	cd $(ROOT)/client && npm run dev

test:
	$(DC) up -d db rabbitmq seaweedfs backend celery_worker
	@$(MAKE) wait-db wait-api
	$(DC) exec -T backend pytest
