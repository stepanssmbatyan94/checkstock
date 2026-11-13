COMPOSE := docker compose
API     := $(COMPOSE) run --rm api

.PHONY: help up down reset logs test lint check-arch check

help:
	@echo "make up          Собрать и запустить всё (http://localhost:8080)"
	@echo "make down        Остановить"
	@echo "make reset       Стереть базу и поднять заново с тестовыми данными"
	@echo "make logs        Логи сервисов"
	@echo "make test        Тесты (доменные + сквозные на PostgreSQL)"
	@echo "make lint        Линтер ruff"
	@echo "make check-arch  Границы слоёв (import-linter)"
	@echo "make check       lint + check-arch + test"

up:
	$(COMPOSE) up --build -d
	@echo "Интерфейс: http://localhost:$${WEB_PORT:-8080}"
	@echo "API docs:  http://localhost:$${API_PORT:-8000}/docs"

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v
	$(MAKE) up

logs:
	$(COMPOSE) logs -f

# Тесты создают рядом отдельную базу checkstock_test и рабочие данные не трогают.
test:
	$(API) pytest

lint:
	$(API) ruff check .

check-arch:
	$(API) lint-imports

check: lint check-arch test
