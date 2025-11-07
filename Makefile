.PHONY: help install install-dev test lint format clean docker-build docker-up docker-down

help:
	@echo "Mitra Bot - Development Commands"
	@echo "================================"
	@echo "install          - Install production dependencies"
	@echo "install-dev      - Install development dependencies"
	@echo "test             - Run tests with coverage"
	@echo "lint             - Run linters (flake8, mypy)"
	@echo "format           - Format code (black, isort)"
	@echo "security-check   - Run security checks (bandit)"
	@echo "pre-commit       - Run pre-commit hooks"
	@echo "clean            - Remove build artifacts"
	@echo "docker-build     - Build Docker image"
	@echo "docker-up        - Start Docker services"
	@echo "docker-down      - Stop Docker services"
	@echo "run-dev          - Run development server"
	@echo "run-prod         - Run production server"

install:
	pip install -r requirements.txt

install-dev: install
	pip install pre-commit pytest pytest-cov pytest-asyncio black flake8 isort mypy bandit
	pre-commit install

test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing

lint:
	flake8 src/ --max-line-length=100 --extend-ignore=E203
	mypy src/ --ignore-missing-imports

format:
	black src/ --line-length=100
	isort src/ --profile=black --line-length=100

security-check:
	bandit -r src/ -c .bandit

pre-commit:
	pre-commit run --all-files

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info

docker-build:
	docker build -t mitra-bot:latest --target production .

docker-up:
	docker-compose -f docker-compose.prod.yml up -d

docker-down:
	docker-compose -f docker-compose.prod.yml down

docker-logs:
	docker-compose -f docker-compose.prod.yml logs -f mitra-bot

run-dev:
	python src/api/main_api.py

run-prod:
	gunicorn -c gunicorn_config.py wsgi:app

db-migrate:
	python setup_production.py

db-backup:
	@./scripts/backup-db.sh
