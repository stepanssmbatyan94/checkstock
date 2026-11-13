#!/usr/bin/env python3
"""PreToolUse-хук: не даёт записать импорт, нарушающий границы слоёв.

Срабатывает на Write/Edit файлов в backend/app/domain и
backend/app/application. Те же правила в CI-виде проверяет import-linter
(`make check-arch`); хук ловит нарушение раньше — до записи на диск.

Код выхода 2 блокирует запись, текст из stderr возвращается агенту.
"""

from __future__ import annotations

import json
import re
import sys

FRAMEWORKS = ("sqlalchemy", "asyncpg", "fastapi", "starlette", "pydantic", "alembic")

# Слой → внутренние пакеты, которые ему запрещено импортировать.
FORBIDDEN_INTERNAL = {
    "domain": ("app.application", "app.infrastructure", "app.api"),
    "application": ("app.infrastructure", "app.api"),
}


def main() -> int:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input", {})
    path = tool_input.get("file_path", "")

    layer = next(
        (name for name in FORBIDDEN_INTERNAL if f"backend/app/{name}/" in path), None
    )
    if layer is None or not path.endswith(".py"):
        return 0

    text = tool_input.get("content") or tool_input.get("new_string") or ""
    forbidden = FRAMEWORKS + FORBIDDEN_INTERNAL[layer]
    pattern = re.compile(
        r"^\s*(?:from|import)\s+(" + "|".join(map(re.escape, forbidden)) + r")\b",
        re.MULTILINE,
    )
    found = sorted(set(pattern.findall(text)))
    if not found:
        return 0

    print(
        f"Слой {layer} не может импортировать: {', '.join(found)}.\n"
        "Зависимости направлены внутрь: api → infrastructure → application → domain.\n"
        "Нужен доступ к базе — объявите порт в app/domain/ports.py "
        "и реализуйте его в app/infrastructure.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
