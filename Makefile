# MoneyTree — configurar ambiente e rodar API / frontend
# Uso: make help

.DEFAULT_GOAL := help

ROOT       := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV       := $(ROOT)/.venv
PY         := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip
UVICORN    := $(VENV)/bin/uvicorn
API_HOST   ?= 127.0.0.1
API_PORT   ?= 8000

export PYTHONPATH := $(ROOT)

.PHONY: help venv install-backend install-backend-llm install-frontend setup setup-llm \
	test api web clean-pyc

help: ## Mostra esta ajuda
	@grep -E '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

venv: ## Cria .venv na raiz do repositório (python3 -m venv)
	@test -d "$(VENV)" || python3 -m venv "$(VENV)"

install-backend: venv ## pip install -e backend[dev] (sem extras de LLM na nuvem)
	@"$(PIP)" install -U pip setuptools wheel
	@"$(PIP)" install -e "$(ROOT)/backend[dev]"

install-backend-llm: venv ## pip install -e backend[dev,llm]
	@"$(PIP)" install -U pip setuptools wheel
	@"$(PIP)" install -e "$(ROOT)/backend[dev,llm]"

install-frontend: ## npm install no frontend/
	cd "$(ROOT)/frontend" && npm install

setup: install-backend install-frontend ## Configura backend + frontend (recomendado)
	@echo "Setup concluído. API: make api | Frontend: make web"

setup-llm: install-backend-llm install-frontend ## setup com anthropic + openai (extra llm)
	@echo "Setup concluído (com extras LLM). API: make api | Frontend: make web"

test: ## Roda pytest (requer install-backend)
	@"$(PY)" -m pytest "$(ROOT)/tests" -q

api: ## Sobe FastAPI com reload (127.0.0.1:8000 por padrão; sobrescreva API_HOST/API_PORT)
	@"$(UVICORN)" backend.api.main:app --reload --host "$(API_HOST)" --port "$(API_PORT)"

web: ## Sobe Vite dev server (http://localhost:5173)
	cd "$(ROOT)/frontend" && npm run dev

clean-pyc: ## Remove __pycache__ e .pyc sob o repositório
	find "$(ROOT)" -type d -name __pycache__ -prune -exec rm -rf {} \; 2>/dev/null || true
	find "$(ROOT)" -type f -name '*.pyc' -delete 2>/dev/null || true
