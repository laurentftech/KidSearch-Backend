.PHONY: help clean test lint format docker-build docker-up docker-down install dev

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

clean: ## Clean temporary files and caches
	@echo "🧹 Cleaning temporary files..."
	@./scripts/cleanup.sh

test: ## Run tests with pytest
	@echo "🧪 Running tests..."
	@python -m pytest tests/ -v --cov=kidsearch --cov-report=term-missing

test-fast: ## Run tests without coverage
	@echo "🧪 Running tests (fast mode)..."
	@python -m pytest tests/ -v

lint: ## Run linter (ruff)
	@echo "🔍 Running linter..."
	@ruff check kidsearch/ dashboard/ tests/

format: ## Format code with ruff
	@echo "✨ Formatting code..."
	@ruff format kidsearch/ dashboard/ tests/

docker-build: ## Build Docker image
	@echo "🐳 Building Docker image..."
	@docker-compose build

docker-up: ## Start Docker containers
	@echo "🚀 Starting Docker containers..."
	@docker-compose up -d

docker-down: ## Stop Docker containers
	@echo "🛑 Stopping Docker containers..."
	@docker-compose down

docker-logs: ## Show Docker logs
	@docker-compose logs -f

install: ## Install dependencies
	@echo "📦 Installing dependencies..."
	@pip install -r requirements.txt

dev: ## Install development dependencies
	@echo "📦 Installing development dependencies..."
	@pip install -r requirements.txt
	@pip install -r tests/requirements-test.txt
	@pip install ruff mypy

release: ## Create a new release (usage: make release VERSION=v1.0.0)
	@if [ -z "$(VERSION)" ]; then \
		echo "❌ Error: VERSION not specified"; \
		echo "Usage: make release VERSION=v1.0.0"; \
		exit 1; \
	fi
	@./scripts/release.sh $(VERSION)

ci-test: ## Run tests as in CI
	@echo "🧪 Running CI tests..."
	@python -m pytest tests/ -v \
		--cov=kidsearch \
		--cov-report=xml \
		--cov-report=term \
		--junitxml=junit.xml

status: ## Show git status
	@git status

.DEFAULT_GOAL := help
