# CheckStock

Прототип учёта остатков по складам фулфилмента (ФФ): приход, перемещения,
FBS, FBO. Python 3.13 + FastAPI + PostgreSQL, интерфейс на React.

## Команды

```bash
make up          # собрать и запустить всё в Docker
make test        # доменные + сквозные тесты на PostgreSQL
make lint        # ruff
make check-arch  # границы слоёв (import-linter)
```

## Устройство

Бэкенд — гексагональная архитектура, зависимости направлены внутрь:

```
backend/app/
  domain/          правила учёта, чистый Python: остаток, документы, журнал, порты
  application/     операции (commands.py) и чтение (queries.py)
  infrastructure/  PostgreSQL: unit of work, репозитории, SQL для чтения
  api/             FastAPI: маршруты, схемы, перевод ошибок
  main.py          точка сборки: соединяет порты с PostgreSQL
```

Почему решения такие — в README.md, раздел «Ключевые решения».

## Обязательно

- Перед изменением бэкенда прочитать `.claude/rules/accounting.md`.
- Границы слоёв проверяют хук `.claude/hooks/validate_architecture.py`
  (до записи файла) и import-linter (`make check-arch`).
- После любого изменения учёта: `make test`. Сверка журнала с остатками
  должна проходить после каждого действия.

## Правила по областям

| Что редактируется | Файл правил |
|---|---|
| `backend/app/**` | `.claude/rules/accounting.md` |
| `backend/tests/**` | `.claude/rules/testing.md` |
| `frontend/src/**` | `.claude/rules/frontend.md` |
