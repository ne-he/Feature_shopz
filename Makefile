# Makefile — common developer commands for feature-store-mvp.
# Usage: `make <target>`. Run `make help` to list targets.

.DEFAULT_GOAL := help
.PHONY: help setup up down test lint format

help: ## Show this help message
	@echo "Available targets:"
	@echo "  setup   Install dependencies and pre-commit hooks"
	@echo "  up      Start PostgreSQL + Redis via Docker Compose"
	@echo "  down    Stop and remove Docker Compose services"
	@echo "  test    Run the test suite with coverage"
	@echo "  lint    Run Ruff linter and Mypy type checker"
	@echo "  format  Auto-format code with Black and Ruff"

setup: ## Install dependencies and pre-commit hooks
	pip install -e ".[dev]"
	pre-commit install

up: ## Start PostgreSQL + Redis via Docker Compose
	docker compose up -d

down: ## Stop and remove Docker Compose services
	docker compose down

test: ## Run the test suite with coverage
	pytest

lint: ## Run Ruff linter and Mypy type checker
	ruff check .
	mypy src/

format: ## Auto-format code with Black and Ruff
	black .
	ruff check --fix .
