# =============================================================================
# TiBoutik / Wimi Backend Management Makefile
# =============================================================================

.PHONY: help venv install install-dev run runserver migrate makemigrations \
        showmigrations test test-verbose test-cov check lint format schema \
        validate-schema superuser shell clean flush collectstatic

# Configuration Variables
PORT ?= 8000
HOST ?= 0.0.0.0
SETTINGS ?= config.settings.local
TEST_SETTINGS ?= config.settings.test
VENV ?= .venv

# Python & Executables Detection
ifeq ($(wildcard $(VENV)/bin/python),)
	PYTHON := python3
	PYTEST := pytest
else
	PYTHON := $(VENV)/bin/python
	PYTEST := $(VENV)/bin/pytest
endif

# Default Target
.DEFAULT_GOAL := help

help: ## Show this interactive help menu
	@echo "========================================================================"
	@echo "                      TiBoutik / Wimi Backend                           "
	@echo "========================================================================"
	@echo ""
	@echo "Usage: make [target] [PORT=8000] [HOST=0.0.0.0]"
	@echo ""
	@echo "Available Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
	@echo ""

# -----------------------------------------------------------------------------
# Environment & Setup
# -----------------------------------------------------------------------------
venv: ## Create a new Python 3.12 virtual environment (.venv)
	@if [ -d "$(VENV)" ]; then \
		echo "Virtual environment already exists in $(VENV)"; \
	else \
		python3 -m venv $(VENV) && echo "Created virtual environment in $(VENV)"; \
	fi

install: ## Install production and development dependencies
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

# -----------------------------------------------------------------------------
# Development Server
# -----------------------------------------------------------------------------
run: runserver ## Alias for runserver

runserver: ## Start the Django development server (default port 8000)
	@echo "Starting Django server on http://$(HOST):$(PORT) [$(SETTINGS)]..."
	$(PYTHON) manage.py runserver $(HOST):$(PORT) --settings=$(SETTINGS)

# -----------------------------------------------------------------------------
# Database & Migrations
# -----------------------------------------------------------------------------
makemigrations: ## Generate new database migrations based on model changes
	$(PYTHON) manage.py makemigrations --settings=$(SETTINGS)

migrate: ## Apply pending database migrations to the configured database
	$(PYTHON) manage.py migrate --settings=$(SETTINGS)

showmigrations: ## Display migration status for all installed apps
	$(PYTHON) manage.py showmigrations --settings=$(SETTINGS)

flush: ## Flush all database records (keeps table schema)
	$(PYTHON) manage.py flush --settings=$(SETTINGS)

# -----------------------------------------------------------------------------
# Automated Testing & Quality
# -----------------------------------------------------------------------------
test: ## Run test suite using pytest
	$(PYTEST)

test-verbose: ## Run pytest with verbose test output
	$(PYTEST) -v

test-cov: ## Run test suite with terminal coverage report
	$(PYTEST) --cov=apps --cov-report=term-missing

check: ## Run Django system checks
	$(PYTHON) manage.py check --settings=$(SETTINGS)

# -----------------------------------------------------------------------------
# OpenAPI Schema & API Documentation
# -----------------------------------------------------------------------------
schema: ## Generate OpenAPI 3.0 schema file (schema.yml)
	$(PYTHON) manage.py spectacular --file schema.yml --settings=$(SETTINGS)
	@echo "OpenAPI 3.0 schema generated at schema.yml"

validate-schema: ## Validate OpenAPI 3.0 schema for syntax or structural issues
	$(PYTHON) manage.py spectacular --validate --settings=$(SETTINGS)

validate-postman: ## Validate JSON syntax and structure of postman.json
	$(PYTHON) -m json.tool postman.json > /dev/null && echo "✓ postman.json syntax is valid."

# -----------------------------------------------------------------------------
# Django Administration & Utilities
# -----------------------------------------------------------------------------
superuser: ## Create a new Django superuser administrator
	$(PYTHON) manage.py createsuperuser --settings=$(SETTINGS)

shell: ## Open an interactive Django shell session
	$(PYTHON) manage.py shell --settings=$(SETTINGS)

collectstatic: ## Collect static files for production deployment
	$(PYTHON) manage.py collectstatic --noinput --settings=$(SETTINGS)

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------
clean: ## Remove temporary cache files, pytest artifacts, and bytecode
	rm -rf .pytest_cache
	rm -rf .coverage htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "Cleaned Python and test artifacts."
