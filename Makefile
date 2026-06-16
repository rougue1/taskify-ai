# Taskify — Docker stack shortcuts.
#
#   make dev           # build + start the whole stack
#   make pull-models   # pull the Ollama models (run once, after `make dev`)
#   make migrate       # apply DB migrations inside the backend container
#   make logs          # tail all container logs
#
# Override the models inline, e.g. `make pull-models OLLAMA_TOOL_MODEL=llama3.2`.

COMPOSE ?= docker compose
OLLAMA_TOOL_MODEL ?= qwen3.5:9b
OLLAMA_EMBED_MODEL ?= nomic-embed-text

.PHONY: dev build up down pull-models migrate logs ps clean

dev: ## Build and start the full stack (postgres, ollama, backend, frontend)
	$(COMPOSE) up --build

up: ## Start the stack in the background
	$(COMPOSE) up -d

build: ## Build all images without starting
	$(COMPOSE) build

down: ## Stop and remove the stack's containers
	$(COMPOSE) down

pull-models: ## Pull the Ollama models the app uses (tool + embeddings)
	$(COMPOSE) exec ollama ollama pull $(OLLAMA_TOOL_MODEL)
	$(COMPOSE) exec ollama ollama pull $(OLLAMA_EMBED_MODEL)

migrate: ## Apply Alembic migrations inside the backend container
	$(COMPOSE) exec backend alembic upgrade head

logs: ## Tail logs from all services
	$(COMPOSE) logs -f

ps: ## Show running services
	$(COMPOSE) ps

clean: ## Stop the stack and remove its volumes (DESTROYS data)
	$(COMPOSE) down -v
